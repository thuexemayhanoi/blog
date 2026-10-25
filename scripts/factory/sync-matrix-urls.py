#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đồng bộ URL trong hàng matrix với permalink THẬT của bài PUBLISHED, CÓ KIỂM SOÁT, theo lô, có hoàn tác (Issue #77).

Bối cảnh: một số hàng matrix của bài đã xuất bản ghi expected_url/canonical_url dạng `/<chuyên-mục>/YYYY/MM/DD/<slug>/`, trong khi permalink
THẬT trong front matter (thứ Jekyll xuất bản, sitemap và URL live dùng) là `/<chuyên-mục>/YYYY-MM-DD/<slug>/` hoặc
`/<chuyên-mục>/YYYY-MM-DD-<slug>/` (50 URL BLG-00820…BLG-00869). Công cụ này sửa MATRIX cho đúng URL thật. Nó KHÔNG đổi permalink, tên tệp,
thân bài hay URL live và KHÔNG tạo trang chuyển hướng: URL đang hoạt động giữ nguyên từng byte.
Hàng matrix là đầu vào của vân tay `matrix_row_sha256` mà evidence QA ràng buộc, nên đổi hàng buộc phải chấm lại ĐỘC LẬP và ghi evidence
mới có provenance — revise-published.py cấm đổi URL, migrate-slug-urls.py chỉ làm khi đổi slug. Công cụ này là đường GHI duy nhất cho ca này.

Một bài chỉ được đồng bộ khi thỏa MỌI điều kiện (tool tự kiểm từ byte hiện tại, không tin manifest, không có cờ ép):
  1. Hàng matrix PUBLISHED; KHÔNG thuộc baseline đ→d (hàng đó do migrate-slug-urls.py sửa cùng lúc đổi URL) và không có trong registry.
  2. Evidence NGUYÊN VẸN: content_sha256 == byte bài hiện tại, matrix_row_sha256 == vân tay hàng hiện tại, source_path đúng, result PASS.
     Evidence đã lệch hash bị TỪ CHỐI (EVIDENCE_NOT_INTACT): phải qua reattest-legacy-qa.py (cần chủ duyệt) trước.
  3. Không nằm trong lease writer nào, không có draft cùng slug/article_id.
  4. Dạng lỗi ĐÃ BIẾT: expected_url == canonical_url == `/<cm>/YYYY/MM/DD/<slug>/` và permalink thật là MỘT TRONG HAI dạng
     `/<cm>/YYYY-MM-DD/<slug>/` | `/<cm>/YYYY-MM-DD-<slug>/` của cùng ngày/slug. Dạng khác bị từ chối (MATRIX_URL_UNKNOWN_SHAPE), không đoán.
  5. Permalink thật là của đúng bài này (không hàng matrix nào khác, không bài nào khác, không trang chuyển hướng nào dùng URL đó).
  6. Chấm điểm ĐỘC LẬP trên cùng byte bài + hàng mới bằng scorer canonical (sàn cứng 75/70): PASS, business_fact PASS, legal PASS|NOT_REQUIRED,
     không critical_failure và KHÔNG tiêu chí nào đạt ở bản cũ lại rớt ở bản mới.
  7. Có chủ duyệt (`--approval-ref` bắt buộc, ghi vào provenance) và manifest do `plan` lập.

Kết quả ghi cho mỗi ID được duyệt:
  * `data/content-matrix.csv`: đúng 2 cột expected_url/canonical_url của hàng đó (hàng khác và cột khác byte-exact);
  * `data/qa/<ID>.json`: đầu ra scorer MỚI + khối `revision` kind=matrix-url-sync (chuỗi history nếu từng sửa); scored_at/published_at GIỮ mốc gốc;
  * `reports/qa-audit/matrix-sync/<batch>.json`: sao lưu byte-exact (evidence + hàng matrix cũ), ghi và đọc lại TRƯỚC khi sửa gì.
Không đụng `_posts/`, `redirects/`, registry hay URL live.

Rào do TOOL tự giữ: sàn 75/70 cứng, lô <= 50 ID, mọi tệp kiểm CAS trước khi ghi, apply lỗi giữa chừng tự trả về byte cũ, `verify` chấm lại độc lập
từng ID, `rollback` chỉ khôi phục khi tệp còn đúng bản đã ghi. `plan`/`apply` TỪ CHỐI khi cây làm việc khác HEAD.

Lệnh:
  plan     --ids A,B [--out FILE] [--allow-dirty]                    chấm điểm đề xuất (không ghi gì)
  apply    --manifest FILE --approval-ref TEXT --ids A,B [--batch-id ID] [--dry-run] [--skip-ineligible]
  verify   --backup FILE [--no-rescore]
  rollback --backup FILE [--ids A,B] [--dry-run]
"""
import argparse
import collections
import copy
import datetime
import importlib.util
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _load('migrate_for_sync', 'migrate-slug-urls.py')     # ctx/matrix/atomic_write dùng chung, không viết lại
R, A, SR = M.R, M.A, M.SR
Refuse = R.Refuse
sha, now_iso, atomic_write = R.sha, R.now_iso, R.atomic_write

MANIFEST_SCHEMA = 'matrix-sync-manifest/1'
BACKUP_SCHEMA = 'matrix-sync-backup/1'
BACKUP_DIR = 'reports/qa-audit/matrix-sync'
ELIGIBLE = 'ELIGIBLE_PROPOSAL_AWAITING_OWNER_APPROVAL'
MAX_BATCH = 50
MATRIX_REL = M.MATRIX_REL
KIND = 'matrix-url-sync'
SYNC_COLS = ('expected_url', 'canonical_url')
TOOL_REL = 'scripts/factory/sync-matrix-urls.py'
SKIPPABLE = ('NOT_PUBLISHED', 'POST_CHANGED_SINCE_PLAN', 'EVIDENCE_CHANGED_SINCE_PLAN', 'INPUT_CHANGED_SINCE_PLAN',
             'EVIDENCE_NOT_INTACT', 'LEASED', 'HAS_DRAFT', 'FRESH_QA_NOT_ELIGIBLE', 'REGRESSION', 'NO_DRIFT',
             'IN_BASELINE', 'IN_REGISTRY', 'MATRIX_URL_UNKNOWN_SHAPE', 'URL_COLLISION')

MATRIX_DATE_RE = re.compile(r'^/(?P<cat>[a-z0-9][a-z0-9-]*)/(?P<y>\d{4})/(?P<m>\d{2})/(?P<d>\d{2})/(?P<slug>[a-z0-9][a-z0-9-]*)/\Z')
PERMALINK_SHAPE_RE = re.compile(r'^/[a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9-]*)+/\Z')
FRONT_PERMALINK_RE = re.compile(r'^permalink: (\S+)[ \t]*$', re.M)


def real_shapes(matrix_url):
    """Hai dạng permalink thật có thể ứng với một URL matrix dạng `/<cm>/YYYY/MM/DD/<slug>/`; () nếu không đúng dạng lỗi đã biết."""
    m = MATRIX_DATE_RE.match(matrix_url or '')
    if not m:
        return ()
    date = '%s-%s-%s' % (m.group('y'), m.group('m'), m.group('d'))
    return ('/%s/%s/%s/' % (m.group('cat'), date, m.group('slug')), '/%s/%s-%s/' % (m.group('cat'), date, m.group('slug')))


# ------------------------------------------------------------------ ngữ cảnh

def make_ctx(root, approval_ref='', batch_id=None, purpose='', reason=''):
    ctx = M.make_ctx(root, approval_ref, batch_id, purpose, reason)
    ctx.permalinks = None
    return ctx


def code_sha(ctx):
    return {**ctx.code_sha, 'sync_tool_sha256': sha(pathlib.Path(__file__).read_bytes()),
            'migrate_tool_sha256': sha((HERE / 'migrate-slug-urls.py').read_bytes())}


def permalink_index(ctx):
    """{permalink: [đường dẫn bài]} của MỌI bài trong _posts (đọc đúng dòng permalink của front matter)."""
    if getattr(ctx, 'permalinks', None) is None:
        idx = collections.defaultdict(list)
        for p in sorted((ctx.root / '_posts').glob('*.md')):
            fm = R.FM_RE.match(p.read_text(encoding='utf-8', errors='replace'))
            if not fm:
                continue
            for m in FRONT_PERMALINK_RE.finditer(fm.group(1)):
                idx[m.group(1)].append(str(p.relative_to(ctx.root)))
        ctx.permalinks = idx
    return ctx.permalinks


class Derived:
    __slots__ = ('aid', 'old_row', 'new_row', 'path', 'permalink', 'old_url', 'post', 'old_ev_bytes', 'old_ev', 'before', 'after')


def derive(ctx, aid, extra=None, score=True):
    """Đánh giá đầy đủ MỘT ID (thuần đọc). `extra` = {id: hàng mới} của các ID khác cùng lô (corpus chấm điểm cuối).
    score=False: chỉ dựng ứng viên (mọi kiểm tra cấu trúc/va chạm, KHÔNG chấm điểm)."""
    extra = extra or {}
    if not isinstance(aid, str) or not R.AID_RE.match(aid):
        raise Refuse('BAD_ID', 'ID sai dinh dang: %r' % (aid,))
    if aid in ctx.baseline:
        raise Refuse('IN_BASELINE', '%s thuoc baseline slug d->d: hang matrix duoc migrate-slug-urls.py sua cung luc doi URL' % aid)
    if aid in ctx.registry:
        raise Refuse('IN_REGISTRY', '%s da co trong registry di tru slug' % aid)
    row = ctx.by_id.get(aid)
    if row is None or row['status'] != 'PUBLISHED':
        raise Refuse('NOT_PUBLISHED', '%s khong phai hang PUBLISHED' % aid)
    path = row.get('output_path') or ''
    if not R.POST_RE.match(path):
        raise Refuse('BAD_OUTPUT_PATH', '%s: output_path %r khong nam trong _posts/' % (aid, path))
    if aid in R.lease_ids(ctx.root):
        raise Refuse('LEASED', '%s nam trong lease writer — khong sua matrix' % aid)
    if R.draft_exists(ctx.root, row):
        raise Refuse('HAS_DRAFT', '%s co draft cung slug/article_id — khong sua matrix' % aid)
    ev_path = ctx.root / 'data/qa' / (aid + '.json')
    if not ev_path.is_file():
        raise Refuse('NO_EVIDENCE', '%s khong co evidence' % aid)
    old_ev_bytes = ev_path.read_bytes()
    old_ev = json.loads(old_ev_bytes)
    post_path = ctx.root / path
    if not post_path.is_file():
        raise Refuse('NO_POST', '%s: khong co file bai %s' % (aid, path))
    post = post_path.read_bytes()
    if not (sha(post) == old_ev.get('content_sha256') and A.fingerprint(row) == old_ev.get('matrix_row_sha256')
            and old_ev.get('article_id') == aid and old_ev.get('source_path') == path and old_ev.get('result') == 'PASS'):
        raise Refuse('EVIDENCE_NOT_INTACT',
                     '%s: evidence khong khop byte bai/hang matrix hien tai (hash lech, source_path, result) — '
                     'xu ly bang reattest-legacy-qa.py (chu duyet) truoc, khong sua matrix' % aid)
    permalink = M.front_permalink(M.read_text_exact(post))
    if not PERMALINK_SHAPE_RE.match(permalink):
        raise Refuse('BAD_URL_SHAPE', '%s: permalink %r khong dung dang /<cm>/.../' % (aid, permalink))
    last, slug = permalink.rstrip('/').rsplit('/', 1)[1], row['slug']
    if not (last == slug or last.endswith('-' + slug)):
        raise Refuse('BAD_URL_SHAPE', '%s: permalink %s khong ket thuc bang slug %r cua hang matrix' % (aid, permalink, slug))
    old_url = row['expected_url']
    if old_url != row['canonical_url']:
        raise Refuse('MATRIX_URL_INCONSISTENT', '%s: expected_url != canonical_url trong matrix' % aid)
    if old_url == permalink:
        raise Refuse('NO_DRIFT', '%s: matrix da khop permalink that %s' % (aid, permalink))
    if permalink not in real_shapes(old_url):
        raise Refuse('MATRIX_URL_UNKNOWN_SHAPE',
                     '%s: URL matrix %s va permalink %s khong phai dang loi da biet (/cm/YYYY/MM/DD/slug/ -> /cm/YYYY-MM-DD[/|-]slug/) — khong doan'
                     % (aid, old_url, permalink))
    owners = [p for p in permalink_index(ctx).get(permalink, []) if p != path]
    if owners:
        raise Refuse('URL_COLLISION', '%s: permalink %s con la cua bai khac %s' % (aid, permalink, owners[0]))
    for r in (extra.get(r['id'], r) for r in ctx.rows if r['id'] != aid):
        if permalink in (r.get('expected_url'), r.get('canonical_url')):
            raise Refuse('URL_COLLISION', '%s: permalink %s trung hang matrix %s' % (aid, permalink, r['id']))
    for reg in ctx.registry.values():
        if permalink in (reg['old_url'], reg['new_url']):
            raise Refuse('URL_COLLISION', '%s: permalink %s trung registry %s' % (aid, permalink, reg['article_id']))
    new_row = dict(row, expected_url=permalink, canonical_url=permalink)
    d = Derived()
    d.aid, d.old_row, d.new_row, d.path, d.permalink, d.old_url = aid, row, new_row, path, permalink, old_url
    d.post, d.old_ev_bytes, d.old_ev, d.before, d.after = post, old_ev_bytes, old_ev, None, None
    if not score:
        return d
    final_rows = [(extra[r['id']] if r['id'] != aid and r['id'] in extra else (new_row if r['id'] == aid else r))
                  for r in ctx.rows]
    before = R.score_candidate(ctx, row, post)
    ctx2 = copy.copy(ctx)
    ctx2.rows = final_rows
    after = R.score_candidate(ctx2, new_row, post)
    if (after.get('content_sha256') != sha(post) or after.get('matrix_row_sha256') != A.fingerprint(new_row)
            or after.get('article_id') != aid or after.get('source_path') != path):
        raise Refuse('FRESH_QA_UNBOUND', '%s: diem cham khong buoc dung byte/hang ung vien' % aid)
    if not R.score_ok(after):
        failed = sorted(k for k, v in after.get('checks', {}).items() if not v)
        raise Refuse('FRESH_QA_NOT_ELIGIBLE', '%s: cham lai doc lap = %s q=%s s=%s (failed_checks=%s) — giu nguyen matrix'
                     % (aid, after.get('result'), after.get('quality'), after.get('seo'), failed), failed_checks=failed)
    flipped = sorted(k for k, v in before.get('checks', {}).items() if v and not after.get('checks', {}).get(k))
    if flipped or after['quality'] < before.get('quality', 0) or after['seo'] < before.get('seo', 0):
        raise Refuse('REGRESSION', '%s: dong bo matrix lam tut tieu chi %s hoac diem (q %s->%s, s %s->%s)'
                     % (aid, flipped, before.get('quality'), after['quality'], before.get('seo'), after['seo']), flipped=flipped)
    d.before, d.after = before, after
    return d


def entry_of(d):
    return {'id': d.aid, 'decision': ELIGIBLE, 'permalink': d.permalink, 'old_matrix_url': d.old_url, 'path': d.path,
            'base_post_sha256': sha(d.post), 'old_evidence_sha256': sha(d.old_ev_bytes),
            'old_row_fingerprint': A.fingerprint(d.old_row), 'new_row_fingerprint': A.fingerprint(d.new_row),
            'before': R.summary(d.before), 'after': R.summary(d.after)}


def build_new_evidence(ctx, d, old_evidence_sha256):
    old_ev = d.old_ev
    if not old_ev.get('scored_at'):
        raise Refuse('NO_HISTORICAL_SCORED_AT', '%s: evidence cu khong co scored_at lich su de giu' % d.aid)
    new = copy.deepcopy(d.after)
    for k in ('scored_at', 'published_at'):               # mốc lịch sử: giữ nguyên (watchdog đọc như tín hiệu hoạt động)
        if old_ev.get(k):
            new[k] = old_ev[k]
    for k, v in old_ev.items():                            # chú thích lịch sử (reattestation,...): giữ nguyên
        if k not in new and k != 'revision':
            new[k] = copy.deepcopy(v)
    history = []
    prev = old_ev.get('revision')
    if isinstance(prev, dict):
        history = list(prev.get('history') or []) + [{k: v for k, v in prev.items() if k != 'history'}]
    new['revision'] = {
        'schema': 'revision/1', 'kind': KIND, 'purpose': ctx.purpose, 'reason': ctx.reason,
        'approval_ref': ctx.approval_ref, 'batch_id': ctx.batch_id, 'revised_at': now_iso(),
        'previous_evidence_sha256': old_evidence_sha256,
        'previous_content_sha256': old_ev['content_sha256'], 'previous_matrix_row_sha256': old_ev['matrix_row_sha256'],
        'new_content_sha256': new['content_sha256'], 'new_matrix_row_sha256': new['matrix_row_sha256'],
        'permalink': d.permalink, 'old_matrix_url': d.old_url, 'new_matrix_url': d.permalink,
        'previous_scores': {k: old_ev.get(k) for k in ('quality', 'seo', 'grade')},
        'scorer': new.get('scorer'), 'thresholds': {'quality_min': ctx.op.QUALITY_MIN, 'seo_min': ctx.op.SEO_MIN},
        'tool': TOOL_REL, 'tool_commit': ctx.tool_commit, **code_sha(ctx),
        'note': ('chi doi 2 cot expected_url/canonical_url cua hang matrix cho khop permalink that; bai, permalink va URL live giu nguyen '
                 'tung byte; scored_at/published_at o cap tren giu moc lich su goc; cham diem doc lap luc revised_at'),
    }
    if history:
        new['revision']['history'] = history
    return new


# ------------------------------------------------------------------ plan

def make_plan(ctx, ids):
    ids = sorted(set(ids))
    if not ids:
        raise Refuse('NO_IDS', 'plan can --ids (khong quet ca matrix)')
    stage1 = {}
    entries, excluded = {}, collections.defaultdict(list)
    for aid in ids:                                         # pass 1: hàng mới của cả lô (corpus chấm điểm cuối)
        try:
            stage1[aid] = derive(ctx, aid, score=False).new_row
        except Refuse as e:
            entries[aid] = {'id': aid, 'decision': e.code, 'reason': e.msg}
            excluded[e.code].append(aid)
    for aid in sorted(stage1):
        try:
            entries[aid] = entry_of(derive(ctx, aid, {k: v for k, v in stage1.items() if k != aid}))
        except Refuse as e:
            entries[aid] = {'id': aid, 'decision': e.code, 'reason': e.msg}
            excluded[e.code].append(aid)
    eligible = sorted(i for i, e in entries.items() if e['decision'] == ELIGIBLE)
    return {
        'schema': MANIFEST_SCHEMA,
        'authority': 'PROPOSAL ONLY — apply kiem lai moi dieu kien tu git + byte hien tai',
        'head': ctx.head, 'head_bound': True,
        'matrix_sha256': sha((ctx.root / MATRIX_REL).read_bytes()),
        'thresholds': {'quality_min': ctx.op.QUALITY_MIN, 'seo_min': ctx.op.SEO_MIN},
        **code_sha(ctx),
        'counts': {'planned': len(entries), 'eligible': len(eligible),
                   'decisions': dict(collections.Counter(e['decision'] for e in entries.values()))},
        'eligible': eligible,
        'excluded': {k: sorted(v) for k, v in sorted(excluded.items())},
        'entries': entries,
    }


def check_manifest(manifest):
    if manifest.get('schema') != MANIFEST_SCHEMA:
        raise Refuse('BAD_MANIFEST', 'schema manifest khong dung')
    if not isinstance(manifest.get('entries'), dict) or not isinstance(manifest.get('eligible'), list):
        raise Refuse('BAD_MANIFEST', 'manifest thieu entries/eligible')
    if manifest.get('head_bound') is not True:
        raise Refuse('MANIFEST_NOT_HEAD_BOUND', 'manifest khong gan voi mot commit sach — chay lai plan tren cay sach')


def check_manifest_current(ctx, manifest):
    for k in ('scorer_code_sha256', 'business_facts_sha256', 'taxonomy_sha256'):
        if manifest.get(k) != ctx.code_sha.get(k):
            raise Refuse('SCORER_CHANGED_SINCE_PLAN', '%s khac manifest (scorer/facts/taxonomy da doi) — chay lai plan' % k)
    if manifest.get('thresholds') != {'quality_min': ctx.op.QUALITY_MIN, 'seo_min': ctx.op.SEO_MIN}:
        raise Refuse('SCORER_CHANGED_SINCE_PLAN', 'nguong QA khac manifest — chay lai plan')


# ------------------------------------------------------------------ apply

def prepare(ctx, manifest, aid, extra):
    e = manifest['entries'].get(aid)
    if e is None or aid not in manifest['eligible'] or e.get('decision') != ELIGIBLE:
        raise Refuse('NOT_ELIGIBLE', '%s khong thuoc danh sach du dieu kien cua manifest' % aid)
    row = ctx.by_id.get(aid)
    if row is None or row['status'] != 'PUBLISHED':
        raise Refuse('NOT_PUBLISHED', '%s khong phai hang PUBLISHED' % aid)
    post_p = ctx.root / row['output_path']
    if not post_p.is_file() or sha(post_p.read_bytes()) != e['base_post_sha256']:
        raise Refuse('POST_CHANGED_SINCE_PLAN', '%s: bai da doi tu luc plan' % aid)
    ev_p = ctx.root / 'data/qa' / (aid + '.json')
    if not ev_p.is_file() or sha(ev_p.read_bytes()) != e['old_evidence_sha256']:
        raise Refuse('EVIDENCE_CHANGED_SINCE_PLAN', '%s: evidence da doi tu luc plan' % aid)
    d = derive(ctx, aid, extra)
    if (sha(d.old_ev_bytes) != e['old_evidence_sha256'] or A.fingerprint(d.old_row) != e['old_row_fingerprint']
            or A.fingerprint(d.new_row) != e['new_row_fingerprint'] or d.permalink != e['permalink']
            or R.summary(d.after) != e['after']):
        raise Refuse('INPUT_CHANGED_SINCE_PLAN', '%s: byte/hang/diem ung vien khac manifest' % aid)
    return d


def apply_batch(ctx, manifest, ids, dry_run=False, skip_ineligible=False):
    if not (ctx.approval_ref or '').strip():
        raise Refuse('NO_APPROVAL', '--approval-ref la bat buoc (ghi vao provenance)')
    check_manifest(manifest)
    check_manifest_current(ctx, manifest)
    ids = sorted(set(ids))
    if not ids:
        raise Refuse('NO_IDS', 'khong co ID nao duoc chon')
    if len(ids) > MAX_BATCH:
        raise Refuse('BATCH_TOO_LARGE', 'toi da %d ID/lo' % MAX_BATCH)
    if ctx.batch_id is not None and not R.BATCH_ID_RE.match(ctx.batch_id):
        raise Refuse('BAD_BATCH_ID', 'batch-id chi gom A-Za-z0-9._- (toi da 80 ky tu)')
    if not ctx.batch_id:
        ctx.batch_id = 'matrix-sync-%s-%s-%s' % (datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d'), ids[0], ids[-1])
    ctx.purpose = 'matrix-url-sync'
    ctx.reason = ('Dong bo expected_url/canonical_url cua hang matrix voi permalink that cua bai da xuat ban '
                  '(matrix ghi /cm/YYYY/MM/DD/slug/, URL live la /cm/YYYY-MM-DD[/|-]slug/); khong doi permalink/bai/URL live. Issue #77.')
    stage1, ineligible = {}, []
    for aid in ids:
        try:
            e = manifest['entries'].get(aid)
            if e is None or aid not in manifest['eligible'] or e.get('decision') != ELIGIBLE:
                raise Refuse('NOT_ELIGIBLE', '%s khong thuoc danh sach du dieu kien cua manifest' % aid)
            stage1[aid] = derive(ctx, aid, score=False).new_row
        except Refuse as e:
            if skip_ineligible and e.code in SKIPPABLE:
                ineligible.append({'id': aid, 'code': e.code, 'reason': e.msg})
                continue
            raise
    prepared = []
    for aid in sorted(stage1):
        try:
            prepared.append(prepare(ctx, manifest, aid, {k: v for k, v in stage1.items() if k != aid}))
        except Refuse as e:
            if skip_ineligible and e.code in SKIPPABLE:
                ineligible.append({'id': aid, 'code': e.code, 'reason': e.msg})
                continue
            raise
    report = {'ok': True, 'batch_id': ctx.batch_id, 'dry_run': dry_run,
              'would_write' if dry_run else 'written': [d.aid for d in prepared], 'skipped_ineligible': ineligible}
    if dry_run or not prepared:
        return report
    if ctx.guard:
        ctx.guard()
    root = ctx.root
    backup_rel = '%s/%s.json' % (BACKUP_DIR, ctx.batch_id)
    backup_path = root / backup_rel
    if backup_path.parent.resolve() != (root / BACKUP_DIR).resolve():
        raise Refuse('BAD_BATCH_ID', 'sao luu phai nam truc tiep trong %s' % BACKUP_DIR)
    if backup_path.exists():
        raise Refuse('BATCH_EXISTS', 'sao luu %s da ton tai — dung batch-id khac' % backup_rel)
    matrix_old = (root / MATRIX_REL).read_bytes()
    M.matrix_bytes_with(root, {})                         # CSV round-trip byte-exact TRƯỚC khi thay hàng
    matrix_new = M.matrix_bytes_with(root, {d.aid: d.new_row for d in prepared})
    backup = {'schema': BACKUP_SCHEMA, 'batch_id': ctx.batch_id, 'created_at': now_iso(), 'approval_ref': ctx.approval_ref,
              'purpose': ctx.purpose, 'reason': ctx.reason, 'head_at_apply': ctx.head, 'tool_commit': ctx.tool_commit,
              'manifest_sha256': sha(R.doc_text(manifest).encode('utf-8')),
              'matrix_old_sha256': sha(matrix_old), 'matrix_new_sha256': sha(matrix_new), 'entries': {}}
    blobs = {}
    for d in prepared:
        new_ev_bytes = R.evidence_text(build_new_evidence(ctx, d, sha(d.old_ev_bytes))).encode('utf-8')
        blobs[d.aid] = new_ev_bytes
        backup['entries'][d.aid] = {
            'post_path': d.path, 'post_sha256': sha(d.post), 'permalink': d.permalink, 'old_matrix_url': d.old_url,
            'old_evidence_text': d.old_ev_bytes.decode('utf-8'), 'old_evidence_sha256': sha(d.old_ev_bytes),
            'new_evidence_sha256': sha(new_ev_bytes), 'old_row': d.old_row, 'new_row': d.new_row}
    atomic_write(backup_path, R.doc_text(backup).encode('utf-8'))
    if json.loads(backup_path.read_text(encoding='utf-8')) != json.loads(R.doc_text(backup)):
        backup_path.unlink()
        raise Refuse('BACKUP_READBACK_FAILED', 'doc lai sao luu khong khop — chua sua file nao')
    attempted = []
    try:
        for d in prepared:
            ev_p, post_p = root / 'data/qa' / (d.aid + '.json'), root / d.path
            if ev_p.read_bytes() != d.old_ev_bytes or post_p.read_bytes() != d.post:
                raise Refuse('FILES_CHANGED_DURING_APPLY', '%s: bai/evidence doi trong luc apply' % d.aid)
            attempted.append(d.aid)                        # TRƯỚC khi ghi
            atomic_write(ev_p, blobs[d.aid])
            if sha(ev_p.read_bytes()) != sha(blobs[d.aid]):
                raise Refuse('WRITE_MISMATCH', '%s: doc lai khong khop' % d.aid)
        if (root / MATRIX_REL).read_bytes() != matrix_old:
            raise Refuse('FILES_CHANGED_DURING_APPLY', 'matrix doi trong luc apply')
        attempted.append('__shared__')
        atomic_write(root / MATRIX_REL, matrix_new)
        ctx2 = make_ctx(root, ctx.approval_ref, ctx.batch_id, ctx.purpose, ctx.reason)
        problems = verify_backup(ctx2, backup, rescore=True)
        if problems:
            raise Refuse('POST_VERIFY_FAILED', '; '.join(problems[:5]), problems=problems)
    except BaseException as exc:
        _abort_apply(ctx, backup, backup_path, exc, attempted, matrix_old)
        raise
    report['backup'] = backup_rel
    return report


def _abort_apply(ctx, backup, backup_path, exc, attempted, matrix_old):
    """Apply lỗi giữa chừng: trả MỌI thứ lần chạy này đã bắt đầu ghi về byte cũ; chỉ xóa sao lưu khi mọi thứ đã về."""
    root = ctx.root
    try:
        if '__shared__' in attempted:
            atomic_write(root / MATRIX_REL, matrix_old)
        for aid in (a for a in attempted if a != '__shared__'):
            atomic_write(root / 'data/qa' / (aid + '.json'), backup['entries'][aid]['old_evidence_text'].encode('utf-8'))
    except BaseException:
        pass
    left = [aid for aid in sorted(a for a in attempted if a != '__shared__')
            if sha((root / 'data/qa' / (aid + '.json')).read_bytes()) != backup['entries'][aid]['old_evidence_sha256']]
    if (root / MATRIX_REL).read_bytes() != matrix_old:
        left.append('__shared__')
    if left:
        raise Refuse('PARTIAL_APPLY_BACKUP_KEPT',
                     'apply loi (%s: %s) va chua ve byte cu: %s — GIU sao luu %s, khoi phuc bang `rollback --backup`'
                     % (type(exc).__name__, exc, ', '.join(left[:5]), backup_path.name), left=left) from exc
    backup_path.unlink()


# ------------------------------------------------------------------ verify / rollback

def check_backup_shape(backup):
    if backup.get('schema') != BACKUP_SCHEMA:
        raise Refuse('BAD_BACKUP', 'schema sao luu khong dung')
    if not isinstance(backup.get('entries'), dict) or not backup['entries']:
        raise Refuse('BAD_BACKUP', 'sao luu khong co entries')
    for aid, b in backup['entries'].items():
        if not R.AID_RE.match(aid) or not isinstance(b, dict):
            raise Refuse('BAD_BACKUP', 'khoa entries %r khong hop le' % (aid,))
        if not isinstance(b.get('post_path'), str) or not R.POST_RE.match(b['post_path']):
            raise Refuse('BAD_BACKUP', '%s: post_path khong nam trong _posts/' % aid)
        for k in ('post_sha256', 'permalink', 'old_matrix_url', 'old_evidence_text', 'old_evidence_sha256', 'new_evidence_sha256'):
            if not isinstance(b.get(k), str):
                raise Refuse('BAD_BACKUP', '%s: thieu %s' % (aid, k))
        if not isinstance(b.get('old_row'), dict) or not isinstance(b.get('new_row'), dict):
            raise Refuse('BAD_BACKUP', '%s: thieu old_row/new_row' % aid)
        if {k: v for k, v in b['old_row'].items() if k not in SYNC_COLS} != {k: v for k, v in b['new_row'].items() if k not in SYNC_COLS}:
            raise Refuse('BAD_BACKUP', '%s: old_row/new_row khac nhau o cot ngoai %s' % (aid, SYNC_COLS))


def verify_backup(ctx, backup, rescore=True):
    """Kiểm trạng thái ĐÃ GHI so với sao lưu + chấm lại ĐỘC LẬP. Trả danh sách lỗi."""
    check_backup_shape(backup)
    problems = []
    root = ctx.root
    for aid, b in sorted(backup['entries'].items()):
        post_p, ev_p = root / b['post_path'], root / 'data/qa' / (aid + '.json')
        if not post_p.is_file() or not ev_p.is_file():
            problems.append('%s: thieu bai hoac evidence' % aid)
            continue
        post_raw, ev_raw = post_p.read_bytes(), ev_p.read_bytes()
        if sha(post_raw) != b['post_sha256']:
            problems.append('%s: bai khac ban luc apply (cong cu nay khong duoc doi bai)' % aid)
            continue
        if sha(ev_raw) != b['new_evidence_sha256']:
            problems.append('%s: evidence khac ban da ghi' % aid)
            continue
        if sha(b['old_evidence_text'].encode('utf-8')) != b['old_evidence_sha256']:
            problems.append('%s: sao luu evidence cu hong (sha khong khop)' % aid)
            continue
        ev, old_ev = json.loads(ev_raw), json.loads(b['old_evidence_text'])
        row = ctx.by_id.get(aid)
        if row is None or row['status'] != 'PUBLISHED' or row.get('output_path') != b['post_path']:
            problems.append('%s: khong con PUBLISHED / output_path khac' % aid)
            continue
        if row != b['new_row']:
            problems.append('%s: hang matrix khac ban da ghi' % aid)
        if {k: v for k, v in b['old_row'].items() if k not in SYNC_COLS} != {k: v for k, v in row.items() if k not in SYNC_COLS}:
            problems.append('%s: hang matrix doi o cot ngoai %s so voi hang cu' % (aid, SYNC_COLS))
        if row['expected_url'] != b['permalink'] or row['canonical_url'] != b['permalink']:
            problems.append('%s: matrix chua khop permalink that %s' % (aid, b['permalink']))
        if M.front_permalink(post_raw.decode('utf-8')) != b['permalink']:
            problems.append('%s: permalink trong bai khac permalink da ghi nhan' % aid)
        if ev.get('content_sha256') != sha(post_raw):
            problems.append('%s: content_sha256 khong khop bai hien tai' % aid)
        if ev.get('matrix_row_sha256') != A.fingerprint(row):
            problems.append('%s: matrix_row_sha256 khong khop hang hien tai' % aid)
        if ev.get('source_path') != row['output_path'] or ev.get('article_id') != aid:
            problems.append('%s: source_path/article_id trong evidence sai' % aid)
        if not R.score_ok(ev):
            problems.append('%s: diem/cong QA khong dat nguong' % aid)
        rev = ev.get('revision') or {}
        if (b['old_evidence_sha256'] != sha(b['old_evidence_text'].encode('utf-8')) or rev.get('kind') != KIND
                or rev.get('previous_evidence_sha256') != b['old_evidence_sha256']
                or rev.get('previous_content_sha256') != old_ev.get('content_sha256')
                or rev.get('previous_matrix_row_sha256') != old_ev.get('matrix_row_sha256')
                or rev.get('new_content_sha256') != ev.get('content_sha256')
                or (rev.get('old_matrix_url'), rev.get('new_matrix_url')) != (b['old_matrix_url'], b['permalink'])
                or not (rev.get('approval_ref') or '').strip()):
            problems.append('%s: provenance khong khop sao luu' % aid)
        for k in ('scored_at', 'published_at'):
            if old_ev.get(k) and ev.get(k) != old_ev.get(k):
                problems.append('%s: %s lich su khong duoc giu nguyen' % (aid, k))
        lost = sorted(k for k in old_ev if k not in ev and k != 'revision')
        if lost:
            problems.append('%s: mat chu thich lich su cua evidence cu: %s' % (aid, ', '.join(lost[:5])))
        if rescore:
            diff = R.score_diff(ev, R.score_candidate(ctx, row, post_raw))
            if diff:
                problems.append('%s: diem trong evidence khac diem cham lai doc lap (%s)' % (aid, ', '.join(diff[:6])))
    return problems


def rollback_backup(root, backup, ids=None, dry_run=False, force=False):
    """Khôi phục byte-exact: evidence cũ + hàng matrix cũ. Mỗi mục chỉ được khôi phục khi evidence VÀ hàng matrix còn đúng bản ĐÃ GHI
    (không đè thay đổi của người khác). Kiểm TOÀN BỘ điều kiện trước khi ghi; chạy lại sau một lần bị ngắt vẫn hoàn tất."""
    check_backup_shape(backup)
    root = pathlib.Path(root)
    if ids is not None:
        unknown = sorted(set(ids) - set(backup['entries']))
        if unknown:
            raise Refuse('UNKNOWN_IDS', 'ID khong co trong sao luu: %s' % unknown[:5])
    cur = {r['id']: r for r in SR.read_csv_rows(root / MATRIX_REL)}
    out = {'restored': [], 'skipped_changed_since_apply': [], 'dry_run': dry_run}
    plan = []                                                # (aid, b, bytes evidence cũ, đường dẫn evidence, ghi evidence?, ghi hàng matrix?)
    for aid, b in sorted(backup['entries'].items()):
        if ids is not None and aid not in ids:
            continue
        old_ev = b['old_evidence_text'].encode('utf-8')
        if sha(old_ev) != b['old_evidence_sha256']:
            raise Refuse('BACKUP_CORRUPT', '%s: sao luu hong' % aid)
        ev_p = root / 'data/qa' / (aid + '.json')
        ev_sha = sha(ev_p.read_bytes()) if ev_p.is_file() else None
        row = cur.get(aid)
        ev_state = 'new' if ev_sha == b['new_evidence_sha256'] else 'old' if ev_sha == b['old_evidence_sha256'] else 'other'
        row_state = 'new' if row == b['new_row'] else 'old' if row == b['old_row'] else 'other'
        if ev_state == 'old' and row_state == 'old':
            continue                                         # đã ở bản gốc
        if not force and 'other' in (ev_state, row_state):   # 'old'+'new' lẫn lộn = lần rollback trước bị ngắt: chạy lại hoàn tất
            out['skipped_changed_since_apply'].append(aid)
            continue
        post_p = root / b['post_path']
        if not post_p.is_file() or sha(post_p.read_bytes()) != b['post_sha256']:
            raise Refuse('POST_CHANGED_SINCE_APPLY', '%s: bai da doi sau apply — khong khoi phuc evidence cu (chua ghi gi)' % aid)
        plan.append((aid, b, old_ev, ev_p, ev_state != 'old', row_state != 'old'))
        out['restored'].append(aid)
    if dry_run:
        return out
    for aid, b, old_ev, ev_p, write_ev, _ in plan:
        if write_ev:
            atomic_write(ev_p, old_ev)
        if sha(ev_p.read_bytes()) != b['old_evidence_sha256']:
            raise Refuse('ROLLBACK_MISMATCH', '%s: khoi phuc khong khop' % aid)
    rows = {aid: b['old_row'] for aid, b, _, _, _, write_row in plan if write_row}
    if rows:
        atomic_write(root / MATRIX_REL, M._matrix_restore_bytes(root, rows))
    out['ok'] = True
    return out


# ------------------------------------------------------------------ CLI

def _ids(v):
    return [x.strip() for x in (v or '').split(',') if x.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--out')
    p.add_argument('--ids', default='')
    p.add_argument('--allow-dirty', action='store_true')
    a_ = sub.add_parser('apply')
    a_.add_argument('--manifest', required=True)
    a_.add_argument('--approval-ref', default='')
    a_.add_argument('--ids', default='')
    a_.add_argument('--batch-id', default=None)
    a_.add_argument('--dry-run', action='store_true')
    a_.add_argument('--skip-ineligible', action='store_true')
    v = sub.add_parser('verify')
    v.add_argument('--backup', required=True)
    v.add_argument('--no-rescore', action='store_true')
    r = sub.add_parser('rollback')
    r.add_argument('--backup', required=True)
    r.add_argument('--ids', default=None)
    r.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'plan':
            dirty = A.dirty_inputs(ROOT)
            if dirty and not a.allow_dirty:
                R.require_clean_tree(ROOT)
            ctx = make_ctx(ROOT)
            manifest = make_plan(ctx, _ids(a.ids))
            manifest['head_bound'] = not dirty
            text = R.doc_text(manifest)
            if a.out:
                atomic_write(os.path.abspath(a.out), text.encode('utf-8'))
                print(json.dumps({'ok': True, 'out': os.path.abspath(a.out), 'counts': manifest['counts'],
                                  'excluded': {k: len(x) for k, x in manifest['excluded'].items()}}, ensure_ascii=False, indent=2))
            else:
                print(text, end='')
            return 0
        if a.cmd == 'apply':
            manifest = json.loads(pathlib.Path(a.manifest).read_text(encoding='utf-8'))
            R.require_clean_tree(ROOT)
            check_manifest(manifest)
            ids = _ids(a.ids)
            if not ids:
                raise Refuse('NO_IDS', 'can --ids')
            ctx = make_ctx(ROOT, a.approval_ref, a.batch_id)
            ctx.guard = lambda: R.require_clean_tree(ROOT)
            print(json.dumps(apply_batch(ctx, manifest, ids, a.dry_run, a.skip_ineligible), ensure_ascii=False, indent=2))
            return 0
        backup = json.loads(pathlib.Path(a.backup).read_text(encoding='utf-8'))
        if a.cmd == 'verify':
            problems = verify_backup(make_ctx(ROOT), backup, rescore=not a.no_rescore)
            print(json.dumps({'ok': not problems, 'checked': len(backup['entries']), 'problems': problems}, ensure_ascii=False, indent=2))
            return 0 if not problems else 1
        ids = None
        if a.ids is not None:
            ids = set(_ids(a.ids))
            if not ids:
                raise Refuse('BAD_IDS', '--ids rong: bo --ids de khoi phuc ca lo')
        out = rollback_backup(ROOT, backup, ids, a.dry_run)
        out['ok'] = not out['skipped_changed_since_apply']
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out['ok'] else 1
    except Refuse as e:
        d = {'ok': False, 'code': e.code, 'error': e.msg}
        d.update(e.extra)
        print(json.dumps(d, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
