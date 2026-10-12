#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-attest CÓ KIỂM SOÁT bằng chứng QA CŨ lệch hash vì migrate domain.

Bối cảnh: sau migration v3 (04d46bef: đổi domain + bỏ tiền tố /blog/) ~1.069
bài PUBLISHED có `data/qa/<ID>.json` lệch `content_sha256` / `matrix_row_sha256`
(`validate --scope batch|full` đỏ). `audit-legacy-qa.py` CHỈ ĐỌC phân loại; tool
này là đường GHI duy nhất, và chỉ cho bài thỏa MỌI điều kiện:

  1. DOMAIN_ONLY_PROVEN: hash cũ trong evidence buộc đúng byte bài + hàng matrix
     của commit baseline (bất biến), và exact-transform v3 (đổi domain + bỏ
     /blog/) của baseline cho ĐÚNG byte/trường hiện tại. Không chuẩn hóa
     khoảng trắng/văn xuôi, không so khớp mờ.
  2. Chấm điểm ĐỘC LẬP: scorer canonical `factory-operator.qa_check_one` chạy lại
     trên byte bài hiện tại (corpus/taxonomy/business-facts hiện tại), KHÔNG dùng
     lại điểm/kết quả của evidence cũ. Ngưỡng 75/70, business_fact, legal,
     critical_failure KHÔNG đổi — thiếu một cổng là KHÔNG re-attest.
  3. Có chủ duyệt (`--approval-ref` bắt buộc, ghi vào provenance) và manifest.

Kết quả ghi (CHỈ `data/qa/<ID>.json` của ID được duyệt + một file sao lưu):
  * evidence mới = đầu ra scorer mới + khối `reattestation` (provenance đầy đủ:
    hash evidence cũ, hash cũ, baseline, bằng chứng domain-only, thời điểm/mã
    scorer, business-facts/taxonomy hash, người duyệt). `scored_at` /
    `published_at` GIỮ mốc lịch sử gốc (watchdog đọc chúng như tín hiệu hoạt
    động: re-attest không được tạo hoạt động giả); thời điểm chấm lại nằm ở
    `reattestation.rescored_at`.
  * sao lưu `reports/qa-audit/reattest/<batch>.json` chứa NGUYÊN VĂN evidence cũ
    + sha256 cũ/mới của từng ID, ghi và đọc lại TRƯỚC khi sửa bất kỳ evidence nào.
  * KHÔNG đụng `_posts/`, matrix, checkpoint, lease, bài/draft. Ca không đủ điều
    kiện (chấm lại FAIL, nội dung/matrix đổi thật, baseline không buộc) GIỮ
    NGUYÊN để xử lý riêng — tool từ chối, không có cờ ép.

Rào do TOOL tự giữ (không tin repo): sàn 75/70 cứng (scorer thấp hơn => THRESHOLD_BELOW_FLOOR),
baseline ghim 1b55bd81 và phải là tiền bối của HEAD, manifest phải lập bởi cùng baseline/scorer/
facts/taxonomy/ngưỡng (SCORER_CHANGED_SINCE_PLAN), ID/batch-id/output_path được kiểm cú pháp,
mỗi file evidence được compare-and-swap trước khi ghi, apply lỗi giữa chừng trả MỌI ID đã bắt đầu
ghi về byte cũ (chỉ xóa sao lưu khi tất cả đã về, nếu không giữ: PARTIAL_APPLY_BACKUP_KEPT),
`verify` chấm lại độc lập từng ID (--no-rescore: chỉ cấu trúc), evidence cũ không có scored_at lịch
sử bị từ chối, chú thích lịch sử của evidence cũ được chép sang `reattestation`.

Chốt cây sạch: kết quả chấm điểm chỉ quy được cho một commit khi mọi đầu vào (matrix,
bài, evidence, scorer, business-facts, taxonomy) đúng bằng HEAD. `plan` và `apply` TỪ
CHỐI (DIRTY_TREE) khi cây làm việc khác HEAD (cùng phép kiểm với audit-legacy-qa.py);
`plan --allow-dirty` là lối thoát tường minh và đánh dấu manifest `head_bound: false`,
loại manifest đó khỏi `apply` (MANIFEST_NOT_HEAD_BOUND). Mỗi batch = một commit rồi mới
đến batch sau. `verify`/`rollback` không bị chốt này (rollback phải chạy được trên cây bẩn).

Lệnh:
  plan     --baseline <commit> [--out FILE] [--allow-dirty]   proposal (không ghi evidence)
  apply    --manifest FILE --approval-ref TEXT (--ids A,B | --limit N [--offset K])
           [--batch-id ID] [--dry-run]            kiểm lại TẤT CẢ rồi ghi (batch ≤ 300)
           [--skip-ineligible]                    ID het du dieu kien luc apply bi BO QUA (bao cao)
  verify   --backup FILE                          kiểm evidence đã ghi + provenance
  rollback --backup FILE [--ids A,B] [--dry-run]  khôi phục byte-exact evidence cũ
                                                  (chỉ khi file còn đúng bản đã ghi)

Manifest của `plan` KHÔNG có hiệu lực pháp lý: `apply` tự kiểm lại mọi điều kiện
từ git + byte hiện tại; manifest bị sửa/lỗi thời chỉ làm `apply` TỪ CHỐI. Một ID
không đạt thì CẢ batch dừng, chưa ghi gì (nguyên tử). Chạy lặp lại là no-op.
Hash chứng minh toàn vẹn/provenance, không phải xác thực tác giả: quyền ghi repo
vẫn do review PR + CI + lịch sử git bất biến bảo vệ.
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
MANIFEST_SCHEMA = 'reattest-manifest/1'
BACKUP_SCHEMA = 'reattest-backup/1'
BACKUP_DIR = 'reports/qa-audit/reattest'
ELIGIBLE = 'ELIGIBLE_PROPOSAL_AWAITING_OWNER_APPROVAL'
MAX_BATCH = 300
# Rao CUNG — khong lay tu repo (scorer/manifest/baseline la thu tool khong duoc tin):
FLOOR_QUALITY, FLOOR_SEO = 75, 70
# Baseline bat bien cua migration v3 (cha cua 04d46bef). Chi baseline nay duoc chap nhan.
PINNED_BASELINE = '1b55bd810aac85dc919eb2a43d71de30ad8d4595'
BATCH_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z')
AID_RE = re.compile(r'^BLG-[0-9]+\Z')            # ASCII only (\d would match other scripts' digits)
POST_RE = re.compile(r'^_posts/[^/]+\.md\Z')
# Khoa lich su/provenance cua evidence: KHONG so voi diem cham lai.
PROVENANCE_KEYS = ('reattestation', 'scored_at', 'published_at')
# Trường buộc manifest với hiện trạng; lệch bất kỳ trường nào => TỪ CHỐI.
BINDING = ('classification', 'old_evidence_sha256', 'current_content_sha256',
           'current_matrix_sha256', 'recorded_content_sha256',
           'recorded_matrix_sha256', 'baseline_content_sha256',
           'baseline_matrix_sha256')
# Tu choi theo TRANG THAI HIEN TAI cua tung ID (bai/evidence/corpus doi tu luc plan,
# cham lai khong dat...). Voi --skip-ineligible chung chi lam ID do bi BO QUA (bao cao
# ro); cac loi chon sai (NOT_ELIGIBLE, thieu evidence) luon dung ca batch.
SKIPPABLE = ('NOT_PUBLISHED', 'EVIDENCE_CHANGED_SINCE_PLAN', 'INPUT_CHANGED_SINCE_PLAN',
             'NOT_DOMAIN_ONLY', 'FRESH_QA_NOT_ELIGIBLE', 'UNEXPECTED_CURRENT_EVIDENCE')
FRESH_FIELDS = ('result', 'quality', 'seo', 'business_fact', 'legal',
                'critical_failure')


class Refuse(Exception):
    def __init__(self, code, msg, **extra):
        super().__init__(msg)
        self.code, self.msg, self.extra = code, msg, extra


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(filename) if os.path.isabs(str(filename)) else HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


A = _load('legacy_audit_for_reattest', 'audit-legacy-qa.py')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%S+00:00')


def evidence_text(obj):
    """Đúng định dạng `factory-operator.write_json_atomic` (indent=2)."""
    return json.dumps(obj, ensure_ascii=False, indent=2)


def doc_text(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n'


def atomic_write(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.reattest.tmp')
    try:
        with open(tmp, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()                      # khong de lai *.reattest.tmp
        except FileNotFoundError:
            pass
        raise
    try:                                      # ben vung ten file moi (fsync thu muc)
        fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def git_out(root, *args):
    r = subprocess.run(['git'] + list(args), cwd=str(root),
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


class Ctx:
    """Mọi đầu vào của một lần chạy (tiêm được cho test)."""

    def __init__(self, root, history, baseline, op, biz, tax,
                 approval_ref='', batch_id=None, head=None, tool_commit=None):
        self.root = pathlib.Path(root)
        self.history = history
        self.baseline = baseline
        self.op, self.biz, self.tax = op, biz, tax
        self.approval_ref = approval_ref
        self.batch_id = batch_id
        self.head, self.tool_commit = head, tool_commit
        self.guard = None        # callable kiem lai cay sach NGAY TRUOC khi ghi (CLI dat)
        self.rows = read_rows(self.root)
        self.by_id = {r['id']: r for r in self.rows}
        self.old_rows = {r['id']: r for r in csv.DictReader(io.StringIO(
            history['data/content-matrix.csv'].decode('utf-8')))} \
            if history.get('data/content-matrix.csv') else {}
        self.code_sha = {
            'scorer_code_sha256': sha((self.root / 'scripts/factory/factory-operator.py').read_bytes()),
            'business_facts_sha256': sha((self.root / 'data/business-facts.json').read_bytes()),
            'taxonomy_sha256': sha((self.root / 'data/content-taxonomy.json').read_bytes()),
        }


def read_rows(root):
    with open(pathlib.Path(root) / 'data/content-matrix.csv',
              encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def make_ctx(root, baseline, approval_ref='', batch_id=None, history=None):
    root = pathlib.Path(root)
    os.chdir(root)               # scorer đọc đường dẫn tương đối từ gốc repo
    commit = baseline
    if history is None:
        commit = git_out(root, 'rev-parse', '--verify', baseline + '^{commit}')
        if not commit:
            raise Refuse('BAD_BASELINE', 'baseline %r khong phai commit' % baseline)
        if commit != PINNED_BASELINE:
            raise Refuse('BASELINE_NOT_PINNED',
                         'chi baseline bat bien %s duoc chap nhan (nhan %s)' % (PINNED_BASELINE, commit))
        if subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'],
                          cwd=str(root), capture_output=True).returncode != 0:
            raise Refuse('BASELINE_NOT_ANCESTOR', 'baseline %s khong phai tien boi cua HEAD' % commit)
        history = A.historical_blobs(commit)
    op = _load('operator_for_reattest', str(root / 'scripts/factory/factory-operator.py'))
    if op.QUALITY_MIN < FLOOR_QUALITY or op.SEO_MIN < FLOOR_SEO:
        # Nguong la thu tool KHONG duoc ha, du repo (scorer) noi gi: chan cua rieng tool.
        raise Refuse('THRESHOLD_BELOW_FLOOR',
                     'scorer co nguong %s/%s thap hon san %s/%s — khong re-attest'
                     % (op.QUALITY_MIN, op.SEO_MIN, FLOOR_QUALITY, FLOOR_SEO))
    biz = json.loads((root / 'data/business-facts.json').read_text(encoding='utf-8'))
    tax = json.loads((root / 'data/content-taxonomy.json').read_text(encoding='utf-8'))
    # qa_check_one doc APPROVED_AMOUNTS (module-global) do build_amount_whitelist
    # dien — giong factory-operator.main / writer-loop. Thieu buoc nay moi so tien
    # deu bi coi la chua duyet (FAIL gia). Goi tuong minh, khong chi trong audit.
    op.build_amount_whitelist(biz)
    return Ctx(root, history, commit, op, biz, tax, approval_ref, batch_id,
               head=git_out(root, 'rev-parse', 'HEAD'),
               tool_commit=git_out(root, 'rev-parse', 'HEAD'))


# ------------------------------------------------------------------ đánh giá

def evaluate(ctx, row):
    """Đánh giá MỘT hàng PUBLISHED từ đầu (không tin manifest/evidence cũ).
    Trả (entry, fresh|None). Thuần đọc."""
    aid = row['id']
    qa_path = 'data/qa/%s.json' % aid
    ev_bytes = (ctx.root / qa_path).read_bytes()
    evidence = json.loads(ev_bytes)
    current = (ctx.root / row['output_path']).read_bytes()
    old_row = ctx.old_rows.get(aid)
    old_bytes = ctx.history.get(old_row['output_path']) if old_row else None
    old_ev = json.loads(ctx.history[qa_path]) if qa_path in ctx.history else None
    cl = A.classify(row, current, evidence, old_row, old_bytes, old_ev)
    entry = {
        'id': aid, 'path': row['output_path'],
        'classification': cl['classification'],
        'old_evidence_sha256': sha(ev_bytes),
        'current_content_sha256': cl['current_content_sha256'],
        'current_matrix_sha256': cl['current_matrix_sha256'],
        'recorded_content_sha256': cl['recorded_content_sha256'],
        'recorded_matrix_sha256': cl['recorded_matrix_sha256'],
        'baseline_content_sha256': cl.get('baseline_content_sha256'),
        'baseline_matrix_sha256': cl.get('baseline_matrix_sha256'),
    }
    if cl['classification'] == 'CURRENT_HASHES_MATCH':
        entry['decision'] = 'NOTHING_TO_DO'
        return entry, None
    if cl['classification'] != 'DOMAIN_ONLY_PROVEN':
        entry['decision'] = 'MANUAL_REVIEW_REQUIRED'
        return entry, None
    fresh = A.rescore_published(ctx.op, row, ctx.rows, ctx.biz, ctx.tax)
    entry['fresh_qa'] = {k: fresh.get(k) for k in FRESH_FIELDS}
    entry['failed_checks'] = sorted(k for k, v in fresh.get('checks', {}).items() if not v)
    entry['decision'] = A.proposal_decision(
        cl['classification'], fresh, current, row, ctx.op.QUALITY_MIN, ctx.op.SEO_MIN)
    return entry, fresh


def make_plan(ctx, ids=None, head_bound=True):
    entries, excluded = {}, collections.defaultdict(list)
    for row in ctx.rows:
        if row['status'] != 'PUBLISHED' or (ids and row['id'] not in ids):
            continue
        entry, _ = evaluate(ctx, row)
        if entry['decision'] == 'NOTHING_TO_DO':
            continue
        entries[row['id']] = entry
        if entry['decision'] != ELIGIBLE:
            excluded[entry['decision'] + ('/' + entry['classification']
                     if entry['decision'] == 'MANUAL_REVIEW_REQUIRED' else '')].append(row['id'])
    eligible = sorted(i for i, e in entries.items() if e['decision'] == ELIGIBLE)
    return {
        'schema': MANIFEST_SCHEMA,
        'authority': 'PROPOSAL ONLY — apply kiem lai moi dieu kien tu git + byte hien tai',
        'baseline_commit': ctx.baseline, 'head': ctx.head,
        # True chi khi cay lam viec == HEAD luc plan (plan --allow-dirty => False;
        # apply tu choi manifest khong gan voi mot commit)
        'head_bound': bool(head_bound),
        'matrix_sha256': sha((ctx.root / 'data/content-matrix.csv').read_bytes()),
        'thresholds': {'quality_min': ctx.op.QUALITY_MIN, 'seo_min': ctx.op.SEO_MIN},
        **ctx.code_sha,
        'counts': {'stale': len(entries), 'eligible': len(eligible),
                   'classifications': dict(collections.Counter(
                       e['classification'] for e in entries.values())),
                   'decisions': dict(collections.Counter(
                       e['decision'] for e in entries.values()))},
        'eligible': eligible,
        'excluded': {k: sorted(v) for k, v in sorted(excluded.items())},
        'entries': entries,
    }


# --------------------------------------------------------------------- apply

_MISSING = object()


def score_diff(evidence, fresh):
    """Khoa khac nhau giua evidence tren dia va diem scorer cham lai (bo qua khoa
    lich su/provenance). Rong = evidence dung la dau ra cua scorer cho byte/hang nay."""
    a = {k: v for k, v in evidence.items() if k not in PROVENANCE_KEYS}
    b = {k: v for k, v in fresh.items() if k not in PROVENANCE_KEYS}
    return sorted(k for k in set(a) | set(b) if a.get(k, _MISSING) != b.get(k, _MISSING))


def build_new_evidence(ctx, e, fresh, old_ev):
    if not old_ev.get('scored_at'):
        # scored_at moi = bay gio se bi watchdog doc nhu hoat dong gia: khong re-attest.
        raise Refuse('NO_HISTORICAL_SCORED_AT',
                     '%s: evidence cu khong co scored_at lich su de giu' % e['id'])
    new = copy.deepcopy(fresh)
    for k in ('scored_at', 'published_at'):       # mốc lịch sử: giữ nguyên
        if old_ev.get(k):
            new[k] = old_ev[k]
    # Trường chú thích LỊCH SỬ mà scorer không sinh ra (post_publish_repair, hash_sync_note,
    # rescore_note, restamped_note...): sao nguyên văn sang khối reattestation de nguoi doc
    # evidence moi van thay "evidence cu tung bi re-stamp/sua sau xuat ban". Khong mat dau vet.
    carried = {k: copy.deepcopy(v) for k, v in old_ev.items()
               if k not in new and k != 'reattestation'}
    new['reattestation'] = {
        'schema': 'reattestation/1',
        'kind': 'domain-migration-v3',
        'classification': 'DOMAIN_ONLY_PROVEN',
        'proof': ('hash cu trong evidence buoc dung byte bai + hang matrix cua '
                  'baseline bat bien; exact-transform v3 (doi domain + bo '
                  '/blog/) cua baseline == byte/truong hien tai'),
        'approval_ref': ctx.approval_ref,
        'batch_id': ctx.batch_id,
        'rescored_at': now_iso(),
        'baseline_commit': ctx.baseline,
        'previous_evidence_path': 'data/qa/%s.json' % e['id'],
        'previous_evidence_sha256': e['old_evidence_sha256'],
        'previous_content_sha256': e['recorded_content_sha256'],
        'previous_matrix_row_sha256': e['recorded_matrix_sha256'],
        'scorer': fresh.get('scorer'),
        'thresholds': {'quality_min': ctx.op.QUALITY_MIN, 'seo_min': ctx.op.SEO_MIN},
        'tool': 'scripts/factory/reattest-legacy-qa.py',
        'tool_commit': ctx.tool_commit,
        'tool_sha256': sha(pathlib.Path(__file__).read_bytes()),
        **ctx.code_sha,
        'note': ('scored_at/published_at o cap tren giu moc lich su goc '
                 '(watchdog doc chung nhu tin hieu hoat dong); chat diem '
                 'doc lap xay ra luc rescored_at'),
    }
    if carried:
        new['reattestation']['previous_evidence_annotations'] = carried
    return new


def prepare(ctx, manifest, aid):
    """Kiểm lại MỌI điều kiện cho một ID. Trả ('ready'|'already_current', ...)
    hoặc Refuse — không bao giờ ghi."""
    e = manifest['entries'].get(aid)
    if e is None or aid not in manifest['eligible']:
        raise Refuse('NOT_ELIGIBLE', '%s khong thuoc danh sach du dieu kien cua manifest' % aid)
    e = dict(e, id=aid)               # id dung la khoa da kiem, khong phai gia tri manifest tu khai
    row = ctx.by_id.get(aid)
    if row is None or row['status'] != 'PUBLISHED':
        raise Refuse('NOT_PUBLISHED', '%s khong phai hang PUBLISHED' % aid)
    if not POST_RE.match(row.get('output_path') or ''):
        raise Refuse('BAD_OUTPUT_PATH', '%s: output_path %r khong nam trong _posts/' % (aid, row.get('output_path')))
    ev_path = ctx.root / 'data/qa' / (aid + '.json')
    if not ev_path.is_file():
        raise Refuse('NO_EVIDENCE', '%s khong co evidence' % aid)
    ev_bytes = ev_path.read_bytes()
    evidence = json.loads(ev_bytes)
    current = (ctx.root / row['output_path']).read_bytes()
    if sha(current) == evidence.get('content_sha256') \
            and A.fingerprint(row) == evidence.get('matrix_row_sha256'):
        prov = evidence.get('reattestation') or {}
        if prov.get('previous_evidence_sha256') == e['old_evidence_sha256']:
            # tu khai provenance khong du: diem tren dia phai dung la dau ra scorer
            diff = score_diff(evidence, A.rescore_published(ctx.op, row, ctx.rows, ctx.biz, ctx.tax))
            if diff or evidence.get('article_id') != aid:
                raise Refuse('UNEXPECTED_CURRENT_EVIDENCE',
                             '%s: evidence khop hash + provenance nhung diem khac cham lai doc lap '
                             '(%s) — khong coi la da re-attest' % (aid, ', '.join(diff[:6])))
            return 'already_current', ev_bytes, None
        raise Refuse('UNEXPECTED_CURRENT_EVIDENCE',
                     '%s: evidence da khop hash nhung khong phai ket qua re-attest '
                     'cua manifest nay — khong ghi de' % aid)
    if sha(ev_bytes) != e['old_evidence_sha256']:
        raise Refuse('EVIDENCE_CHANGED_SINCE_PLAN', '%s: evidence da doi tu luc plan' % aid)
    entry, fresh = evaluate(ctx, row)
    for k in BINDING:
        if entry.get(k) != e.get(k):
            raise Refuse('INPUT_CHANGED_SINCE_PLAN',
                         '%s: %s khac manifest (bai/hang/baseline da doi)' % (aid, k))
    if entry['classification'] != 'DOMAIN_ONLY_PROVEN':
        raise Refuse('NOT_DOMAIN_ONLY', '%s: %s' % (aid, entry['classification']))
    if entry['decision'] != ELIGIBLE or fresh is None:
        raise Refuse('FRESH_QA_NOT_ELIGIBLE',
                     '%s: cham lai doc lap = %s (failed_checks=%s) — giu nguyen de xu ly rieng'
                     % (aid, entry['decision'], entry.get('failed_checks')),
                     failed_checks=entry.get('failed_checks'))
    return 'ready', ev_bytes, build_new_evidence(ctx, e, fresh, evidence)


def check_manifest(manifest):
    if manifest.get('schema') != MANIFEST_SCHEMA:
        raise Refuse('BAD_MANIFEST', 'schema manifest khong dung')
    if not isinstance(manifest.get('entries'), dict) or not isinstance(manifest.get('eligible'), list):
        raise Refuse('BAD_MANIFEST', 'manifest thieu entries/eligible')
    if manifest.get('head_bound') is not True:
        raise Refuse('MANIFEST_NOT_HEAD_BOUND',
                     'manifest khong gan voi mot commit sach (plan --allow-dirty, hoac ban cu '
                     'khong co head_bound) — chay lai plan tren cay lam viec sach')


def check_manifest_current(ctx, manifest):
    """Manifest phai lap bang CUNG baseline/scorer/facts/taxonomy/nguong voi hien tai:
    khac => scorer/du lieu da doi tu luc plan, chay lai plan (fail-closed)."""
    if manifest.get('baseline_commit') != ctx.baseline:
        raise Refuse('MANIFEST_BASELINE_MISMATCH',
                     'manifest lap tren baseline %s, hien tai %s' % (manifest.get('baseline_commit'), ctx.baseline))
    for k, v in ctx.code_sha.items():
        if manifest.get(k) != v:
            raise Refuse('SCORER_CHANGED_SINCE_PLAN', '%s khac manifest (scorer/facts/taxonomy da doi) — chay lai plan' % k)
    if manifest.get('thresholds') != {'quality_min': ctx.op.QUALITY_MIN, 'seo_min': ctx.op.SEO_MIN}:
        raise Refuse('SCORER_CHANGED_SINCE_PLAN', 'nguong QA khac manifest — chay lai plan')


def require_clean_tree(root=ROOT):
    """Cay lam viec phai bang HEAD (cung phep kiem voi audit-legacy-qa.py): diem chi
    quy duoc cho mot commit khi matrix/bai/evidence/scorer/facts/taxonomy dung la cua no."""
    dirty = A.dirty_inputs(root)
    if dirty:
        raise Refuse('DIRTY_TREE', 'cay lam viec khac HEAD; commit/hoan tac truoc '
                     '(plan --allow-dirty chi de xem thu, manifest khong dung de apply)',
                     dirty=dirty[:20], dirty_count=len(dirty))


def apply_batch(ctx, manifest, ids, dry_run=False, skip_ineligible=False):
    if not (ctx.approval_ref or '').strip():
        raise Refuse('NO_APPROVAL', '--approval-ref la bat buoc (ghi vao provenance)')
    check_manifest(manifest)
    check_manifest_current(ctx, manifest)
    ids = sorted(set(ids))
    if not ids:
        raise Refuse('NO_IDS', 'khong co ID nao duoc chon')
    if len(ids) > MAX_BATCH:
        raise Refuse('BATCH_TOO_LARGE', 'toi da %d ID/batch (batch co gioi han)' % MAX_BATCH)
    bad = [a for a in ids if not isinstance(a, str) or not AID_RE.match(a)]
    if bad:
        raise Refuse('BAD_ID', 'ID sai dinh dang: %s' % bad[:5])
    if ctx.batch_id is not None and not BATCH_ID_RE.match(ctx.batch_id):
        raise Refuse('BAD_BATCH_ID', 'batch-id chi gom A-Za-z0-9._- (toi da 80 ky tu)')
    if not ctx.batch_id:
        ctx.batch_id = 'reattest-%s-%s-%s' % (
            datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d'), ids[0], ids[-1])
    prepared, skipped, ineligible = [], [], []
    for aid in ids:                         # kiểm HẾT trước khi ghi bất kỳ thứ gì
        try:
            state, old_bytes, new_ev = prepare(ctx, manifest, aid)
        except Refuse as e:
            if skip_ineligible and e.code in SKIPPABLE:
                ineligible.append({'id': aid, 'code': e.code, 'reason': e.msg})
                continue
            raise
        (skipped if state == 'already_current' else prepared).append((aid, old_bytes, new_ev))
    report = {'ok': True, 'batch_id': ctx.batch_id, 'dry_run': dry_run,
              'would_write' if dry_run else 'written': [a for a, _, _ in prepared],
              'already_current': [a for a, _, _ in skipped],
              'skipped_ineligible': ineligible}
    if dry_run or not prepared:
        return report
    if ctx.guard:
        ctx.guard()               # cay lam viec con sach NGAY TRUOC khi ghi (batch chay vai phut)
    backup_rel = '%s/%s.json' % (BACKUP_DIR, ctx.batch_id)
    backup_path = ctx.root / backup_rel
    if backup_path.parent.resolve() != (ctx.root / BACKUP_DIR).resolve():
        raise Refuse('BAD_BATCH_ID', 'sao luu phai nam truc tiep trong %s' % BACKUP_DIR)
    if backup_path.exists():
        raise Refuse('BATCH_EXISTS', 'sao luu %s da ton tai — dung batch-id khac' % backup_rel)
    backup = {'schema': BACKUP_SCHEMA, 'batch_id': ctx.batch_id,
              'created_at': now_iso(), 'approval_ref': ctx.approval_ref,
              'baseline_commit': ctx.baseline, 'head_at_apply': ctx.head,
              'tool_commit': ctx.tool_commit,
              'manifest_sha256': sha(doc_text(manifest).encode('utf-8')),
              'entries': {}}
    new_blobs = {}
    for aid, old_bytes, new_ev in prepared:
        new_bytes = evidence_text(new_ev).encode('utf-8')
        new_blobs[aid] = new_bytes
        backup['entries'][aid] = {
            'old_evidence_text': old_bytes.decode('utf-8'),
            'old_evidence_sha256': sha(old_bytes),
            'new_evidence_sha256': sha(new_bytes),
            'content_sha256': new_ev['content_sha256'],
            'matrix_row_sha256': new_ev['matrix_row_sha256']}
    atomic_write(backup_path, doc_text(backup).encode('utf-8'))
    if json.loads(backup_path.read_text(encoding='utf-8')) != json.loads(doc_text(backup)):
        backup_path.unlink()
        raise Refuse('BACKUP_READBACK_FAILED', 'doc lai sao luu khong khop — chua sua evidence nao')
    attempted = []
    try:
        for aid, old_bytes, _ in prepared:
            p = ctx.root / 'data/qa' / (aid + '.json')
            if p.read_bytes() != old_bytes:       # CAS: evidence doi giua luc kiem va luc ghi
                raise Refuse('EVIDENCE_CHANGED_DURING_APPLY', '%s: evidence doi trong luc apply' % aid)
            attempted.append(aid)                 # TRUOC khi ghi: ngat giua atomic_write van duoc tinh
            atomic_write(p, new_blobs[aid])
            if sha(p.read_bytes()) != backup['entries'][aid]['new_evidence_sha256']:
                raise Refuse('WRITE_MISMATCH', '%s: doc lai khong khop' % aid)
        problems = verify_backup(ctx, backup)
        if problems:
            raise Refuse('POST_VERIFY_FAILED', '; '.join(problems[:5]), problems=problems)
    except BaseException as exc:
        _abort_apply(ctx, backup, backup_path, exc, attempted)
        raise
    report['backup'] = backup_rel
    return report


def _abort_apply(ctx, backup, backup_path, exc, attempted):
    """Apply that bai giua chung: tra moi ID MA LAN CHAY NAY DA BAT DAU GHI ve byte cu (ke ca ID
    ma mot ngat o giua atomic_write da doi ten file nhung chua kip ghi nhan). Chi xoa sao luu khi
    MOI ID do da bang byte cu; neu khong, giu sao luu va bao ro de khoi phuc tay. ID chua bat dau
    ghi (vd. bi CAS tu choi) khong phai viec cua tool: khong dong vao."""
    ids = set(attempted)
    try:
        rollback_backup(ctx.root, backup, ids=ids)
    except BaseException:
        pass                                  # van kiem ket qua that o duoi
    left = []
    for aid in sorted(ids):
        b = backup['entries'][aid]
        p = ctx.root / 'data/qa' / (aid + '.json')
        if not p.is_file() or sha(p.read_bytes()) != b['old_evidence_sha256']:
            left.append(aid)
    if left:
        raise Refuse('PARTIAL_APPLY_BACKUP_KEPT',
                     'apply loi (%s: %s) va %d evidence chua ve byte cu: %s — GIU sao luu %s, '
                     'khoi phuc bang `rollback --backup`' % (type(exc).__name__, exc, len(left),
                                                         ', '.join(left[:5]), backup_path.name),
                     left=left) from exc
    backup_path.unlink()                      # file nay do chinh lan chay nay tao


# ------------------------------------------------------------ verify / rollback

def check_backup_shape(backup):
    if not isinstance(backup.get('entries'), dict) or not backup['entries']:
        raise Refuse('BAD_BACKUP', 'sao luu khong co entries')
    for aid, b in backup['entries'].items():
        if not AID_RE.match(aid) or not isinstance(b, dict):
            raise Refuse('BAD_BACKUP', 'khoa entries %r khong hop le' % (aid,))
        for k in ('old_evidence_text', 'old_evidence_sha256', 'new_evidence_sha256'):
            if not isinstance(b.get(k), str):
                raise Refuse('BAD_BACKUP', '%s: thieu %s' % (aid, k))


def verify_backup(ctx, backup, rescore=True):
    """Tương đương kiểm của validate.py + provenance + (rescore) cham lai DOC LAP: diem tren dia
    phai dung la dau ra scorer cho byte/hang hien tai. Tra danh sach loi."""
    check_backup_shape(backup)
    problems = []
    for aid, b in sorted(backup['entries'].items()):
        p = ctx.root / 'data/qa' / (aid + '.json')
        if not p.is_file():
            problems.append('%s: thieu evidence' % aid)
            continue
        raw = p.read_bytes()
        if sha(raw) != b['new_evidence_sha256']:
            problems.append('%s: evidence khac ban da ghi' % aid)
            continue
        ev = json.loads(raw)
        row = ctx.by_id.get(aid)
        if row is None or row['status'] != 'PUBLISHED':
            problems.append('%s: khong con PUBLISHED' % aid)
            continue
        if sha((ctx.root / row['output_path']).read_bytes()) != ev.get('content_sha256'):
            problems.append('%s: content_sha256 khong khop bai hien tai' % aid)
        if A.fingerprint(row) != ev.get('matrix_row_sha256'):
            problems.append('%s: matrix_row_sha256 khong khop hang hien tai' % aid)
        if ev.get('source_path') != row['output_path']:
            problems.append('%s: source_path != output_path' % aid)
        if ev.get('article_id') != aid:
            problems.append('%s: article_id trong evidence la %r' % (aid, ev.get('article_id')))
        if not (ev.get('result') == 'PASS' and ev.get('quality', 0) >= FLOOR_QUALITY
                and ev.get('seo', 0) >= FLOOR_SEO and ev.get('business_fact') == 'PASS'
                and ev.get('legal') in ('PASS', 'NOT_REQUIRED')
                and ev.get('critical_failure') is False):
            problems.append('%s: diem/cong QA khong dat nguong' % aid)
        prov = ev.get('reattestation') or {}
        old_sha = sha(b['old_evidence_text'].encode('utf-8'))
        old = json.loads(b['old_evidence_text'])
        carried = {k: v for k, v in old.items() if k not in ev}
        if (prov.get('previous_evidence_annotations') or {}) != carried:
            problems.append('%s: chu thich lich su cua evidence cu khong duoc giu nguyen' % aid)
        if (b['old_evidence_sha256'] != old_sha
                or prov.get('previous_evidence_sha256') != old_sha
                or prov.get('previous_content_sha256') != old.get('content_sha256')
                or prov.get('previous_matrix_row_sha256') != old.get('matrix_row_sha256')
                or not (prov.get('approval_ref') or '').strip()):
            problems.append('%s: provenance khong khop sao luu' % aid)
        if rescore:
            diff = score_diff(ev, A.rescore_published(ctx.op, row, ctx.rows, ctx.biz, ctx.tax))
            if diff:
                problems.append('%s: diem trong evidence khac diem cham lai doc lap (%s)'
                                % (aid, ', '.join(diff[:6])))
    return problems


def rollback_backup(root, backup, ids=None, dry_run=False):
    check_backup_shape(backup)
    if ids is not None:
        unknown = sorted(set(ids) - set(backup['entries']))
        if unknown:
            raise Refuse('UNKNOWN_IDS', 'ID khong co trong sao luu: %s' % unknown[:5])
    out = {'restored': [], 'skipped_changed_since_apply': [], 'dry_run': dry_run}
    for aid, b in sorted(backup['entries'].items()):
        if ids is not None and aid not in ids:
            continue
        p = pathlib.Path(root) / 'data/qa' / (aid + '.json')
        if not p.is_file() or sha(p.read_bytes()) != b['new_evidence_sha256']:
            out['skipped_changed_since_apply'].append(aid)   # không đè thay đổi của người khác
            continue
        old = b['old_evidence_text'].encode('utf-8')
        if sha(old) != b['old_evidence_sha256']:
            raise Refuse('BACKUP_CORRUPT', '%s: sao luu hong' % aid)
        if not dry_run:
            atomic_write(p, old)
            if sha(p.read_bytes()) != b['old_evidence_sha256']:
                raise Refuse('ROLLBACK_MISMATCH', '%s: khoi phuc khong khop' % aid)
        out['restored'].append(aid)
    return out


# ------------------------------------------------------------------------ CLI

def _ids(v):
    return [x.strip() for x in (v or '').split(',') if x.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--baseline', required=True)
    p.add_argument('--out')
    p.add_argument('--ids', default='')
    p.add_argument('--allow-dirty', action='store_true',
                   help='plan tren cay khac HEAD (manifest ghi head_bound: false, apply se tu choi)')
    a_ = sub.add_parser('apply')
    a_.add_argument('--manifest', required=True)
    a_.add_argument('--approval-ref', default='')
    a_.add_argument('--ids', default='')
    a_.add_argument('--limit', type=int, default=0)
    a_.add_argument('--offset', type=int, default=0)
    a_.add_argument('--batch-id', default=None)
    a_.add_argument('--dry-run', action='store_true')
    a_.add_argument('--skip-ineligible', action='store_true',
                    help='ID khong con du dieu kien luc apply bi BO QUA (bao cao) thay vi dung ca batch')
    v = sub.add_parser('verify')
    v.add_argument('--backup', required=True)
    v.add_argument('--no-rescore', action='store_true',
                   help='chi kiem cau truc/hash/provenance, khong cham lai (mac dinh cham lai doc lap)')
    r = sub.add_parser('rollback')
    r.add_argument('--backup', required=True)
    r.add_argument('--ids', default=None)
    r.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'plan':
            out_path = os.path.abspath(a.out) if a.out else None   # truoc make_ctx (chdir)
            dirty = A.dirty_inputs(ROOT)
            if dirty and not a.allow_dirty:
                require_clean_tree(ROOT)
            ctx = make_ctx(ROOT, a.baseline)
            manifest = make_plan(ctx, set(_ids(a.ids)) or None, head_bound=not dirty)
            text = doc_text(manifest)
            if out_path:
                atomic_write(out_path, text.encode('utf-8'))
                print(json.dumps({'ok': True, 'out': out_path, 'counts': manifest['counts'],
                                  'excluded': {k: len(v) for k, v in manifest['excluded'].items()}},
                                 ensure_ascii=False, indent=2))
            else:
                print(text, end='')
            return 0
        if a.cmd == 'apply':
            manifest = json.loads(pathlib.Path(a.manifest).read_text(encoding='utf-8'))
            require_clean_tree(ROOT)        # ca --dry-run: ket qua phai quy duoc cho HEAD
            check_manifest(manifest)
            ids = _ids(a.ids)
            if not ids:
                elig = sorted(manifest['eligible'])
                if a.limit <= 0:
                    raise Refuse('NO_IDS', 'can --ids hoac --limit N [--offset K]')
                ids = elig[a.offset:a.offset + a.limit]
            ctx = make_ctx(ROOT, manifest['baseline_commit'], a.approval_ref, a.batch_id)
            ctx.guard = lambda: require_clean_tree(ROOT)
            print(json.dumps(apply_batch(ctx, manifest, ids, a.dry_run, a.skip_ineligible),
                             ensure_ascii=False, indent=2))
            return 0
        backup = json.loads(pathlib.Path(a.backup).read_text(encoding='utf-8'))
        if backup.get('schema') != BACKUP_SCHEMA:
            raise Refuse('BAD_BACKUP', 'schema sao luu khong dung')
        if a.cmd == 'verify':
            ctx = make_ctx(ROOT, backup['baseline_commit'], history={})
            problems = verify_backup(ctx, backup, rescore=not a.no_rescore)
            print(json.dumps({'ok': not problems, 'checked': len(backup['entries']),
                              'problems': problems}, ensure_ascii=False, indent=2))
            return 0 if not problems else 1
        ids = None
        if a.ids is not None:
            ids = set(_ids(a.ids))
            if not ids:
                raise Refuse('BAD_IDS', '--ids rong: bo --ids de khoi phuc ca batch')
        out = rollback_backup(ROOT, backup, ids, a.dry_run)
        out['ok'] = True
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except Refuse as e:
        d = {'ok': False, 'code': e.code, 'error': e.msg}
        d.update(e.extra)
        print(json.dumps(d, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
