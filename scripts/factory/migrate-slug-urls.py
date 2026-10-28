#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Di trú URL bài PUBLISHED có slug thiếu chữ đ (đ -> d) CÓ KIỂM SOÁT, theo lô, có hoàn tác (Issue #77).

Bối cảnh: 1.410 bài đã xuất bản mang slug do slugify lỗi cũ sinh ra ("xe đạp điện" -> "xe-ap-ien"). GitHub Pages không có HTTP 301
theo đường dẫn (bằng chứng runner: server GitHub.com, không có lớp edge), nên chủ repo chọn: URL CŨ = trang HTTP 200 chứa
`<meta http-equiv="refresh" content="0; url=MỚI">` + canonical MỚI (loại khỏi sitemap); URL MỚI = bài thật. Báo cáo luôn gọi đúng tên
"HTTP 200 + meta refresh", KHÔNG gọi là 301. Đổi permalink làm đổi byte bài, hàng matrix và evidence QA nên cần công cụ chính thức
(revise-published.py cấm đổi permalink; reattest-legacy-qa.py chỉ cho ca đổi domain). Công cụ này là đường GHI duy nhất cho thay đổi đó.

Một bài chỉ được di trú khi thỏa MỌI điều kiện (tool tự kiểm từ byte hiện tại, không tin manifest, không có cờ ép):
  1. Thuộc danh sách ĐÓNG BĂNG reports/factory/seo-master/slug-d-baseline.csv; hàng matrix PUBLISHED, slug khớp slug lỗi cũ của tiêu đề
     (`slugify_legacy_without_d(title)`), URL cũ/mới và đường dẫn tệp khớp baseline, chưa có trong registry.
  2. Evidence NGUYÊN VẸN: content_sha256 == byte bài hiện tại, matrix_row_sha256 == vân tay hàng hiện tại, source_path đúng, result PASS.
     Evidence đã lệch hash (migrate domain) bị TỪ CHỐI (EVIDENCE_NOT_INTACT): phải qua reattest-legacy-qa.py (cần chủ duyệt) trước.
  3. Không nằm trong lease writer nào, không có draft cùng slug (cũ hoặc mới) / cùng article_id.
  4. Slug mới = slugkit.slugify(title), KHÔNG trùng slug/URL/đường dẫn của hàng nào khác, tệp mới chưa tồn tại.
  5. Bài mới = bài cũ khác ĐÚNG MỘT dòng front matter (`permalink:` cũ -> mới); thân bài và mọi dòng khác giữ nguyên từng byte.
  6. Chấm điểm ĐỘC LẬP trên byte mới + hàng mới bằng scorer canonical (corpus/taxonomy/business-facts hiện tại, sàn cứng 75/70):
     PASS, business_fact PASS, legal PASS|NOT_REQUIRED, không critical_failure, và KHÔNG tiêu chí nào đạt ở bản cũ lại rớt ở bản mới.
  7. Có chủ duyệt (`--approval-ref` bắt buộc, ghi vào provenance) và manifest do `plan` lập.

Kết quả ghi cho mỗi ID được duyệt:
  * `_posts/<cũ>.md` -> `_posts/<mới>.md` (đổi tên + đổi đúng dòng permalink);
  * `data/qa/<ID>.json`: đầu ra scorer MỚI + khối `revision` kind=permalink-migration (provenance, chuỗi history nếu từng sửa);
    scored_at/published_at GIỮ mốc lịch sử gốc;
  * `data/content-matrix.csv`: đúng 4 cột slug/expected_url/canonical_url/output_path của hàng đó (các hàng khác byte-exact);
  * `redirects/slug-d/<ID>.html`: trang chuyển hướng cho URL cũ (sinh từ registry, không sửa tay);
  * `reports/factory/seo-master/slug-redirect-registry.csv`: thêm dòng MIGRATED;
  * `reports/qa-audit/migrate/<batch>.json`: sao lưu byte-exact (bài + evidence + hàng matrix cũ) ghi và đọc lại TRƯỚC khi sửa gì.

Rào do TOOL tự giữ: sàn 75/70 cứng, lô <= 50 ID, mọi tệp được kiểm CAS trước khi ghi, apply lỗi giữa chừng tự trả mọi thứ về byte cũ,
`verify` chấm lại độc lập từng ID và kiểm trang chuyển hướng/registry, `rollback` chỉ khôi phục khi tệp còn đúng bản đã ghi.
`plan`/`apply` TỪ CHỐI khi cây làm việc khác HEAD. Mỗi lô = một commit rồi mới đến lô sau.

Lệnh:
  plan     [--jobs N] [--out FILE] [--ids A,B] [--allow-dirty]       chấm điểm đề xuất cho baseline (không ghi gì)
  apply    --manifest FILE --approval-ref TEXT (--ids A,B | --limit N [--offset K]) [--batch-id ID] [--dry-run] [--skip-ineligible]
  verify   --backup FILE [--no-rescore]                              kiểm bài/evidence/matrix/registry/trang chuyển hướng + chấm lại
  rollback --backup FILE [--ids A,B] [--dry-run]                     khôi phục byte-exact (chỉ khi còn đúng bản đã ghi)
  refresh-data [--check]                                             làm mới dữ liệu phái sinh theo URL mới (xem refresh_data)
  links-plan   [--mapping FILE] [--from-registry] [--jobs N] --out FILE   (pha 2) bài NGUYÊN VẸN còn liên kết tới URL cũ/thiếu dấu `/`
  links-apply  --manifest FILE --approval-ref TEXT (--ids | --limit/--offset) [--batch-id] [--dry-run]   đổi ĐÚNG đích liên kết, ghi lại evidence
  links-verify --backup FILE [--no-rescore] / links-rollback --backup FILE [--ids] [--dry-run]

Pha 2 (internal link): bài khác trỏ tới URL cũ đã di trú (đang đi qua trang chuyển hướng) được trỏ thẳng tới URL mới. Mỗi bài chỉ đổi ĐÍCH
của liên kết `](ĐÍCH)` / `href="ĐÍCH"` có trong ánh xạ (chữ liên kết, tiêu đề, # đoạn giữ nguyên); phần còn lại của bài giữ nguyên từng byte;
evidence chấm lại độc lập (khối revision kind `link-retarget`); không đụng matrix. Bài evidence đã lệch hash bị TỪ CHỐI như ở pha 1.
"""
import argparse
import collections
import copy
import csv
import datetime
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# scripts/factory/queue.py (script legacy) che module `queue` của stdlib khi thư mục này đứng đầu sys.path
# (multiprocessing import queue): đưa thư mục này xuống CUỐI để stdlib thắng, vẫn import được slugkit/slug_redirects.
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != str(HERE)]
sys.path.append(str(HERE))
import slug_redirects as SR  # noqa: E402
import slugkit  # noqa: E402


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = _load('revise_for_migrate', 'revise-published.py')     # scorer/ctx/atomic_write... dùng chung, không viết lại
A = R.A
Refuse = R.Refuse
sha, now_iso, atomic_write = R.sha, R.now_iso, R.atomic_write

MANIFEST_SCHEMA = 'migrate-manifest/1'
BACKUP_SCHEMA = 'migrate-backup/1'
BACKUP_DIR = 'reports/qa-audit/migrate'
ELIGIBLE = 'ELIGIBLE_PROPOSAL_AWAITING_OWNER_APPROVAL'
MAX_BATCH = 50
MATRIX_REL = 'data/content-matrix.csv'
KIND = 'permalink-migration'
URL_COLS = ('slug', 'expected_url', 'canonical_url', 'output_path')
LEGAL_NOTICES_REL = '_data/legal-notices.json'
LEADS_REL = '_data/seo-leads.yml'
GENERATED_DATA = (('_data/seo-topic-links.json', 'scripts/seo/build-topic-links.py'),
                  ('_data/price-notices.json', 'scripts/seo/build-price-notices.py'))
OUT_PATH_RE = re.compile(r'^_posts/(\d{4}-\d{2}-\d{2})-(.+)\.md\Z')
PERMALINK_RE = re.compile(r'^permalink: (\S+)\Z')
SKIPPABLE = ('NOT_PUBLISHED', 'POST_CHANGED_SINCE_PLAN', 'EVIDENCE_CHANGED_SINCE_PLAN', 'INPUT_CHANGED_SINCE_PLAN',
             'EVIDENCE_NOT_INTACT', 'LEASED', 'HAS_DRAFT', 'FRESH_QA_NOT_ELIGIBLE', 'REGRESSION',
             'SLUG_COLLISION', 'URL_COLLISION', 'PATH_EXISTS', 'ALREADY_MIGRATED')


# ------------------------------------------------------------------ văn bản bài

def read_text_exact(raw):
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        raise Refuse('NOT_UTF8', 'bai khong phai UTF-8')


def front_permalink(text):
    front, _ = R.split_front(text)
    found = [PERMALINK_RE.match(l).group(1) for l in front.split('\n') if PERMALINK_RE.match(l)]
    if len(found) != 1:
        raise Refuse('PERMALINK_LINE', 'front matter phai co DUNG MOT dong `permalink: ...` (co %d)' % len(found))
    return found[0]


def replace_permalink(text, old, new):
    """Đổi ĐÚNG dòng `permalink: <old>` trong front matter; mọi byte khác giữ nguyên."""
    m = R.FM_RE.match(text)
    if not m:
        raise Refuse('NO_FRONT_MATTER', 'bai khong co front matter')
    lines = m.group(1).split('\n')
    idx = [i for i, l in enumerate(lines) if l == 'permalink: ' + old]
    if len(idx) != 1:
        raise Refuse('PERMALINK_LINE', 'khong tim thay dung mot dong permalink: %s' % old)
    lines[idx[0]] = 'permalink: ' + new
    return '---\n' + '\n'.join(lines) + '---\n' + text[m.end():]


def check_only_permalink_changed(old_text, new_text, old, new):
    """Bất biến: bài mới == bài cũ chỉ khác đúng dòng permalink."""
    if replace_permalink(old_text, old, new) != new_text:
        raise Refuse('POST_DIFF_NOT_PERMALINK_ONLY', 'bai moi khac bai cu o noi khac ngoai dong permalink')
    ol, nl = old_text.split('\n'), new_text.split('\n')
    if len(ol) != len(nl) or sum(1 for a, b in zip(ol, nl) if a != b) != 1:
        raise Refuse('POST_DIFF_NOT_PERMALINK_ONLY', 'so dong khac nhau != 1')


# ------------------------------------------------------------------ ngữ cảnh

def make_ctx(root, approval_ref='', batch_id=None, purpose='', reason=''):
    ctx = R.make_ctx(root, approval_ref, batch_id, purpose, reason)
    ctx.op._ROUTES = None                 # route truth tính lại từ cây hiện tại (có trang chuyển hướng của lô trước)
    ctx.registry = {r['article_id']: r for r in SR.load_registry(ctx.root)}
    ctx.baseline = SR.load_baseline(ctx.root)
    return ctx


def code_sha(ctx):
    return {**ctx.code_sha, 'migrate_tool_sha256': sha(pathlib.Path(__file__).read_bytes()),
            'slugkit_sha256': sha((HERE / 'slugkit.py').read_bytes()),
            'baseline_sha256': SR.baseline_sha256(ctx.root)}


class Derived:
    __slots__ = ('aid', 'old_row', 'new_row', 'old_path', 'new_path', 'old_url', 'new_url', 'old_slug', 'new_slug',
                 'old_post', 'new_post', 'old_ev_bytes', 'old_ev', 'before', 'after', 'url_drift', 'entry')


def _collisions(ctx, aid, new_slug, new_url, new_path, extra):
    others = [extra.get(r['id'], r) for r in ctx.rows if r['id'] != aid]
    for r in others:
        if r.get('slug') == new_slug:
            raise Refuse('SLUG_COLLISION', '%s: slug moi %r trung slug cua %s (%s)' % (aid, new_slug, r['id'], r['status']))
        if new_url in (r.get('expected_url'), r.get('canonical_url')):
            raise Refuse('URL_COLLISION', '%s: URL moi %s trung hang %s' % (aid, new_url, r['id']))
        if r.get('output_path') == new_path:
            raise Refuse('PATH_EXISTS', '%s: output_path moi trung hang %s' % (aid, r['id']))
    if new_url in ctx.op.canonical_routes():
        raise Refuse('URL_COLLISION', '%s: URL moi %s da la route cua mot trang' % (aid, new_url))
    if (ctx.root / new_path).exists():
        raise Refuse('PATH_EXISTS', '%s: tep %s da ton tai' % (aid, new_path))


BASELINE_DOUBLE_DATE_RE = re.compile(r'^(_posts/\d{4}-\d{2}-\d{2}-)\d{4}-\d{2}-\d{2}-')


def baseline_new_path(path):
    """Baseline đóng băng ghi tiền tố ngày HAI lần cho 7 bài legacy có ngày trong slug (`_posts/2026-09-29-2026-09-29-<slug>.md`);
    đường dẫn đúng chỉ có một ngày (đúng như tệp bài hiện có). So sánh với bản đã gộp, không sửa baseline (sha256 ghim)."""
    return BASELINE_DOUBLE_DATE_RE.sub(r'\1', path or '')


def derive(ctx, aid, extra=None, score=True):
    """Đánh giá đầy đủ MỘT ID (thuần đọc). `extra` = {id: hàng mới} của các ID khác cùng lô (corpus chấm điểm cuối cùng).
    score=False: chỉ dựng ứng viên (mọi kiểm tra cấu trúc/va chạm, KHÔNG chấm điểm) — dùng để biết hàng mới của cả lô."""
    extra = extra or {}
    if not isinstance(aid, str) or not R.AID_RE.match(aid):
        raise Refuse('BAD_ID', 'ID sai dinh dang: %r' % (aid,))
    base = ctx.baseline.get(aid)
    if base is None:
        raise Refuse('NOT_IN_BASELINE', '%s khong thuoc danh sach dong bang slug-d-baseline.csv' % aid)
    if aid in ctx.registry:
        raise Refuse('ALREADY_MIGRATED', '%s da co trong registry' % aid)
    row = ctx.by_id.get(aid)
    if row is None or row['status'] != 'PUBLISHED':
        raise Refuse('NOT_PUBLISHED', '%s khong phai hang PUBLISHED' % aid)
    old_path = row.get('output_path') or ''
    if not R.POST_RE.match(old_path):
        raise Refuse('BAD_OUTPUT_PATH', '%s: output_path %r khong nam trong _posts/' % (aid, old_path))
    if aid in R.lease_ids(ctx.root):
        raise Refuse('LEASED', '%s nam trong lease writer — khong di tru' % aid)
    if R.draft_exists(ctx.root, row):
        raise Refuse('HAS_DRAFT', '%s co draft cung slug/article_id — khong di tru' % aid)
    old_slug, title = row['slug'], row['title']
    new_slug = slugkit.slugify(title)
    if R.draft_exists(ctx.root, dict(row, output_path=row['output_path'].replace('-%s.md' % old_slug, '-%s.md' % new_slug))):
        raise Refuse('HAS_DRAFT', '%s co draft cung slug moi — khong di tru' % aid)
    if slugkit.slugify_legacy_without_d(title) != old_slug or new_slug == old_slug:
        raise Refuse('SLUG_NOT_KNOWN_DEFECT', '%s: slug %r khong phai slug loi cu (mat chu d) cua tieu de' % (aid, old_slug))
    dm = OUT_PATH_RE.match(old_path)
    if not dm or dm.group(2) != old_slug:
        raise Refuse('BAD_OUTPUT_PATH', '%s: output_path %r khong khop slug %r' % (aid, old_path, old_slug))
    new_path = '_posts/%s-%s.md' % (dm.group(1), new_slug)
    ev_path = ctx.root / 'data/qa' / (aid + '.json')
    if not ev_path.is_file():
        raise Refuse('NO_EVIDENCE', '%s khong co evidence' % aid)
    old_ev_bytes = ev_path.read_bytes()
    old_ev = json.loads(old_ev_bytes)
    post_path = ctx.root / old_path
    if not post_path.is_file():
        raise Refuse('NO_POST', '%s: khong co file bai %s' % (aid, old_path))
    old_post = post_path.read_bytes()
    if not (sha(old_post) == old_ev.get('content_sha256') and A.fingerprint(row) == old_ev.get('matrix_row_sha256')
            and old_ev.get('article_id') == aid and old_ev.get('source_path') == old_path
            and old_ev.get('result') == 'PASS'):
        raise Refuse('EVIDENCE_NOT_INTACT',
                     '%s: evidence khong khop byte bai/hang matrix hien tai (hash lech, source_path, result) — '
                     'xu ly bang reattest-legacy-qa.py (chu duyet) truoc, khong di tru' % aid)
    old_text = read_text_exact(old_post)
    old_url = front_permalink(old_text)
    try:
        new_url = slugkit.replace_slug_in_url(old_url, old_slug, new_slug)
    except ValueError as e:
        raise Refuse('BAD_URL_SHAPE', '%s: %s' % (aid, e))
    if (base['old_url'], base['new_url'], baseline_new_path(base['new_output_path'])) != (old_url, new_url, new_path):
        raise Refuse('URL_MISMATCH_BASELINE', '%s: URL/duong dan tinh duoc (%s -> %s, %s) khac baseline (%s -> %s, %s)'
                     % (aid, old_url, new_url, new_path, base['old_url'], base['new_url'], base['new_output_path']))
    drift = not (row['expected_url'] == old_url and row['canonical_url'] == old_url)
    if drift and row['expected_url'] != row['canonical_url']:
        raise Refuse('MATRIX_URL_INCONSISTENT', '%s: expected_url != canonical_url trong matrix' % aid)
    new_row = dict(row, slug=new_slug, expected_url=new_url, canonical_url=new_url, output_path=new_path)
    _collisions(ctx, aid, new_slug, new_url, new_path, extra)
    new_text = replace_permalink(old_text, old_url, new_url)
    check_only_permalink_changed(old_text, new_text, old_url, new_url)
    new_post = new_text.encode('utf-8')
    if not score:
        d = Derived()
        d.aid, d.old_row, d.new_row, d.old_path, d.new_path = aid, row, new_row, old_path, new_path
        d.old_url, d.new_url, d.old_slug, d.new_slug = old_url, new_url, old_slug, new_slug
        d.old_post, d.new_post, d.old_ev_bytes, d.old_ev, d.before, d.after, d.url_drift = (
            old_post, new_post, old_ev_bytes, old_ev, None, None, drift)
        d.entry = None
        return d
    final_rows = [(extra.get(r['id']) if r['id'] != aid and r['id'] in extra else (new_row if r['id'] == aid else r))
                  for r in ctx.rows]
    before = R.score_candidate(ctx, row, old_post)
    ctx2 = copy.copy(ctx)
    ctx2.rows = final_rows
    after = R.score_candidate(ctx2, new_row, new_post)
    if (after.get('content_sha256') != sha(new_post) or after.get('matrix_row_sha256') != A.fingerprint(new_row)
            or after.get('article_id') != aid or after.get('source_path') != new_path):
        raise Refuse('FRESH_QA_UNBOUND', '%s: diem cham khong buoc dung byte/hang ung vien' % aid)
    if not R.score_ok(after):
        failed = sorted(k for k, v in after.get('checks', {}).items() if not v)
        raise Refuse('FRESH_QA_NOT_ELIGIBLE', '%s: cham lai doc lap = %s q=%s s=%s (failed_checks=%s) — giu nguyen URL cu'
                     % (aid, after.get('result'), after.get('quality'), after.get('seo'), failed), failed_checks=failed)
    flipped = sorted(k for k, v in before.get('checks', {}).items() if v and not after.get('checks', {}).get(k))
    if flipped or after['quality'] < before.get('quality', 0) or after['seo'] < before.get('seo', 0):
        raise Refuse('REGRESSION', '%s: di tru lam tut tieu chi %s hoac diem (q %s->%s, s %s->%s)'
                     % (aid, flipped, before.get('quality'), after['quality'], before.get('seo'), after['seo']),
                     flipped=flipped)
    d = Derived()
    d.aid, d.old_row, d.new_row, d.old_path, d.new_path = aid, row, new_row, old_path, new_path
    d.old_url, d.new_url, d.old_slug, d.new_slug = old_url, new_url, old_slug, new_slug
    d.old_post, d.new_post, d.old_ev_bytes, d.old_ev, d.before, d.after, d.url_drift = (
        old_post, new_post, old_ev_bytes, old_ev, before, after, drift)
    d.entry = None
    return d


def entry_of(d):
    return {'id': d.aid, 'decision': ELIGIBLE, 'old_url': d.old_url, 'new_url': d.new_url, 'old_slug': d.old_slug,
            'new_slug': d.new_slug, 'old_path': d.old_path, 'new_path': d.new_path, 'matrix_url_drift': d.url_drift,
            'base_post_sha256': sha(d.old_post), 'new_post_sha256': sha(d.new_post),
            'old_evidence_sha256': sha(d.old_ev_bytes), 'old_row_fingerprint': A.fingerprint(d.old_row),
            'new_row_fingerprint': A.fingerprint(d.new_row), 'before': R.summary(d.before), 'after': R.summary(d.after),
            'before_scores': {'quality': d.before.get('quality'), 'seo': d.before.get('seo')}}


def build_new_evidence(ctx, d, old_evidence_sha256):
    old_ev = d.old_ev
    if not old_ev.get('scored_at'):
        raise Refuse('NO_HISTORICAL_SCORED_AT', '%s: evidence cu khong co scored_at lich su de giu' % d.aid)
    new = copy.deepcopy(d.after)
    for k in ('scored_at', 'published_at'):            # mốc lịch sử: giữ nguyên (watchdog đọc như tín hiệu hoạt động)
        if old_ev.get(k):
            new[k] = old_ev[k]
    for k, v in old_ev.items():                         # chú thích lịch sử (reattestation,...): giữ nguyên
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
        'old_url': d.old_url, 'new_url': d.new_url, 'old_slug': d.old_slug, 'new_slug': d.new_slug,
        'old_output_path': d.old_path, 'new_output_path': d.new_path, 'matrix_url_drift_fixed': d.url_drift,
        'redirect': 'HTTP 200 + meta refresh 0s + canonical (khong phai HTTP 301): %s' % SR.stub_relpath(d.aid),
        'previous_scores': {k: old_ev.get(k) for k in ('quality', 'seo', 'grade')},
        'scorer': new.get('scorer'), 'thresholds': {'quality_min': ctx.op.QUALITY_MIN, 'seo_min': ctx.op.SEO_MIN},
        'tool': 'scripts/factory/migrate-slug-urls.py', 'tool_commit': ctx.tool_commit, **code_sha(ctx),
        'note': ('chi doi URL (slug thieu chu d -> dung); than bai va moi dong front matter khac giu nguyen tung byte; '
                 'scored_at/published_at o cap tren giu moc lich su goc; cham diem doc lap luc revised_at'),
    }
    if history:
        new['revision']['history'] = history
    return new


# ------------------------------------------------------------------ plan

_PLAN_CTX = None


def _plan_worker(aid):
    try:
        d = derive(_PLAN_CTX, aid)
        return aid, entry_of(d), None
    except Refuse as e:
        return aid, None, {'id': aid, 'decision': e.code, 'reason': e.msg}


def make_plan(ctx, ids=None, jobs=1):
    global _PLAN_CTX
    ids = sorted(ids if ids is not None else ctx.baseline)
    _PLAN_CTX = ctx
    if jobs > 1:
        import multiprocessing
        with multiprocessing.get_context('fork').Pool(jobs) as pool:
            results = pool.map(_plan_worker, ids, chunksize=8)
    else:
        results = [_plan_worker(a) for a in ids]
    entries, excluded = {}, collections.defaultdict(list)
    for aid, ent, err in results:
        if ent is not None:
            entries[aid] = ent
        else:
            entries[aid] = err
            excluded[err['decision']].append(aid)
    eligible = sorted(i for i, e in entries.items() if e['decision'] == ELIGIBLE)
    return {
        'schema': MANIFEST_SCHEMA,
        'authority': 'PROPOSAL ONLY — apply kiem lai moi dieu kien tu git + byte hien tai',
        'head': ctx.head, 'head_bound': True,
        'matrix_sha256': sha((ctx.root / MATRIX_REL).read_bytes()),
        'thresholds': {'quality_min': ctx.op.QUALITY_MIN, 'seo_min': ctx.op.SEO_MIN},
        **code_sha(ctx),
        'counts': {'baseline': len(ctx.baseline), 'planned': len(entries), 'eligible': len(eligible),
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
    for k in ('scorer_code_sha256', 'business_facts_sha256', 'taxonomy_sha256', 'slugkit_sha256', 'baseline_sha256'):
        if manifest.get(k) != code_sha(ctx).get(k):
            raise Refuse('SCORER_CHANGED_SINCE_PLAN', '%s khac manifest (scorer/facts/taxonomy/slugkit/baseline da doi) — chay lai plan' % k)
    if manifest.get('thresholds') != {'quality_min': ctx.op.QUALITY_MIN, 'seo_min': ctx.op.SEO_MIN}:
        raise Refuse('SCORER_CHANGED_SINCE_PLAN', 'nguong QA khac manifest — chay lai plan')


# ------------------------------------------------------------------ ghi: matrix / registry / stub

def matrix_bytes_with(root, replacements):
    """Matrix mới = matrix hiện tại với các hàng thay thế; hàng khác giữ nguyên TỪNG BYTE (CSV tất định, LF)."""
    raw = (root / MATRIX_REL).read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8'), newline=''))
    fields = reader.fieldnames
    rows = list(reader)
    seen = set()
    out = []
    for r in rows:
        if r['id'] in replacements:
            new = replacements[r['id']]
            if set(new) != set(fields):
                raise Refuse('MATRIX_SCHEMA', 'hang thay the khac cot cua matrix')
            diff = [k for k in fields if new[k] != r[k]]
            if set(diff) - set(URL_COLS):
                raise Refuse('MATRIX_UNEXPECTED_COLUMNS', '%s: doi cot ngoai %s: %s' % (r['id'], URL_COLS, diff))
            seen.add(r['id'])
            out.append(new)
        else:
            out.append(r)
    if seen != set(replacements):
        raise Refuse('MATRIX_ROW_MISSING', 'khong thay hang: %s' % sorted(set(replacements) - seen)[:5])
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
    w.writeheader()
    w.writerows(out)
    new_bytes = buf.getvalue().encode('utf-8')
    if not replacements and new_bytes != raw:
        raise Refuse('MATRIX_ROUNDTRIP', 'CSV khong round-trip byte-exact — khong ghi')
    return new_bytes


def registry_entry(ctx, d):
    return {'article_id': d.aid, 'title': d.new_row['title'], 'old_url': d.old_url, 'new_url': d.new_url,
            'old_slug': d.old_slug, 'new_slug': d.new_slug, 'old_output_path': d.old_path,
            'new_output_path': d.new_path, 'status': SR.MIGRATED, 'batch_id': ctx.batch_id, 'migrated_at': now_iso()}


def doc_text(obj):
    return R.doc_text(obj)


# ------------------------------------------------------------------ apply

def prepare(ctx, manifest, aid, extra):
    e = manifest['entries'].get(aid)
    if e is None or aid not in manifest['eligible'] or e.get('decision') != ELIGIBLE:
        raise Refuse('NOT_ELIGIBLE', '%s khong thuoc danh sach du dieu kien cua manifest' % aid)
    if aid in ctx.registry:
        return 'already_current', None
    cur = (ctx.root / ctx.by_id[aid]['output_path']).read_bytes() if aid in ctx.by_id else b''
    if sha(cur) != e['base_post_sha256']:
        raise Refuse('POST_CHANGED_SINCE_PLAN', '%s: bai da doi tu luc plan' % aid)
    ev_p = ctx.root / 'data/qa' / (aid + '.json')
    if not ev_p.is_file() or sha(ev_p.read_bytes()) != e['old_evidence_sha256']:
        raise Refuse('EVIDENCE_CHANGED_SINCE_PLAN', '%s: evidence da doi tu luc plan' % aid)
    d = derive(ctx, aid, extra)
    if (sha(d.new_post) != e['new_post_sha256'] or sha(d.old_ev_bytes) != e['old_evidence_sha256']
            or A.fingerprint(d.new_row) != e['new_row_fingerprint']
            or R.summary(d.after) != e['after']):
        raise Refuse('INPUT_CHANGED_SINCE_PLAN', '%s: byte/hang/diem ung vien khac manifest' % aid)
    return 'ready', d


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
        ctx.batch_id = 'migrate-%s-%s-%s' % (datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d'), ids[0], ids[-1])
    ctx.purpose = 'slug-d-migration'
    ctx.reason = ('Sua slug bi mat chu U+0111 (d co gach ngang -> d) cua bai da xuat ban; URL cu thanh trang HTTP 200 + meta refresh 0s + canonical '
                  '(GitHub Pages khong co HTTP 301 theo duong dan). Issue #77.')
    # pass 1: ứng viên + corpus cuối của lô (hàng mới của các ID cùng lô) -> chấm điểm trên corpus cuối
    stage1, skipped, ineligible = {}, [], []
    for aid in ids:
        try:
            row = ctx.by_id.get(aid)
            if row is None:
                raise Refuse('NOT_PUBLISHED', '%s khong co trong matrix' % aid)
            if aid in ctx.registry:
                skipped.append(aid)
                continue
            e = manifest['entries'].get(aid)
            if e is None or aid not in manifest['eligible'] or e.get('decision') != ELIGIBLE:
                raise Refuse('NOT_ELIGIBLE', '%s khong thuoc danh sach du dieu kien cua manifest' % aid)
            post_p = ctx.root / row['output_path']
            if not post_p.is_file() or sha(post_p.read_bytes()) != e['base_post_sha256']:
                raise Refuse('POST_CHANGED_SINCE_PLAN', '%s: bai da doi tu luc plan' % aid)
            d0 = derive(ctx, aid, score=False)
            stage1[aid] = d0.new_row
        except Refuse as e:
            if skip_ineligible and e.code in SKIPPABLE:
                ineligible.append({'id': aid, 'code': e.code, 'reason': e.msg})
                continue
            raise
    prepared = []
    for aid in sorted(stage1):
        try:
            state, d = prepare(ctx, manifest, aid, {k: v for k, v in stage1.items() if k != aid})
        except Refuse as e:
            if skip_ineligible and e.code in SKIPPABLE:
                ineligible.append({'id': aid, 'code': e.code, 'reason': e.msg})
                continue
            raise
        if state == 'already_current':
            skipped.append(aid)
        else:
            prepared.append(d)
    report = {'ok': True, 'batch_id': ctx.batch_id, 'dry_run': dry_run,
              'would_write' if dry_run else 'written': [d.aid for d in prepared],
              'already_current': skipped, 'skipped_ineligible': ineligible}
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
    new_rows = {d.aid: d.new_row for d in prepared}
    matrix_old = (root / MATRIX_REL).read_bytes()
    matrix_bytes_with(root, {})                      # CSV round-trip byte-exact TRƯỚC khi thay hàng (hàng khác giữ nguyên từng byte)
    matrix_new = matrix_bytes_with(root, new_rows)
    reg_old_path = root / SR.REGISTRY_REL
    reg_old = reg_old_path.read_bytes()
    reg_rows = [dict(r) for r in SR.load_registry(root)] + [registry_entry(ctx, d) for d in prepared]
    reg_new = SR.registry_text(reg_rows).encode('utf-8')
    backup = {'schema': BACKUP_SCHEMA, 'batch_id': ctx.batch_id, 'created_at': now_iso(), 'approval_ref': ctx.approval_ref,
              'purpose': ctx.purpose, 'reason': ctx.reason, 'head_at_apply': ctx.head, 'tool_commit': ctx.tool_commit,
              'manifest_sha256': sha(doc_text(manifest).encode('utf-8')),
              'matrix_old_sha256': sha(matrix_old), 'matrix_new_sha256': sha(matrix_new),
              'registry_old_sha256': sha(reg_old), 'registry_new_sha256': sha(reg_new), 'entries': {}}
    blobs = {}
    for d in prepared:
        new_ev = build_new_evidence(ctx, d, sha(d.old_ev_bytes))
        new_ev_bytes = R.evidence_text(new_ev).encode('utf-8')
        stub = SR.stub_source(registry_entry(ctx, d))
        blobs[d.aid] = (new_ev_bytes, stub)
        backup['entries'][d.aid] = {
            'old_path': d.old_path, 'new_path': d.new_path, 'old_url': d.old_url, 'new_url': d.new_url,
            'old_slug': d.old_slug, 'new_slug': d.new_slug,
            'old_post_text': d.old_post.decode('utf-8'), 'old_post_sha256': sha(d.old_post), 'new_post_sha256': sha(d.new_post),
            'old_evidence_text': d.old_ev_bytes.decode('utf-8'), 'old_evidence_sha256': sha(d.old_ev_bytes),
            'new_evidence_sha256': sha(new_ev_bytes), 'old_row': d.old_row, 'new_row': d.new_row,
            'stub_path': SR.stub_relpath(d.aid), 'stub_sha256': sha(stub.encode('utf-8')), 'matrix_url_drift': d.url_drift}
    atomic_write(backup_path, doc_text(backup).encode('utf-8'))
    if json.loads(backup_path.read_text(encoding='utf-8')) != json.loads(doc_text(backup)):
        backup_path.unlink()
        raise Refuse('BACKUP_READBACK_FAILED', 'doc lai sao luu khong khop — chua sua file nao')
    attempted = []
    try:
        for d in prepared:
            old_p, new_p = root / d.old_path, root / d.new_path
            ev_p = root / 'data/qa' / (d.aid + '.json')
            stub_p = root / SR.stub_relpath(d.aid)
            if old_p.read_bytes() != d.old_post or ev_p.read_bytes() != d.old_ev_bytes or new_p.exists() or stub_p.exists():
                raise Refuse('FILES_CHANGED_DURING_APPLY', '%s: bai/evidence/dich doi trong luc apply' % d.aid)
            attempted.append(d.aid)                                     # TRƯỚC khi ghi
            atomic_write(new_p, d.new_post)
            atomic_write(ev_p, blobs[d.aid][0])
            atomic_write(stub_p, blobs[d.aid][1].encode('utf-8'))
            old_p.unlink()
            if sha(new_p.read_bytes()) != sha(d.new_post) or sha(ev_p.read_bytes()) != sha(blobs[d.aid][0]):
                raise Refuse('WRITE_MISMATCH', '%s: doc lai khong khop' % d.aid)
        if (root / MATRIX_REL).read_bytes() != matrix_old or reg_old_path.read_bytes() != reg_old:
            raise Refuse('FILES_CHANGED_DURING_APPLY', 'matrix/registry doi trong luc apply')
        attempted.append('__shared__')
        atomic_write(root / MATRIX_REL, matrix_new)
        atomic_write(reg_old_path, reg_new)
        ctx2 = make_ctx(root, ctx.approval_ref, ctx.batch_id, ctx.purpose, ctx.reason)
        problems = verify_backup(ctx2, backup, rescore=True)
        if problems:
            raise Refuse('POST_VERIFY_FAILED', '; '.join(problems[:5]), problems=problems)
    except BaseException as exc:
        _abort_apply(ctx, backup, backup_path, exc, attempted, matrix_old, reg_old)
        raise
    report['backup'] = backup_rel
    return report


def _abort_apply(ctx, backup, backup_path, exc, attempted, matrix_old, reg_old):
    """Apply lỗi giữa chừng: trả MỌI thứ lần chạy này đã bắt đầu ghi về byte cũ; chỉ xóa sao lưu khi mọi thứ đã về."""
    root = ctx.root
    try:
        if '__shared__' in attempted:
            atomic_write(root / MATRIX_REL, matrix_old)
            atomic_write(root / SR.REGISTRY_REL, reg_old)
        rollback_backup(root, backup, ids={a for a in attempted if a != '__shared__'}, force=True, shared=False)
    except BaseException:
        pass
    left = []
    for aid in sorted(a for a in attempted if a != '__shared__'):
        b = backup['entries'][aid]
        if (not (root / b['old_path']).is_file() or sha((root / b['old_path']).read_bytes()) != b['old_post_sha256']
                or (root / b['new_path']).exists() or (root / b['stub_path']).exists()
                or sha((root / 'data/qa' / (aid + '.json')).read_bytes()) != b['old_evidence_sha256']):
            left.append(aid)
    if (root / MATRIX_REL).read_bytes() != matrix_old or (root / SR.REGISTRY_REL).read_bytes() != reg_old:
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
        for k in ('old_path', 'new_path'):
            if not isinstance(b.get(k), str) or not R.POST_RE.match(b[k]):
                raise Refuse('BAD_BACKUP', '%s: %s khong nam trong _posts/' % (aid, k))
        for k in ('old_post_text', 'old_post_sha256', 'new_post_sha256', 'old_evidence_text', 'old_evidence_sha256',
                  'new_evidence_sha256', 'old_url', 'new_url', 'old_slug', 'new_slug', 'stub_path', 'stub_sha256'):
            if not isinstance(b.get(k), str):
                raise Refuse('BAD_BACKUP', '%s: thieu %s' % (aid, k))
        if not isinstance(b.get('old_row'), dict) or not isinstance(b.get('new_row'), dict):
            raise Refuse('BAD_BACKUP', '%s: thieu old_row/new_row' % aid)


def verify_backup(ctx, backup, rescore=True):
    """Kiểm trạng thái ĐÃ GHI so với sao lưu + chấm lại ĐỘC LẬP. Trả danh sách lỗi."""
    check_backup_shape(backup)
    problems = []
    root = ctx.root
    reg = {r['article_id']: r for r in SR.load_registry(root)}
    for aid, b in sorted(backup['entries'].items()):
        old_p, new_p = root / b['old_path'], root / b['new_path']
        ev_p = root / 'data/qa' / (aid + '.json')
        stub_p = root / b['stub_path']
        if old_p.exists():
            problems.append('%s: tep bai cu %s con ton tai' % (aid, b['old_path']))
        if not new_p.is_file() or not ev_p.is_file():
            problems.append('%s: thieu bai moi hoac evidence' % aid)
            continue
        post_raw, ev_raw = new_p.read_bytes(), ev_p.read_bytes()
        if sha(post_raw) != b['new_post_sha256']:
            problems.append('%s: bai khac ban da ghi' % aid)
            continue
        if sha(ev_raw) != b['new_evidence_sha256']:
            problems.append('%s: evidence khac ban da ghi' % aid)
            continue
        old_text = b['old_post_text']
        if sha(old_text.encode('utf-8')) != b['old_post_sha256']:
            problems.append('%s: sao luu bai cu hong (sha khong khop)' % aid)
            continue
        try:
            replay = replace_permalink(old_text, b['old_url'], b['new_url'])
            check_only_permalink_changed(old_text, replay, b['old_url'], b['new_url'])
        except Refuse as e:
            problems.append('%s: bai cu + doi permalink khong hop le (%s)' % (aid, e.code))
            continue
        if replay.encode('utf-8') != post_raw:
            problems.append('%s: bai hien tai != bai cu + doi dung dong permalink' % aid)
        ev = json.loads(ev_raw)
        row = ctx.by_id.get(aid)
        if row is None or row['status'] != 'PUBLISHED' or row.get('output_path') != b['new_path']:
            problems.append('%s: khong con PUBLISHED / output_path khac' % aid)
            continue
        for k in URL_COLS:
            if row[k] != b['new_row'][k]:
                problems.append('%s: matrix %s = %r khac ban da ghi %r' % (aid, k, row[k], b['new_row'][k]))
        if row != b['new_row']:
            problems.append('%s: hang matrix khac ban da ghi' % aid)
        if {k: v for k, v in b['old_row'].items() if k not in URL_COLS} != {k: v for k, v in row.items() if k not in URL_COLS}:
            problems.append('%s: hang matrix doi o cot ngoai %s so voi hang cu' % (aid, URL_COLS))
        if front_permalink(post_raw.decode('utf-8')) != b['new_url']:
            problems.append('%s: permalink trong bai khac new_url' % aid)
        if ev.get('content_sha256') != sha(post_raw):
            problems.append('%s: content_sha256 khong khop bai hien tai' % aid)
        if ev.get('matrix_row_sha256') != A.fingerprint(row):
            problems.append('%s: matrix_row_sha256 khong khop hang hien tai' % aid)
        if ev.get('source_path') != row['output_path'] or ev.get('article_id') != aid:
            problems.append('%s: source_path/article_id trong evidence sai' % aid)
        if not R.score_ok(ev):
            problems.append('%s: diem/cong QA khong dat nguong' % aid)
        rev = ev.get('revision') or {}
        old_ev = json.loads(b['old_evidence_text'])
        old_ev_sha = sha(b['old_evidence_text'].encode('utf-8'))
        if (b['old_evidence_sha256'] != old_ev_sha or rev.get('kind') != KIND
                or rev.get('previous_evidence_sha256') != old_ev_sha
                or rev.get('previous_content_sha256') != old_ev.get('content_sha256')
                or rev.get('previous_matrix_row_sha256') != old_ev.get('matrix_row_sha256')
                or rev.get('new_content_sha256') != ev.get('content_sha256')
                or (rev.get('old_url'), rev.get('new_url')) != (b['old_url'], b['new_url'])
                or not (rev.get('approval_ref') or '').strip()):
            problems.append('%s: provenance khong khop sao luu' % aid)
        for k in ('scored_at', 'published_at'):
            if old_ev.get(k) and ev.get(k) != old_ev.get(k):
                problems.append('%s: %s lich su khong duoc giu nguyen' % (aid, k))
        lost = sorted(k for k in old_ev if k not in ev and k != 'revision')
        if lost:
            problems.append('%s: mat chu thich lich su cua evidence cu: %s' % (aid, ', '.join(lost[:5])))
        r = reg.get(aid)
        if r is None or r.get('status') != SR.MIGRATED or (r['old_url'], r['new_url'], r['new_output_path']) != (
                b['old_url'], b['new_url'], b['new_path']):
            problems.append('%s: registry thieu/sai' % aid)
        else:
            want = SR.stub_source(r)
            if not stub_p.is_file() or stub_p.read_text(encoding='utf-8') != want or sha(want.encode('utf-8')) != b['stub_sha256']:
                problems.append('%s: trang chuyen huong thieu/sai' % aid)
        if rescore:
            diff = R.score_diff(ev, R.score_candidate(ctx, row, post_raw))
            if diff:
                problems.append('%s: diem trong evidence khac diem cham lai doc lap (%s)' % (aid, ', '.join(diff[:6])))
    return problems


def rollback_backup(root, backup, ids=None, dry_run=False, force=False, shared=True):
    """Khôi phục byte-exact: bài cũ (đúng tên cũ), evidence cũ, hàng matrix cũ, bỏ dòng registry và trang chuyển hướng.
    Mỗi mục chỉ được khôi phục khi còn đúng bản ĐÃ GHI (không đè thay đổi của người khác); `force` (nội bộ) khôi phục cả bản dở.
    Thứ tự an toàn: (1) kiểm TOÀN BỘ điều kiện (tệp + matrix + registry) rồi mới (2) ghi; (3) phần dùng chung (matrix/registry)
    độc lập với trạng thái tệp của từng ID nên chạy lại sau một lần bị ngắt vẫn hoàn tất, không bao giờ kẹt nửa chừng."""
    check_backup_shape(backup)
    root = pathlib.Path(root)
    if ids is not None:
        unknown = sorted(set(ids) - set(backup['entries']))
        if unknown:
            raise Refuse('UNKNOWN_IDS', 'ID khong co trong sao luu: %s' % unknown[:5])
    out = {'restored': [], 'skipped_changed_since_apply': [], 'shared_restored': [], 'dry_run': dry_run}
    plan, original_ids = [], []
    for aid, b in sorted(backup['entries'].items()):
        if ids is not None and aid not in ids:
            continue
        old_post, old_ev = b['old_post_text'].encode('utf-8'), b['old_evidence_text'].encode('utf-8')
        if sha(old_post) != b['old_post_sha256'] or sha(old_ev) != b['old_evidence_sha256']:
            raise Refuse('BACKUP_CORRUPT', '%s: sao luu hong' % aid)
        old_p, new_p = root / b['old_path'], root / b['new_path']
        ev_p, stub_p = root / 'data/qa' / (aid + '.json'), root / b['stub_path']
        written = (not old_p.exists() and new_p.is_file() and sha(new_p.read_bytes()) == b['new_post_sha256']
                   and ev_p.is_file() and sha(ev_p.read_bytes()) == b['new_evidence_sha256'])
        original = (old_p.is_file() and sha(old_p.read_bytes()) == b['old_post_sha256'] and not new_p.exists()
                    and ev_p.is_file() and sha(ev_p.read_bytes()) == b['old_evidence_sha256'] and not stub_p.exists())
        if original:
            original_ids.append(aid)
            continue
        if not written and not force:
            out['skipped_changed_since_apply'].append(aid)
            continue
        plan.append((aid, b, old_post, old_ev, old_p, new_p, ev_p, stub_p))
        out['restored'].append(aid)
    # phần dùng chung: ID sắp khôi phục tệp + ID đã có tệp cũ (lần rollback trước bị ngắt) mà matrix/registry còn ở bản đã di trú
    shared_plan = []                                   # (aid, b, hàng matrix còn là bản đã ghi?)
    if shared and not force and plan:
        inbound = inbound_links_to_new_urls(root, backup, [p[0] for p in plan])
        if inbound:
            raise Refuse('INBOUND_LINKS_TO_NEW_URL',
                         'con bai khac lien ket toi URL moi sap bi go (%s) — `links-rollback` pha 2 TRUOC, roi moi rollback pha 1 '
                         '(chua ghi gi)' % '; '.join('%s <- %s' % h for h in inbound))
    if shared:
        cur = {r['id']: r for r in SR.read_csv_rows(root / MATRIX_REL)}
        in_registry = {r['article_id'] for r in SR.load_registry(root)}
        for aid in sorted({p[0] for p in plan} | set(original_ids)):
            b = backup['entries'][aid]
            row = cur.get(aid)
            migrated = row == b['new_row']
            if not migrated and row != b['old_row'] and not force:
                raise Refuse('MATRIX_CHANGED_SINCE_APPLY',
                             '%s: hang matrix da doi sau apply — khong khoi phuc ban mo (chua ghi gi)' % aid)
            if migrated or aid in in_registry:
                shared_plan.append((aid, b, migrated))
        out['shared_restored'] = [a for a, _, _ in shared_plan]
    if dry_run:
        return out
    for aid, b, old_post, old_ev, old_p, new_p, ev_p, stub_p in plan:
        atomic_write(old_p, old_post)
        atomic_write(ev_p, old_ev)
        if new_p.exists():
            new_p.unlink()
        if stub_p.exists():
            stub_p.unlink()
        if sha(old_p.read_bytes()) != sha(old_post) or sha(ev_p.read_bytes()) != sha(old_ev):
            raise Refuse('ROLLBACK_MISMATCH', '%s: khoi phuc khong khop' % aid)
    if shared_plan:
        restore = {aid: b['old_row'] for aid, b, migrated in shared_plan if migrated}
        if restore:
            atomic_write(root / MATRIX_REL, _matrix_restore_bytes(root, restore))
        drop = {aid for aid, _, _ in shared_plan}
        reg = [r for r in SR.load_registry(root) if r['article_id'] not in drop]
        atomic_write(root / SR.REGISTRY_REL, SR.registry_text(reg).encode('utf-8'))
    out['ok'] = True
    return out


def inbound_links_to_new_urls(root, backup, ids):
    """Bài KHÁC (không thuộc các mục sắp khôi phục) còn liên kết `](URL_MỚI)` / `href="URL_MỚI"` tới URL sẽ biến mất khi rollback
    (thường do pha 2 `links-apply` đã trỏ thẳng tới URL mới). Trả [(ID đích, đường dẫn bài nguồn)] — tối đa 5."""
    root = pathlib.Path(root)
    news = {backup['entries'][a]['new_url']: a for a in ids}
    if not news:
        return []
    own = {root / backup['entries'][a]['new_path'] for a in ids}
    md, html = _link_res({u: u for u in news})
    hits = []
    for p in sorted((root / '_posts').glob('*.md')):
        if p in own:
            continue
        text = p.read_text(encoding='utf-8', errors='replace')
        for rx in (md, html):
            m = rx.search(text)
            if m:
                hits.append((news[m.group(2)], str(p.relative_to(root))))
                break
        if len(hits) >= 5:
            break
    return hits


def _matrix_restore_bytes(root, old_rows):
    raw = (root / MATRIX_REL).read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8'), newline=''))
    fields = reader.fieldnames
    rows = [old_rows.get(r['id'], r) for r in reader]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode('utf-8')


# ------------------------------------------------------------------ dữ liệu phái sinh theo URL

def mapping(root):
    """URL cũ -> mới của mọi bài đã di trú (còn trang chuyển hướng HOẶC URL cũ đã gỡ — liên kết tới URL đã gỡ là 404, càng phải trỏ thẳng)."""
    return {r['old_url']: r['new_url'] for r in SR.load_registry(root) if r.get('status') in SR.STATUSES}


def _rewrite(text, mp):
    """Thay URL cũ -> mới theo TOKEN đầy đủ (URL kết thúc bằng '/', được bao bởi ký tự không thuộc URL)."""
    if not mp:
        return text
    pat = re.compile('|'.join(re.escape(k) for k in sorted(mp, key=len, reverse=True)))
    return pat.sub(lambda m: mp[m.group(0)], text)


def refresh_data(root, check=False):
    """Sau khi di trú: (1) dữ liệu khóa theo URL không sinh bằng máy (legal-notices.json, seo-leads.yml) được ánh xạ URL cũ -> mới
    theo registry; (2) dữ liệu sinh bằng máy (seo-topic-links.json, price-notices.json) được sinh lại bằng đúng script của nó.
    Trả danh sách tệp đã đổi (check=True: không ghi, trả danh sách tệp LỆCH)."""
    root = pathlib.Path(root)
    mp = mapping(root)
    changed = []
    for rel in (LEGAL_NOTICES_REL, LEADS_REL):
        p = root / rel
        if not p.is_file():
            continue
        old = p.read_text(encoding='utf-8')
        new = _rewrite(old, mp)
        if rel.endswith('.json'):
            json.loads(new)
        if new != old:
            changed.append(rel)
            if not check:
                atomic_write(p, new.encode('utf-8'))
    for rel, script in GENERATED_DATA:
        p = root / rel
        before = p.read_bytes() if p.is_file() else b''
        cmd = [sys.executable, str(root / script)] + (['--check'] if check else [])
        r = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
        if r.returncode != 0 and not check:
            raise Refuse('GENERATOR_FAILED', '%s: %s' % (script, (r.stdout + r.stderr)[-300:]))
        if check:
            if r.returncode != 0:
                changed.append(rel)
        elif (p.read_bytes() if p.is_file() else b'') != before:
            changed.append(rel)
    return changed


# ------------------------------------------------------------------ pha 2: đổi ĐÍCH liên kết nội bộ

LINK_MANIFEST_SCHEMA = 'retarget-manifest/1'
LINK_BACKUP_SCHEMA = 'retarget-backup/1'
LINK_BACKUP_DIR = 'reports/qa-audit/links'
LINK_KIND = 'link-retarget'
MASK_RE = re.compile(r'(\]\()[^)]*(\))|(href=")[^"]*(")')


def mapping_digest(mp):
    return sha(json.dumps(mp, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8'))


def _link_res(mp):
    keys = '|'.join(re.escape(k) for k in sorted(mp, key=len, reverse=True))
    md = re.compile(r'(\]\()(%s)((?:#[^)\s"]*)?(?:\s+"[^"]*")?\))' % keys)
    html = re.compile(r'(href=")(%s)((?:#[^"]*)?")' % keys)
    return md, html


def retarget_text(text, mp):
    """Đổi đích liên kết có trong ánh xạ. Trả (văn bản mới, {đích cũ: số lần})."""
    if not mp:
        return text, {}
    md, html = _link_res(mp)
    counts = collections.Counter()

    def sub(m):
        counts[m.group(2)] += 1
        return m.group(1) + mp[m.group(2)] + m.group(3)

    out = html.sub(sub, md.sub(sub, text))
    return out, dict(counts)


def mask_links(text):
    """Văn bản với MỌI đích liên kết thay bằng chỗ giữ: hai văn bản bằng nhau sau mask <=> chỉ khác đích liên kết."""
    return MASK_RE.sub(lambda m: (m.group(1) + '#' + m.group(2)) if m.group(1) else (m.group(3) + '#' + m.group(4)), text)


def derive_links(ctx, aid, mp, score=True):
    row = ctx.by_id.get(aid)
    if row is None or row['status'] != 'PUBLISHED':
        raise Refuse('NOT_PUBLISHED', '%s khong phai hang PUBLISHED' % aid)
    path = row.get('output_path') or ''
    if not R.POST_RE.match(path):
        raise Refuse('BAD_OUTPUT_PATH', '%s: output_path %r khong nam trong _posts/' % (aid, path))
    if aid in R.lease_ids(ctx.root):
        raise Refuse('LEASED', '%s nam trong lease writer — khong sua' % aid)
    if R.draft_exists(ctx.root, row):
        raise Refuse('HAS_DRAFT', '%s co draft cung slug/article_id — khong sua' % aid)
    ev_path = ctx.root / 'data/qa' / (aid + '.json')
    if not ev_path.is_file():
        raise Refuse('NO_EVIDENCE', '%s khong co evidence' % aid)
    old_ev_bytes = ev_path.read_bytes()
    old_ev = json.loads(old_ev_bytes)
    post_path = ctx.root / path
    if not post_path.is_file():
        raise Refuse('NO_POST', '%s: khong co file bai %s' % (aid, path))
    old_post = post_path.read_bytes()
    old_text = read_text_exact(old_post)
    new_text, counts = retarget_text(old_text, mp)
    if not counts:
        raise Refuse('NO_LINKS', '%s: khong co lien ket nao thuoc anh xa' % aid)
    if not (sha(old_post) == old_ev.get('content_sha256') and A.fingerprint(row) == old_ev.get('matrix_row_sha256')
            and old_ev.get('article_id') == aid and old_ev.get('source_path') == path and old_ev.get('result') == 'PASS'):
        raise Refuse('EVIDENCE_NOT_INTACT', '%s: evidence khong khop byte bai/hang matrix hien tai — xu ly bang '
                     'reattest-legacy-qa.py (chu duyet) truoc, khong sua lien ket' % aid)
    if mask_links(old_text) != mask_links(new_text):
        raise Refuse('POST_DIFF_NOT_LINKS_ONLY', '%s: bai moi khac bai cu o noi khac ngoai dich lien ket' % aid)
    new_post = new_text.encode('utf-8')
    d = Derived()
    d.aid, d.old_row, d.new_row, d.old_path, d.new_path = aid, row, row, path, path
    d.old_url = d.new_url = d.old_slug = d.new_slug = ''
    d.old_post, d.new_post, d.old_ev_bytes, d.old_ev, d.url_drift = old_post, new_post, old_ev_bytes, old_ev, False
    d.before = d.after = None
    d.entry = counts
    if not score:
        return d
    d.before = R.score_candidate(ctx, row, old_post)
    d.after = R.score_candidate(ctx, row, new_post)
    after = d.after
    if (after.get('content_sha256') != sha(new_post) or after.get('matrix_row_sha256') != A.fingerprint(row)
            or after.get('article_id') != aid or after.get('source_path') != path):
        raise Refuse('FRESH_QA_UNBOUND', '%s: diem cham khong buoc dung byte/hang ung vien' % aid)
    if not R.score_ok(after):
        failed = sorted(k for k, v in after.get('checks', {}).items() if not v)
        raise Refuse('FRESH_QA_NOT_ELIGIBLE', '%s: cham lai doc lap = %s q=%s s=%s (failed_checks=%s) — giu nguyen lien ket'
                     % (aid, after.get('result'), after.get('quality'), after.get('seo'), failed), failed_checks=failed)
    flipped = sorted(k for k, v in d.before.get('checks', {}).items() if v and not after.get('checks', {}).get(k))
    if flipped or after['quality'] < d.before.get('quality', 0) or after['seo'] < d.before.get('seo', 0):
        raise Refuse('REGRESSION', '%s: doi lien ket lam tut tieu chi %s hoac diem (q %s->%s, s %s->%s)'
                     % (aid, flipped, d.before.get('quality'), after['quality'], d.before.get('seo'), after['seo']),
                     flipped=flipped)
    return d


def build_links_evidence(ctx, d, mp_digest):
    old_ev = d.old_ev
    if not old_ev.get('scored_at'):
        raise Refuse('NO_HISTORICAL_SCORED_AT', '%s: evidence cu khong co scored_at lich su de giu' % d.aid)
    new = copy.deepcopy(d.after)
    for k in ('scored_at', 'published_at'):
        if old_ev.get(k):
            new[k] = old_ev[k]
    for k, v in old_ev.items():
        if k not in new and k != 'revision':
            new[k] = copy.deepcopy(v)
    history = []
    prev = old_ev.get('revision')
    if isinstance(prev, dict):
        history = list(prev.get('history') or []) + [{k: v for k, v in prev.items() if k != 'history'}]
    new['revision'] = {
        'schema': 'revision/1', 'kind': LINK_KIND, 'purpose': ctx.purpose, 'reason': ctx.reason,
        'approval_ref': ctx.approval_ref, 'batch_id': ctx.batch_id, 'revised_at': now_iso(),
        'previous_evidence_sha256': sha(d.old_ev_bytes),
        'previous_content_sha256': old_ev['content_sha256'], 'previous_matrix_row_sha256': old_ev['matrix_row_sha256'],
        'new_content_sha256': new['content_sha256'], 'mapping_sha256': mp_digest,
        'links_retargeted': sum(d.entry.values()), 'targets': dict(sorted(d.entry.items())),
        'previous_scores': {k: old_ev.get(k) for k in ('quality', 'seo', 'grade')},
        'scorer': new.get('scorer'), 'thresholds': {'quality_min': ctx.op.QUALITY_MIN, 'seo_min': ctx.op.SEO_MIN},
        'tool': 'scripts/factory/migrate-slug-urls.py links-apply', 'tool_commit': ctx.tool_commit, **code_sha(ctx),
        'note': ('chi doi DICH lien ket noi bo (chu lien ket, tieu de, # doan va moi byte khac giu nguyen); '
                 'scored_at/published_at o cap tren giu moc lich su goc; cham diem doc lap luc revised_at'),
    }
    if history:
        new['revision']['history'] = history
    return new


def compose_mapping(mp):
    """Gập chuỗi ánh xạ: A->B và B->C thành A->C (liên kết không bao giờ đáp xuống một URL sắp thành trang chuyển hướng).
    Vòng/tự trỏ (A->A, A->B->A) bị từ chối. Trả bản sao đã gập, khóa giữ nguyên."""
    out = {}
    for k in sorted(mp):
        seen, v = [k], mp[k]
        while v in mp and v != seen[-1]:
            if v in seen:
                raise Refuse('MAPPING_LOOP', 'anh xa co vong: %s' % ' -> '.join(seen + [v]))
            seen.append(v)
            v = mp[v]
        if v == k:
            raise Refuse('MAPPING_LOOP', 'anh xa tu tro: %s -> %s' % (k, v))
        out[k] = v
    return out


def default_mapping(root):
    """Ánh xạ mặc định pha 2: URL cũ -> mới theo registry (đã di trú), cả dạng thiếu '/' cuối của URL cũ
    (`](/a/b)` -> `/a/b-moi/` thẳng, không qua `/a/b/` rồi trang chuyển hướng). Khóa là TOKEN đầy đủ nên `/a/b` không khớp `/a/b/`."""
    mp = dict(mapping(pathlib.Path(root)))
    for old, new in list(mp.items()):
        if old.endswith('/') and old[:-1] and old[:-1] not in mp:
            mp[old[:-1]] = new
    return compose_mapping(mp)


_LINK_CTX = None
_LINK_MAP = None


def _links_worker(aid):
    try:
        d = derive_links(_LINK_CTX, aid, _LINK_MAP)
        return aid, links_entry(d), None
    except Refuse as e:
        return aid, None, {'id': aid, 'decision': e.code, 'reason': e.msg}


def links_entry(d):
    return {'id': d.aid, 'decision': ELIGIBLE, 'path': d.old_path, 'targets': dict(sorted(d.entry.items())),
            'base_post_sha256': sha(d.old_post), 'new_post_sha256': sha(d.new_post),
            'old_evidence_sha256': sha(d.old_ev_bytes), 'before': R.summary(d.before), 'after': R.summary(d.after),
            'before_scores': {'quality': d.before.get('quality'), 'seo': d.before.get('seo')}}


def candidate_ids(ctx, mp):
    """Quét rẻ (không chấm điểm): ID PUBLISHED có ít nhất một liên kết thuộc ánh xạ."""
    md, html = _link_res(mp)
    out = []
    for r in ctx.rows:
        if r['status'] != 'PUBLISHED' or not R.POST_RE.match(r.get('output_path') or ''):
            continue
        p = ctx.root / r['output_path']
        if not p.is_file():
            continue
        t = p.read_text(encoding='utf-8')
        if md.search(t) or html.search(t):
            out.append(r['id'])
    return sorted(out)


def make_links_plan(ctx, mp, ids=None, jobs=1):
    global _LINK_CTX, _LINK_MAP
    ids = sorted(ids if ids is not None else candidate_ids(ctx, mp))
    _LINK_CTX, _LINK_MAP = ctx, mp
    if jobs > 1:
        import multiprocessing
        with multiprocessing.get_context('fork').Pool(jobs) as pool:
            results = pool.map(_links_worker, ids, chunksize=8)
    else:
        results = [_links_worker(a) for a in ids]
    entries, excluded = {}, collections.defaultdict(list)
    for aid, ent, err in results:
        if ent is not None:
            entries[aid] = ent
        else:
            entries[aid] = err
            excluded[err['decision']].append(aid)
    eligible = sorted(i for i, e in entries.items() if e['decision'] == ELIGIBLE)
    return {
        'schema': LINK_MANIFEST_SCHEMA, 'authority': 'PROPOSAL ONLY — links-apply kiem lai moi dieu kien tu git + byte hien tai',
        'head': ctx.head, 'head_bound': True, 'matrix_sha256': sha((ctx.root / MATRIX_REL).read_bytes()),
        'thresholds': {'quality_min': ctx.op.QUALITY_MIN, 'seo_min': ctx.op.SEO_MIN}, **code_sha(ctx),
        'mapping': dict(sorted(mp.items())), 'mapping_sha256': mapping_digest(mp),
        'counts': {'mapping': len(mp), 'candidates': len(entries), 'eligible': len(eligible),
                   'links': sum(sum(e['targets'].values()) for e in entries.values() if e['decision'] == ELIGIBLE),
                   'decisions': dict(collections.Counter(e['decision'] for e in entries.values()))},
        'eligible': eligible, 'excluded': {k: sorted(v) for k, v in sorted(excluded.items())}, 'entries': entries,
    }


def check_links_manifest(manifest):
    if manifest.get('schema') != LINK_MANIFEST_SCHEMA:
        raise Refuse('BAD_MANIFEST', 'schema manifest khong dung')
    if not isinstance(manifest.get('entries'), dict) or not isinstance(manifest.get('eligible'), list) \
            or not isinstance(manifest.get('mapping'), dict):
        raise Refuse('BAD_MANIFEST', 'manifest thieu entries/eligible/mapping')
    if manifest.get('head_bound') is not True:
        raise Refuse('MANIFEST_NOT_HEAD_BOUND', 'manifest khong gan voi mot commit sach — chay lai links-plan tren cay sach')
    if manifest.get('mapping_sha256') != mapping_digest(manifest['mapping']):
        raise Refuse('BAD_MANIFEST', 'mapping_sha256 khong khop anh xa trong manifest')


def apply_links(ctx, manifest, ids, dry_run=False, skip_ineligible=False):
    if not (ctx.approval_ref or '').strip():
        raise Refuse('NO_APPROVAL', '--approval-ref la bat buoc (ghi vao provenance)')
    check_links_manifest(manifest)
    for k in ('scorer_code_sha256', 'business_facts_sha256', 'taxonomy_sha256'):
        if manifest.get(k) != code_sha(ctx).get(k):
            raise Refuse('SCORER_CHANGED_SINCE_PLAN', '%s khac manifest — chay lai links-plan' % k)
    ids = sorted(set(ids))
    if not ids:
        raise Refuse('NO_IDS', 'khong co ID nao duoc chon')
    if len(ids) > MAX_BATCH:
        raise Refuse('BATCH_TOO_LARGE', 'toi da %d ID/lo' % MAX_BATCH)
    if ctx.batch_id is not None and not R.BATCH_ID_RE.match(ctx.batch_id):
        raise Refuse('BAD_BATCH_ID', 'batch-id chi gom A-Za-z0-9._- (toi da 80 ky tu)')
    if not ctx.batch_id:
        ctx.batch_id = 'links-%s-%s-%s' % (datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d'), ids[0], ids[-1])
    ctx.purpose = 'internal-link-retarget'
    ctx.reason = ('Tro lien ket noi bo thang toi URL moi (sau di tru slug d -> d, hoac them dau / cuoi) thay vi qua trang chuyen '
                  'huong/301 cua may chu. Issue #77.')
    mp = manifest['mapping']
    prepared, skipped, ineligible = [], [], []
    for aid in ids:
        e = manifest['entries'].get(aid)
        try:
            if e is None or aid not in manifest['eligible'] or e.get('decision') != ELIGIBLE:
                raise Refuse('NOT_ELIGIBLE', '%s khong thuoc danh sach du dieu kien cua manifest' % aid)
            row = ctx.by_id.get(aid)
            cur = (ctx.root / row['output_path']).read_bytes() if row else b''
            if sha(cur) == e['new_post_sha256']:
                ev_now = ctx.root / 'data/qa' / (aid + '.json')
                if not ev_now.is_file() or json.loads(ev_now.read_text(encoding='utf-8')).get('content_sha256') != sha(cur):
                    raise Refuse('EVIDENCE_NOT_BOUND_TO_NEW_POST',
                                 '%s: bai da la ban moi nhung evidence khong khop byte (apply truoc bi ngat?) — khoi phuc bang '
                                 '`links-rollback --backup` roi chay lai, khong coi la xong' % aid)
                skipped.append(aid)                      # da la ban moi (evidence khop byte)
                continue
            if sha(cur) != e['base_post_sha256']:
                raise Refuse('POST_CHANGED_SINCE_PLAN', '%s: bai da doi tu luc plan' % aid)
            ev_p = ctx.root / 'data/qa' / (aid + '.json')
            if not ev_p.is_file() or sha(ev_p.read_bytes()) != e['old_evidence_sha256']:
                raise Refuse('EVIDENCE_CHANGED_SINCE_PLAN', '%s: evidence da doi tu luc plan' % aid)
            d = derive_links(ctx, aid, mp)
            if sha(d.new_post) != e['new_post_sha256'] or R.summary(d.after) != e['after']:
                raise Refuse('INPUT_CHANGED_SINCE_PLAN', '%s: byte/diem ung vien khac manifest' % aid)
            prepared.append(d)
        except Refuse as ex:
            if skip_ineligible and ex.code in SKIPPABLE + ('NO_LINKS',):
                ineligible.append({'id': aid, 'code': ex.code, 'reason': ex.msg})
                continue
            raise
    report = {'ok': True, 'batch_id': ctx.batch_id, 'dry_run': dry_run,
              'would_write' if dry_run else 'written': [d.aid for d in prepared],
              'already_current': skipped, 'skipped_ineligible': ineligible}
    if dry_run or not prepared:
        return report
    if ctx.guard:
        ctx.guard()
    root = ctx.root
    backup_rel = '%s/%s.json' % (LINK_BACKUP_DIR, ctx.batch_id)
    backup_path = root / backup_rel
    if backup_path.parent.resolve() != (root / LINK_BACKUP_DIR).resolve():
        raise Refuse('BAD_BATCH_ID', 'sao luu phai nam truc tiep trong %s' % LINK_BACKUP_DIR)
    if backup_path.exists():
        raise Refuse('BATCH_EXISTS', 'sao luu %s da ton tai — dung batch-id khac' % backup_rel)
    digest = mapping_digest(mp)
    backup = {'schema': LINK_BACKUP_SCHEMA, 'batch_id': ctx.batch_id, 'created_at': now_iso(), 'approval_ref': ctx.approval_ref,
              'purpose': ctx.purpose, 'reason': ctx.reason, 'head_at_apply': ctx.head, 'tool_commit': ctx.tool_commit,
              'mapping': {k: v for k, v in sorted(mp.items()) if any(k in d.entry for d in prepared)},
              'mapping_sha256': digest, 'entries': {}}
    blobs = {}
    for d in prepared:
        new_ev = build_links_evidence(ctx, d, digest)
        new_ev_bytes = R.evidence_text(new_ev).encode('utf-8')
        blobs[d.aid] = new_ev_bytes
        backup['entries'][d.aid] = {
            'path': d.old_path, 'targets': dict(sorted(d.entry.items())),
            'old_post_text': d.old_post.decode('utf-8'), 'old_post_sha256': sha(d.old_post), 'new_post_sha256': sha(d.new_post),
            'old_evidence_text': d.old_ev_bytes.decode('utf-8'), 'old_evidence_sha256': sha(d.old_ev_bytes),
            'new_evidence_sha256': sha(new_ev_bytes)}
    atomic_write(backup_path, doc_text(backup).encode('utf-8'))
    if json.loads(backup_path.read_text(encoding='utf-8')) != json.loads(doc_text(backup)):
        backup_path.unlink()
        raise Refuse('BACKUP_READBACK_FAILED', 'doc lai sao luu khong khop — chua sua file nao')
    attempted = []
    try:
        for d in prepared:
            post_p, ev_p = root / d.old_path, root / 'data/qa' / (d.aid + '.json')
            if post_p.read_bytes() != d.old_post or ev_p.read_bytes() != d.old_ev_bytes:
                raise Refuse('FILES_CHANGED_DURING_APPLY', '%s: bai/evidence doi trong luc apply' % d.aid)
            attempted.append(d.aid)
            atomic_write(post_p, d.new_post)
            atomic_write(ev_p, blobs[d.aid])
            if sha(post_p.read_bytes()) != sha(d.new_post) or sha(ev_p.read_bytes()) != sha(blobs[d.aid]):
                raise Refuse('WRITE_MISMATCH', '%s: doc lai khong khop' % d.aid)
        ctx2 = make_ctx(root, ctx.approval_ref, ctx.batch_id, ctx.purpose, ctx.reason)
        problems = verify_links_backup(ctx2, backup, rescore=True)
        if problems:
            raise Refuse('POST_VERIFY_FAILED', '; '.join(problems[:5]), problems=problems)
    except BaseException as exc:
        try:
            rollback_links(root, backup, ids=set(attempted), force=True)
        except BaseException:
            pass
        left = [a for a in attempted if (root / 'data/qa' / (a + '.json')).read_bytes().decode('utf-8') != backup['entries'][a]['old_evidence_text']
                or (root / backup['entries'][a]['path']).read_bytes().decode('utf-8') != backup['entries'][a]['old_post_text']]
        if left:
            raise Refuse('PARTIAL_APPLY_BACKUP_KEPT', 'apply loi (%s: %s) va chua ve byte cu: %s — GIU sao luu %s'
                         % (type(exc).__name__, exc, ', '.join(left[:5]), backup_path.name), left=left) from exc
        backup_path.unlink()
        raise
    report['backup'] = backup_rel
    return report


def check_links_backup_shape(backup):
    if backup.get('schema') != LINK_BACKUP_SCHEMA:
        raise Refuse('BAD_BACKUP', 'schema sao luu khong dung')
    if not isinstance(backup.get('entries'), dict) or not backup['entries'] or not isinstance(backup.get('mapping'), dict):
        raise Refuse('BAD_BACKUP', 'sao luu khong co entries/mapping')
    for aid, b in backup['entries'].items():
        if not R.AID_RE.match(aid) or not isinstance(b, dict) or not R.POST_RE.match(b.get('path', '')):
            raise Refuse('BAD_BACKUP', 'entry %r khong hop le' % (aid,))
        for k in ('old_post_text', 'old_post_sha256', 'new_post_sha256', 'old_evidence_text', 'old_evidence_sha256',
                  'new_evidence_sha256'):
            if not isinstance(b.get(k), str):
                raise Refuse('BAD_BACKUP', '%s: thieu %s' % (aid, k))


def verify_links_backup(ctx, backup, rescore=True):
    check_links_backup_shape(backup)
    problems = []
    root = ctx.root
    mp = backup['mapping']
    for aid, b in sorted(backup['entries'].items()):
        post_p, ev_p = root / b['path'], root / 'data/qa' / (aid + '.json')
        if not post_p.is_file() or not ev_p.is_file():
            problems.append('%s: thieu bai hoac evidence' % aid)
            continue
        post_raw, ev_raw = post_p.read_bytes(), ev_p.read_bytes()
        if sha(post_raw) != b['new_post_sha256']:
            problems.append('%s: bai khac ban da ghi' % aid)
            continue
        if sha(ev_raw) != b['new_evidence_sha256']:
            problems.append('%s: evidence khac ban da ghi' % aid)
            continue
        old_text = b['old_post_text']
        if sha(old_text.encode('utf-8')) != b['old_post_sha256']:
            problems.append('%s: sao luu bai cu hong' % aid)
            continue
        replay, counts = retarget_text(old_text, mp)
        if replay.encode('utf-8') != post_raw:
            problems.append('%s: bai hien tai != bai cu + doi dich lien ket theo anh xa' % aid)
        if mask_links(old_text) != mask_links(post_raw.decode('utf-8')):
            problems.append('%s: bai doi o noi khac ngoai dich lien ket' % aid)
        if counts != b['targets']:
            problems.append('%s: so lien ket da doi khac sao luu' % aid)
        ev = json.loads(ev_raw)
        row = ctx.by_id.get(aid)
        if row is None or row['status'] != 'PUBLISHED' or row.get('output_path') != b['path']:
            problems.append('%s: khong con PUBLISHED / output_path doi' % aid)
            continue
        if ev.get('content_sha256') != sha(post_raw):
            problems.append('%s: content_sha256 khong khop bai hien tai' % aid)
        if ev.get('matrix_row_sha256') != A.fingerprint(row):
            problems.append('%s: matrix_row_sha256 khong khop hang hien tai' % aid)
        if ev.get('source_path') != row['output_path'] or ev.get('article_id') != aid:
            problems.append('%s: source_path/article_id trong evidence sai' % aid)
        if not R.score_ok(ev):
            problems.append('%s: diem/cong QA khong dat nguong' % aid)
        rev = ev.get('revision') or {}
        old_ev = json.loads(b['old_evidence_text'])
        old_ev_sha = sha(b['old_evidence_text'].encode('utf-8'))
        if (b['old_evidence_sha256'] != old_ev_sha or rev.get('kind') != LINK_KIND
                or rev.get('previous_evidence_sha256') != old_ev_sha
                or rev.get('previous_content_sha256') != old_ev.get('content_sha256')
                or rev.get('previous_matrix_row_sha256') != old_ev.get('matrix_row_sha256')
                or rev.get('new_content_sha256') != ev.get('content_sha256')
                or rev.get('mapping_sha256') != backup.get('mapping_sha256')
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


def rollback_links(root, backup, ids=None, dry_run=False, force=False):
    check_links_backup_shape(backup)
    root = pathlib.Path(root)
    if ids is not None:
        unknown = sorted(set(ids) - set(backup['entries']))
        if unknown:
            raise Refuse('UNKNOWN_IDS', 'ID khong co trong sao luu: %s' % unknown[:5])
    out = {'restored': [], 'skipped_changed_since_apply': [], 'dry_run': dry_run}
    for aid, b in sorted(backup['entries'].items()):
        if ids is not None and aid not in ids:
            continue
        old_post, old_ev = b['old_post_text'].encode('utf-8'), b['old_evidence_text'].encode('utf-8')
        if sha(old_post) != b['old_post_sha256'] or sha(old_ev) != b['old_evidence_sha256']:
            raise Refuse('BACKUP_CORRUPT', '%s: sao luu hong' % aid)
        post_p, ev_p = root / b['path'], root / 'data/qa' / (aid + '.json')
        plan = []
        for p, old, new_sha, old_sha in ((post_p, old_post, b['new_post_sha256'], b['old_post_sha256']),
                                         (ev_p, old_ev, b['new_evidence_sha256'], b['old_evidence_sha256'])):
            cur = sha(p.read_bytes()) if p.is_file() else None
            if cur == old_sha:
                continue
            if cur != new_sha and not force:
                plan = None
                break
            plan.append((p, old))
        if plan is None:
            out['skipped_changed_since_apply'].append(aid)
            continue
        if plan:
            if not dry_run:
                for p, old in plan:
                    atomic_write(p, old)
                    if sha(p.read_bytes()) != sha(old):
                        raise Refuse('ROLLBACK_MISMATCH', '%s: khoi phuc khong khop' % aid)
            out['restored'].append(aid)
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
    p.add_argument('--jobs', type=int, default=1)
    p.add_argument('--allow-dirty', action='store_true')
    a_ = sub.add_parser('apply')
    a_.add_argument('--manifest', required=True)
    a_.add_argument('--approval-ref', default='')
    a_.add_argument('--ids', default='')
    a_.add_argument('--limit', type=int, default=0)
    a_.add_argument('--offset', type=int, default=0)
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
    rd = sub.add_parser('refresh-data')
    rd.add_argument('--check', action='store_true')
    lp = sub.add_parser('links-plan')
    lp.add_argument('--out')
    lp.add_argument('--mapping', default='', help='JSON {dich_cu: dich_moi} bo sung (vd them dau / cuoi)')
    lp.add_argument('--no-registry', action='store_true', help='khong dung anh xa registry mac dinh')
    lp.add_argument('--ids', default='')
    lp.add_argument('--jobs', type=int, default=1)
    lp.add_argument('--allow-dirty', action='store_true')
    la = sub.add_parser('links-apply')
    la.add_argument('--manifest', required=True)
    la.add_argument('--approval-ref', default='')
    la.add_argument('--ids', default='')
    la.add_argument('--limit', type=int, default=0)
    la.add_argument('--offset', type=int, default=0)
    la.add_argument('--batch-id', default=None)
    la.add_argument('--dry-run', action='store_true')
    la.add_argument('--skip-ineligible', action='store_true')
    lv = sub.add_parser('links-verify')
    lv.add_argument('--backup', required=True)
    lv.add_argument('--no-rescore', action='store_true')
    lr = sub.add_parser('links-rollback')
    lr.add_argument('--backup', required=True)
    lr.add_argument('--ids', default=None)
    lr.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'plan':
            out_path = os.path.abspath(a.out) if a.out else None
            dirty = A.dirty_inputs(ROOT)
            if dirty and not a.allow_dirty:
                R.require_clean_tree(ROOT)
            ctx = make_ctx(ROOT)
            manifest = make_plan(ctx, _ids(a.ids) or None, max(1, a.jobs))
            manifest['head_bound'] = not dirty
            text = doc_text(manifest)
            if out_path:
                atomic_write(out_path, text.encode('utf-8'))
                print(json.dumps({'ok': True, 'out': out_path, 'counts': manifest['counts'],
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
                elig = sorted(manifest['eligible'])
                if a.limit <= 0:
                    raise Refuse('NO_IDS', 'can --ids hoac --limit N [--offset K]')
                ids = elig[a.offset:a.offset + a.limit]
            ctx = make_ctx(ROOT, a.approval_ref, a.batch_id)
            ctx.guard = lambda: R.require_clean_tree(ROOT)
            print(json.dumps(apply_batch(ctx, manifest, ids, a.dry_run, a.skip_ineligible), ensure_ascii=False, indent=2))
            return 0
        if a.cmd == 'links-plan':
            out_path = os.path.abspath(a.out) if a.out else None
            extra = json.loads(pathlib.Path(a.mapping).read_text(encoding='utf-8')) if a.mapping else {}
            dirty = A.dirty_inputs(ROOT)
            if dirty and not a.allow_dirty:
                R.require_clean_tree(ROOT)
            ctx = make_ctx(ROOT)
            mp = compose_mapping(dict(extra if a.no_registry else {**default_mapping(ROOT), **extra}))
            if not mp:
                raise Refuse('EMPTY_MAPPING', 'anh xa rong (chua di tru bai nao va khong co --mapping)')
            manifest = make_links_plan(ctx, mp, _ids(a.ids) or None, max(1, a.jobs))
            manifest['head_bound'] = not dirty
            if out_path:
                atomic_write(out_path, doc_text(manifest).encode('utf-8'))
                print(json.dumps({'ok': True, 'out': out_path, 'counts': manifest['counts'],
                                  'excluded': {k: len(x) for k, x in manifest['excluded'].items()}}, ensure_ascii=False, indent=2))
            else:
                print(doc_text(manifest), end='')
            return 0
        if a.cmd == 'links-apply':
            manifest = json.loads(pathlib.Path(a.manifest).read_text(encoding='utf-8'))
            R.require_clean_tree(ROOT)
            check_links_manifest(manifest)
            ids = _ids(a.ids)
            if not ids:
                if a.limit <= 0:
                    raise Refuse('NO_IDS', 'can --ids hoac --limit N [--offset K]')
                ids = sorted(manifest['eligible'])[a.offset:a.offset + a.limit]
            ctx = make_ctx(ROOT, a.approval_ref, a.batch_id)
            ctx.guard = lambda: R.require_clean_tree(ROOT)
            print(json.dumps(apply_links(ctx, manifest, ids, a.dry_run, a.skip_ineligible), ensure_ascii=False, indent=2))
            return 0
        if a.cmd in ('links-verify', 'links-rollback'):
            backup = json.loads(pathlib.Path(a.backup).read_text(encoding='utf-8'))
            if a.cmd == 'links-verify':
                problems = verify_links_backup(make_ctx(ROOT), backup, rescore=not a.no_rescore)
                print(json.dumps({'ok': not problems, 'checked': len(backup['entries']), 'problems': problems},
                                 ensure_ascii=False, indent=2))
                return 0 if not problems else 1
            ids = set(_ids(a.ids)) if a.ids is not None else None
            if a.ids is not None and not ids:
                raise Refuse('BAD_IDS', '--ids rong: bo --ids de khoi phuc ca lo')
            out = rollback_links(ROOT, backup, ids, a.dry_run)
            out['ok'] = not out.get('skipped_changed_since_apply')
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0 if out['ok'] else 1
        if a.cmd == 'refresh-data':
            changed = refresh_data(ROOT, a.check)
            print(json.dumps({'ok': not (a.check and changed), 'changed' if not a.check else 'stale': changed},
                             ensure_ascii=False, indent=2))
            return 1 if (a.check and changed) else 0
        backup = json.loads(pathlib.Path(a.backup).read_text(encoding='utf-8'))
        if a.cmd == 'verify':
            ctx = make_ctx(ROOT)
            problems = verify_backup(ctx, backup, rescore=not a.no_rescore)
            print(json.dumps({'ok': not problems, 'checked': len(backup['entries']), 'problems': problems},
                             ensure_ascii=False, indent=2))
            return 0 if not problems else 1
        ids = None
        if a.ids is not None:
            ids = set(_ids(a.ids))
            if not ids:
                raise Refuse('BAD_IDS', '--ids rong: bo --ids de khoi phuc ca lo')
        out = rollback_backup(ROOT, backup, ids, a.dry_run)
        out['ok'] = not out['skipped_changed_since_apply']        # có ID bị bỏ qua (đã đổi sau apply) = chưa khôi phục hết
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out['ok'] else 1
    except Refuse as e:
        d = {'ok': False, 'code': e.code, 'error': e.msg}
        d.update(e.extra)
        print(json.dumps(d, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
