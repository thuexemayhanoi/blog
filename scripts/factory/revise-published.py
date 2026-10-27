#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sửa NỘI DUNG bài PUBLISHED CÓ KIỂM SOÁT và ghi lại bằng chứng QA hợp lệ.

Bối cảnh: bài PUBLISHED bị ràng buộc bởi `data/qa/<ID>.json` (`content_sha256`,
`matrix_row_sha256`, `source_path`). Sửa tay một chữ trong bài làm evidence lệch hash
(`validate --scope batch|full` đỏ); sửa tay evidence là cấm (AGENTS.md quy tắc 9).
`reattest-legacy-qa.py` chỉ phục vụ ca lệch hash do đổi domain. Tool này là đường GHI
duy nhất cho ca còn lại: SỬA NỘI DUNG THẬT của bài đã xuất bản (vd. đồng bộ giá thuê
với bảng giá chủ xe, sửa câu lỗi thời), theo lô nhỏ, có chủ duyệt, có sao lưu và hoàn
tác byte-exact. KHÔNG đổi URL, title, permalink, canonical, hàng matrix, liên kết.

Một bài chỉ được sửa khi thỏa MỌI điều kiện (tool tự kiểm từ byte hiện tại, không tin
manifest, không có cờ ép):

  1. Hàng matrix PUBLISHED, `output_path` nằm trong `_posts/`, evidence NGUYÊN VẸN:
     `content_sha256` == sha256(byte bài hiện tại), `matrix_row_sha256` == vân tay hàng
     hiện tại, `article_id`/`source_path` đúng, result PASS. Evidence đã lệch hash (vd.
     migrate domain) bị TỪ CHỐI (EVIDENCE_NOT_INTACT): đi qua `reattest-legacy-qa.py` trước —
     TRỪ khi gọi tường minh `--domain-drift` (plan VÀ apply): khi đó evidence lệch hash chỉ được
     nhận nếu tool tự chứng minh DOMAIN_ONLY_PROVEN đúng phép kiểm của `reattest-legacy-qa.py`
     (baseline ghim bất biến, tiền bối của HEAD; hash trong evidence buộc đúng byte bài + hàng
     matrix của baseline; exact-transform v3 của baseline == byte/trường hiện tại; evidence chưa
     đổi từ baseline). Đây là ca bài lệch hash do đổi domain mà nội dung còn sai (vd. giá cũ):
     reattest từ chối vì chấm lại rớt, revise thường từ chối vì evidence lệch — đường này sửa + chấm
     lại ĐỘC LẬP trong CÙNG một giao dịch (điều kiện 2–5 giữ nguyên), evidence mới ghi
     `revision.base = DOMAIN_ONLY_PROVEN` + bằng chứng (`domain_only_proof`); `verify` chứng minh
     lại từ lịch sử git, không tin sao lưu. Ca không chứng minh được (NOT_DOMAIN_ONLY) giữ nguyên.
  2. ID không nằm trong bất kỳ lease writer nào và không có draft cùng slug.
  3. Chỉ đổi được THÂN BÀI và dòng `description:`: mọi dòng front matter khác (title,
     date, permalink, article_id, parent_id, child_id, tags...) phải giữ nguyên từng byte;
     tập liên kết/Liquid/URL trong thân và số heading theo cấp phải giữ nguyên; tối đa 60
     sửa/bài và tổng ký tự đổi <= 20% độ dài bài (sửa nhẹ, không viết lại).
  4. Chấm điểm ĐỘC LẬP trên byte ứng viên bằng scorer canonical `factory-operator.qa_check_one`
     (corpus/taxonomy/business-facts hiện tại): result PASS, quality >= 75, seo >= 70,
     business_fact PASS, legal PASS|NOT_REQUIRED, không critical_failure; và KHÔNG tiêu chí
     nào đạt ở bản chưa sửa lại rớt ở bản đã sửa, điểm không thấp hơn bản chưa sửa.
  5. Có chủ duyệt (`--approval-ref` bắt buộc, ghi vào provenance) và manifest do `plan` lập.

Kết quả ghi cho mỗi ID được duyệt (CHỈ hai file + một file sao lưu mỗi lô):
  * `_posts/<file>.md`: byte ứng viên (đúng các sửa trong manifest).
  * `data/qa/<ID>.json`: đầu ra scorer MỚI trên byte mới + khối `revision` (provenance:
    hash evidence/bài cũ, hash bài mới, sha256 danh sách sửa, người duyệt, mã scorer/facts/
    taxonomy, chuỗi `history` nếu bài từng bị sửa). `scored_at`/`published_at` GIỮ mốc lịch
    sử gốc (watchdog đọc chúng như tín hiệu hoạt động: sửa nội dung không được tạo hoạt động
    giả); mọi chú thích lịch sử khác của evidence cũ (reattestation, post_publish_repair...)
    được giữ nguyên ở cấp trên.
  * `reports/qa-audit/revise/<batch>.json`: NGUYÊN VĂN bài + evidence cũ, sha256 cũ/mới và
    danh sách sửa, ghi và đọc lại TRƯỚC khi sửa bất kỳ file nào.
  * KHÔNG đụng matrix, checkpoint, lease, draft, bài khác.

Rào do TOOL tự giữ (không tin repo): sàn 75/70 cứng, ID/batch-id/output_path được kiểm cú pháp, lô <= 50
ID, mỗi file được compare-and-swap trước khi ghi, apply lỗi giữa chừng trả MỌI ID đã bắt đầu
ghi về byte cũ (chỉ xóa sao lưu khi tất cả đã về, nếu không giữ: PARTIAL_APPLY_BACKUP_KEPT),
`verify` chấm lại độc lập từng ID (--no-rescore: chỉ cấu trúc/hash). `plan` và `apply` TỪ CHỐI
khi cây làm việc khác HEAD (DIRTY_TREE; `plan --allow-dirty` chỉ để xem thử, manifest đánh dấu
`head_bound: false` và bị `apply` từ chối). Mỗi lô = một commit rồi mới đến lô sau.

Lệnh:
  plan     --patches FILE [--out FILE] [--allow-dirty] [--domain-drift]   chấm điểm đề xuất (không ghi gì)
  apply    --manifest FILE --approval-ref TEXT (--ids A,B | --limit N [--offset K])
           [--batch-id ID] [--dry-run] [--skip-ineligible] [--domain-drift]
                                                          kiểm lại TẤT CẢ rồi ghi (lô <= 50)
  verify   --backup FILE [--no-rescore]                  kiểm bài + evidence đã ghi + provenance
  rollback --backup FILE [--ids A,B] [--dry-run]         khôi phục byte-exact bài + evidence cũ
                                                          (chỉ khi file còn đúng bản đã ghi)

File `--patches` (schema `revise-patches/1`) do người/công cụ nội dung lập, ví dụ:
  {"schema": "revise-patches/1", "purpose": "price-sync-20261023", "reason": "...",
   "patches": {"BLG-00123": {"edits": [{"old": "...", "new": "...", "count": 1}]}}}
Mỗi `old` phải xuất hiện đúng `count` lần (mặc định 1) trong byte hiện tại; các sửa không chồng nhau.

Manifest của `plan` KHÔNG có hiệu lực pháp lý: `apply` tự kiểm lại mọi điều kiện từ git + byte
hiện tại; manifest bị sửa/lỗi thời chỉ làm `apply` TỪ CHỐI. Một ID không đạt thì CẢ lô dừng,
chưa ghi gì (nguyên tử). Chạy lặp lại là no-op. Hash chứng minh toàn vẹn/provenance, không phải
xác thực tác giả: quyền ghi repo vẫn do review PR + CI + lịch sử git bất biến bảo vệ.
"""
import argparse
import builtins
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
PATCHES_SCHEMA = 'revise-patches/1'
MANIFEST_SCHEMA = 'revise-manifest/1'
BACKUP_SCHEMA = 'revise-backup/1'
BACKUP_DIR = 'reports/qa-audit/revise'
ELIGIBLE = 'ELIGIBLE_PROPOSAL_AWAITING_OWNER_APPROVAL'
MAX_BATCH = 50
MAX_EDITS = 60
MAX_CHANGE_RATIO = 0.20
# Rao CUNG — khong lay tu repo (scorer/manifest la thu tool khong duoc tin):
FLOOR_QUALITY, FLOOR_SEO = 75, 70
BATCH_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z')
AID_RE = re.compile(r'^BLG-[0-9]+\Z')            # ASCII only
POST_RE = re.compile(r'^_posts/[^/]+\.md\Z')
FM_RE = re.compile(r'\A---\n(.*?\n)---\n', re.S)
DESC_LINE_RE = re.compile(r'''\Adescription: ("(?:[^"\\]|\\.)*"|'(?:[^']|'')*')\Z''')
LINKISH_RE = re.compile(r'\]\([^)]*\)|href="[^"]*"|\{\{.*?\}\}|\{%.*?%\}|https?://[^\s)"<>]+')
HEAD_RE = re.compile(r'^(#{1,6})\s', re.M)
# Khoa lich su/provenance cua evidence: KHONG so voi diem cham lai.
PROVENANCE_KEYS = ('revision', 'scored_at', 'published_at')
FRESH_FIELDS = ('result', 'quality', 'seo', 'business_fact', 'legal', 'critical_failure')
# Tu choi theo TRANG THAI HIEN TAI cua tung ID (bai/evidence/corpus doi tu luc plan, cham lai
# khong dat...). Voi --skip-ineligible chung chi lam ID do bi BO QUA (bao cao ro); cac loi chon sai
# (NOT_ELIGIBLE, thieu evidence) luon dung ca lo.
SKIPPABLE = ('NOT_PUBLISHED', 'POST_CHANGED_SINCE_PLAN', 'EVIDENCE_CHANGED_SINCE_PLAN',
             'INPUT_CHANGED_SINCE_PLAN', 'EVIDENCE_NOT_INTACT', 'NOT_DOMAIN_ONLY', 'LEASED', 'HAS_DRAFT',
             'EDIT_MISMATCH', 'FRESH_QA_NOT_ELIGIBLE', 'REGRESSION', 'UNEXPECTED_CURRENT_EVIDENCE')
# Nền của bài trước khi sửa: evidence nguyên vẹn, hoặc (chỉ với --domain-drift) lệch hash đã chứng minh
# chỉ do đổi domain v3 (cùng phép kiểm với reattest-legacy-qa.py).
BASE_INTACT, BASE_DOMAIN = 'INTACT', 'DOMAIN_ONLY_PROVEN'


class Refuse(Exception):
    def __init__(self, code, msg, **extra):
        super().__init__(msg)
        self.code, self.msg, self.extra = code, msg, extra


def _load(name, filename):
    path = pathlib.Path(filename) if os.path.isabs(str(filename)) else HERE / filename
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


A = _load('legacy_audit_for_revise', 'audit-legacy-qa.py')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')


def evidence_text(obj):
    """Đúng định dạng `factory-operator.write_json_atomic` (indent=2, không xuống dòng cuối)."""
    return json.dumps(obj, ensure_ascii=False, indent=2)


def doc_text(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n'


def edits_digest(edits):
    return sha(json.dumps(edits, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':')).encode('utf-8'))


def atomic_write(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.revise.tmp')
    try:
        with open(tmp, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()                      # khong de lai *.revise.tmp
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
    r = subprocess.run(['git'] + list(args), cwd=str(root), capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def read_rows(root):
    with open(pathlib.Path(root) / 'data/content-matrix.csv', encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


class Ctx:
    """Mọi đầu vào của một lần chạy (tiêm được cho test)."""

    def __init__(self, root, op, biz, tax, approval_ref='', batch_id=None, head=None,
                 tool_commit=None, purpose='', reason='', domain_drift=False, history=None,
                 baseline=None):
        self.root = pathlib.Path(root)
        # --domain-drift: nhận evidence lệch hash do đổi domain (chứng minh lại từ baseline ghim).
        # history/baseline: blob của commit baseline (nạp lười từ git; test tiêm dict).
        self.domain_drift = bool(domain_drift)
        self.history, self.baseline = history, baseline
        self._old_rows = None
        self.op, self.biz, self.tax = op, biz, tax
        self.approval_ref, self.batch_id = approval_ref, batch_id
        self.head, self.tool_commit = head, tool_commit
        self.purpose, self.reason = purpose, reason
        self.guard = None        # callable kiem lai cay sach NGAY TRUOC khi ghi (CLI dat)
        self.rows = read_rows(self.root)
        self.by_id = {r['id']: r for r in self.rows}
        self.code_sha = {
            'scorer_code_sha256': sha((self.root / 'scripts/factory/factory-operator.py').read_bytes()),
            'business_facts_sha256': sha((self.root / 'data/business-facts.json').read_bytes()),
            'taxonomy_sha256': sha((self.root / 'data/content-taxonomy.json').read_bytes()),
        }


def make_ctx(root, approval_ref='', batch_id=None, purpose='', reason='', domain_drift=False,
             history=None):
    root = pathlib.Path(root)
    os.chdir(root)               # scorer đọc đường dẫn tương đối từ gốc repo
    op = _load('operator_for_revise', str(root / 'scripts/factory/factory-operator.py'))
    if op.QUALITY_MIN < FLOOR_QUALITY or op.SEO_MIN < FLOOR_SEO:
        # Nguong la thu tool KHONG duoc ha, du repo (scorer) noi gi: chan cua rieng tool.
        raise Refuse('THRESHOLD_BELOW_FLOOR',
                     'scorer co nguong %s/%s thap hon san %s/%s — khong sua bai'
                     % (op.QUALITY_MIN, op.SEO_MIN, FLOOR_QUALITY, FLOOR_SEO))
    biz = json.loads((root / 'data/business-facts.json').read_text(encoding='utf-8'))
    tax = json.loads((root / 'data/content-taxonomy.json').read_text(encoding='utf-8'))
    op.build_amount_whitelist(biz)     # qa_check_one doc APPROVED_AMOUNTS (module-global)
    head = git_out(root, 'rev-parse', 'HEAD')
    return Ctx(root, op, biz, tax, approval_ref, batch_id, head=head, tool_commit=head,
               purpose=purpose, reason=reason, domain_drift=domain_drift, history=history,
               baseline='fixture-baseline' if history is not None else None)


def baseline_view(ctx):
    """(history, baseline_commit, old_rows) của baseline ghim của reattest-legacy-qa.py (migration v3).
    Nạp lười từ git: baseline phải là đúng commit ghim và là tiền bối của HEAD (không tin repo/manifest)."""
    if ctx.history is None:
        pinned = _load('reattest_for_revise', 'reattest-legacy-qa.py').PINNED_BASELINE
        commit = git_out(ctx.root, 'rev-parse', '--verify', pinned + '^{commit}')
        if commit != pinned:
            raise Refuse('BASELINE_MISSING', 'khong doc duoc baseline ghim %s (can lich su git day du)' % pinned)
        if subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'],
                          cwd=str(ctx.root), capture_output=True).returncode != 0:
            raise Refuse('BASELINE_NOT_ANCESTOR', 'baseline %s khong phai tien boi cua HEAD' % commit)
        ctx.history, ctx.baseline = A.historical_blobs(commit), commit
    if ctx._old_rows is None:
        raw = ctx.history.get('data/content-matrix.csv') or b''
        ctx._old_rows = {r['id']: r for r in csv.DictReader(io.StringIO(raw.decode('utf-8')))}
    return ctx.history, ctx.baseline, ctx._old_rows


def domain_drift_proof(ctx, row, current, evidence):
    """Chứng minh evidence lệch hash CHỈ vì đổi domain v3 — đúng phép `audit-legacy-qa.classify` mà
    reattest-legacy-qa.py dùng: hash ghi trong evidence buộc byte bài + hàng matrix của baseline, evidence
    chưa đổi từ baseline, exact-transform v3 của baseline == `current` và hàng hiện tại. Trả bằng chứng
    (dict) hoặc Refuse NOT_DOMAIN_ONLY."""
    history, baseline, old_rows = baseline_view(ctx)
    aid = row['id']
    qa_path = 'data/qa/%s.json' % aid
    old_row = old_rows.get(aid)
    old_bytes = history.get(old_row['output_path']) if old_row else None
    old_ev = json.loads(history[qa_path]) if qa_path in history else None
    cl = A.classify(row, current, evidence, old_row, old_bytes, old_ev)
    if cl['classification'] != BASE_DOMAIN:
        raise Refuse('NOT_DOMAIN_ONLY',
                     '%s: evidence lech hash nhung khong chung minh duoc chi do doi domain (%s) — giu nguyen'
                     % (aid, cl['classification']), classification=cl['classification'])
    return {'classification': BASE_DOMAIN, 'baseline_commit': baseline,
            'baseline_content_sha256': cl['baseline_content_sha256'],
            'baseline_matrix_sha256': cl['baseline_matrix_sha256'],
            'pre_edit_content_sha256': cl['current_content_sha256'],
            'pre_edit_matrix_row_sha256': cl['current_matrix_sha256']}


# ------------------------------------------------------------------ sửa văn bản

def split_front(text):
    m = FM_RE.match(text)
    if not m:
        raise Refuse('NO_FRONT_MATTER', 'bai khong co front matter dang ---\\n...\\n---\\n')
    return m.group(1), text[m.end():]


def apply_edits(text, edits):
    """Áp danh sách sửa lên `text`: mỗi `old` phải xuất hiện đúng `count` lần TRONG VĂN BẢN GỐC,
    các vị trí không chồng nhau (không có chuyện sửa sau khớp vào chữ vừa được sửa trước).
    Trả (văn bản mới, số ký tự bị đổi)."""
    if not isinstance(edits, list) or not edits:
        raise Refuse('NO_EDITS', 'khong co sua nao')
    if len(edits) > MAX_EDITS:
        raise Refuse('TOO_MANY_EDITS', 'toi da %d sua/bai (nhan %d)' % (MAX_EDITS, len(edits)))
    spans = []
    for i, ed in enumerate(edits):
        if not isinstance(ed, dict) or set(ed) - {'old', 'new', 'count', 'note'}:
            raise Refuse('BAD_EDIT', 'sua #%d sai dinh dang (chi old/new/count/note)' % i)
        old, new = ed.get('old'), ed.get('new')
        if not isinstance(old, str) or not isinstance(new, str) or not old or old == new:
            raise Refuse('BAD_EDIT', 'sua #%d: old/new phai la chuoi, old khong rong va khac new' % i)
        count = ed.get('count', 1)
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise Refuse('BAD_EDIT', 'sua #%d: count phai la so nguyen >= 1' % i)
        found = [m.start() for m in re.finditer(re.escape(old), text)]
        if len(found) != count:
            raise Refuse('EDIT_MISMATCH', 'sua #%d: %r xuat hien %d lan, can dung %d'
                         % (i, old[:60], len(found), count))
        spans += [(s, s + len(old), new, i) for s in found]
    spans.sort(key=lambda t: (t[0], t[1]))
    for a, b in zip(spans, spans[1:]):
        if a[1] > b[0]:
            raise Refuse('EDIT_OVERLAP', 'sua #%d va #%d chong len nhau' % (a[3], b[3]))
    out, pos, changed = [], 0, 0
    for s, e, new, _ in spans:
        out += [text[pos:s], new]
        pos = e
        changed += (e - s) + len(new)
    out.append(text[pos:])
    return ''.join(out), changed


def check_invariants(old_text, new_text, changed):
    """Sửa nhẹ trong biên: front matter chỉ đổi được `description:`, thân giữ nguyên tập liên kết
    và số heading theo cấp, tổng ký tự đổi trong ngưỡng."""
    old_front, old_body = split_front(old_text)
    new_front, new_body = split_front(new_text)
    ol, nl = old_front.split('\n'), new_front.split('\n')
    if len(ol) != len(nl):
        raise Refuse('FRONT_MATTER_CHANGED', 'so dong front matter doi')
    for a, b in zip(ol, nl):
        if a == b:
            continue
        if a.startswith('description:') and DESC_LINE_RE.match(b) and DESC_LINE_RE.match(a):
            continue
        raise Refuse('FRONT_MATTER_CHANGED',
                     'chi duoc doi dong description (title/permalink/id/tags... bat bien): %r' % a[:60])
    if collections.Counter(LINKISH_RE.findall(old_body)) != collections.Counter(LINKISH_RE.findall(new_body)):
        raise Refuse('LINKS_CHANGED', 'tap lien ket/Liquid/URL trong than bai bi doi')
    if collections.Counter(len(h) for h in HEAD_RE.findall(old_body)) \
            != collections.Counter(len(h) for h in HEAD_RE.findall(new_body)):
        raise Refuse('HEADINGS_CHANGED', 'so heading theo cap bi doi')
    if changed > MAX_CHANGE_RATIO * max(len(old_text), 1):
        raise Refuse('CHANGE_TOO_LARGE', 'doi %d ky tu > %d%% do dai bai (sua nhe, khong viet lai)'
                     % (changed, int(MAX_CHANGE_RATIO * 100)))


# --------------------------------------------------------------- chấm điểm ứng viên

def score_candidate(ctx, row, post_bytes):
    """Chấm `post_bytes` như thể chúng là `row['output_path']`, KHÔNG ghi gì lên đĩa: scorer đọc bài bằng
    `open(<đường dẫn tương đối>)`; ta thay đúng lời gọi mở file đó bằng byte ứng viên trong một khối
    có phạm vi (mọi file khác đọc bình thường) rồi trả lại `open` gốc."""
    op = ctx.op
    path = row['output_path']
    slug = pathlib.Path(path).name[11:-3]
    root = str(ctx.root)
    target = os.path.abspath(os.path.join(root, path))
    real_open = builtins.open

    def patched_open(file, mode='r', *args, **kwargs):
        if isinstance(file, (str, bytes, os.PathLike)):
            if os.path.abspath(os.fsdecode(os.fspath(file))) == target:
                if any(c in mode for c in 'wax+'):
                    raise Refuse('SCORER_WROTE_POST', 'scorer co ghi vao bai: tu choi')
                raw = io.BytesIO(post_bytes)
                if 'b' in mode:
                    return raw
                return io.TextIOWrapper(raw, encoding=kwargs.get('encoding') or 'utf-8')
        return real_open(file, mode, *args, **kwargs)

    original = op.find_draft
    try:
        previous = os.getcwd()
    except OSError:
        previous = None
    try:
        os.chdir(root)
        op.find_draft = lambda r: (path, slug) if r['id'] == row['id'] else original(r)
        builtins.open = patched_open
        return op.qa_check_one(row, ctx.rows, ctx.biz, ctx.tax)
    finally:
        builtins.open = real_open
        op.find_draft = original
        if previous is not None:
            os.chdir(previous)


def score_ok(ev, fl_quality=FLOOR_QUALITY, fl_seo=FLOOR_SEO):
    return (ev.get('result') == 'PASS' and ev.get('quality', 0) >= fl_quality
            and ev.get('seo', 0) >= fl_seo and ev.get('business_fact') == 'PASS'
            and ev.get('legal') in ('PASS', 'NOT_REQUIRED') and ev.get('critical_failure') is False)


_MISSING = object()


def score_diff(evidence, fresh):
    """Khoá khác nhau giữa evidence trên đĩa và điểm scorer chấm lại (bỏ khoá lịch sử/provenance và
    các chú thích lịch sử mà scorer không sinh ra). Rỗng = evidence đúng là đầu ra scorer cho byte này."""
    a = {k: v for k, v in evidence.items() if k not in PROVENANCE_KEYS and k in fresh}
    b = {k: v for k, v in fresh.items() if k not in PROVENANCE_KEYS}
    return sorted(k for k in set(a) | set(b) if a.get(k, _MISSING) != b.get(k, _MISSING))


# ------------------------------------------------------------------ đánh giá một ID

def lease_ids(root):
    """Mọi ID xuất hiện trong BẤT KỲ lease nào (kể cả đã hết hạn: bài đã xuất bản không được nằm trong lease)."""
    p = pathlib.Path(root) / 'data/state/writer-claims.json'
    if not p.is_file():
        return set()
    try:
        reg = json.loads(p.read_text(encoding='utf-8'))
        ids = set()
        for lease in (reg.get('leases') or {}).values():
            ids |= set(lease.get('ids') or [])
        return ids
    except (ValueError, AttributeError, TypeError):
        raise Refuse('BAD_REGISTRY', 'writer-claims.json khong doc duoc — dung (fail-closed)')


def draft_exists(root, row):
    """Có draft cùng slug hoặc draft mang article_id này không (writer đang làm lại bài)."""
    d = pathlib.Path(root) / '_drafts'
    if not d.is_dir():
        return False
    slug = pathlib.Path(row['output_path']).name[11:-3]
    for f in d.glob('*.md'):
        if f.name.endswith('-%s.md' % slug):
            return True
        try:
            head = f.read_text(encoding='utf-8')[:2000]
        except OSError:
            continue
        if re.search(r'^article_id:\s*["\']?%s["\']?\s*$' % re.escape(row['id']), head, re.M):
            return True
    return False


class Derived:
    """Kết quả đánh giá đầy đủ một ID (thuần đọc)."""
    __slots__ = ('aid', 'row', 'path', 'old_post', 'new_post', 'old_ev_bytes', 'old_ev',
                 'before', 'after', 'edits', 'edits_sha256', 'changed', 'base', 'proof')


def derive(ctx, aid, edits):
    if not isinstance(aid, str) or not AID_RE.match(aid):
        raise Refuse('BAD_ID', 'ID sai dinh dang: %r' % (aid,))
    row = ctx.by_id.get(aid)
    if row is None or row['status'] != 'PUBLISHED':
        raise Refuse('NOT_PUBLISHED', '%s khong phai hang PUBLISHED' % aid)
    path = row.get('output_path') or ''
    if not POST_RE.match(path):
        raise Refuse('BAD_OUTPUT_PATH', '%s: output_path %r khong nam trong _posts/' % (aid, path))
    if aid in lease_ids(ctx.root):
        raise Refuse('LEASED', '%s nam trong lease writer — khong sua' % aid)
    if draft_exists(ctx.root, row):
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
    hashes_match = (sha(old_post) == old_ev.get('content_sha256')
                    and A.fingerprint(row) == old_ev.get('matrix_row_sha256'))
    if not (old_ev.get('article_id') == aid and old_ev.get('source_path') == path
            and old_ev.get('result') == 'PASS') or (not hashes_match and not ctx.domain_drift):
        raise Refuse('EVIDENCE_NOT_INTACT',
                     '%s: evidence khong khop byte bai/hang matrix hien tai (hash lech, source_path, '
                     'result) — xu ly bang reattest-legacy-qa.py truoc (lech do doi domain: --domain-drift), '
                     'khong sua noi dung' % aid)
    base, proof = BASE_INTACT, None
    if not hashes_match:
        proof = domain_drift_proof(ctx, row, old_post, old_ev)
        base = BASE_DOMAIN
    try:
        old_text = old_post.decode('utf-8')
    except UnicodeDecodeError:
        raise Refuse('NOT_UTF8', '%s: bai khong phai UTF-8' % aid)
    new_text, changed = apply_edits(old_text, edits)
    check_invariants(old_text, new_text, changed)
    new_post = new_text.encode('utf-8')
    before = score_candidate(ctx, row, old_post)
    after = score_candidate(ctx, row, new_post)
    if (after.get('content_sha256') != sha(new_post) or after.get('matrix_row_sha256') != A.fingerprint(row)
            or after.get('article_id') != aid or after.get('source_path') != path):
        raise Refuse('FRESH_QA_UNBOUND', '%s: diem cham khong buoc dung byte/hang ung vien' % aid)
    if not score_ok(after):
        failed = sorted(k for k, v in after.get('checks', {}).items() if not v)
        raise Refuse('FRESH_QA_NOT_ELIGIBLE',
                     '%s: cham lai doc lap = %s q=%s s=%s (failed_checks=%s) — giu nguyen de xu ly rieng'
                     % (aid, after.get('result'), after.get('quality'), after.get('seo'), failed),
                     failed_checks=failed)
    flipped = sorted(k for k, v in before.get('checks', {}).items()
                     if v and not after.get('checks', {}).get(k))
    if flipped or after['quality'] < before.get('quality', 0) or after['seo'] < before.get('seo', 0):
        raise Refuse('REGRESSION', '%s: sua lam tut tieu chi %s hoac diem (q %s->%s, s %s->%s)'
                     % (aid, flipped, before.get('quality'), after['quality'],
                        before.get('seo'), after['seo']), flipped=flipped)
    d = Derived()
    d.aid, d.row, d.path = aid, row, path
    d.old_post, d.new_post, d.old_ev_bytes, d.old_ev = old_post, new_post, old_ev_bytes, old_ev
    d.before, d.after = before, after
    d.edits, d.edits_sha256, d.changed = edits, edits_digest(edits), changed
    d.base, d.proof = base, proof
    return d


def build_new_evidence(ctx, d, old_evidence_sha256):
    if not d.old_ev.get('scored_at'):
        # scored_at moi = bay gio se bi watchdog doc nhu hoat dong gia: khong sua bai.
        raise Refuse('NO_HISTORICAL_SCORED_AT', '%s: evidence cu khong co scored_at lich su de giu' % d.aid)
    new = copy.deepcopy(d.after)
    for k in ('scored_at', 'published_at'):           # mốc lịch sử: giữ nguyên
        if d.old_ev.get(k):
            new[k] = d.old_ev[k]
    for k, v in d.old_ev.items():                      # chú thích lịch sử (reattestation,...): giữ nguyên
        if k not in new and k != 'revision':
            new[k] = copy.deepcopy(v)
    history = []
    prev = d.old_ev.get('revision')
    if isinstance(prev, dict):
        history = list(prev.get('history') or []) + [{k: v for k, v in prev.items() if k != 'history'}]
    new['revision'] = {
        'schema': 'revision/1',
        'kind': 'content-revision',
        'purpose': ctx.purpose,
        'reason': ctx.reason,
        'approval_ref': ctx.approval_ref,
        'batch_id': ctx.batch_id,
        'revised_at': now_iso(),
        'previous_evidence_sha256': old_evidence_sha256,
        'previous_content_sha256': d.old_ev['content_sha256'],
        'previous_matrix_row_sha256': d.old_ev['matrix_row_sha256'],
        'new_content_sha256': new['content_sha256'],
        'edit_count': len(d.edits),
        'edits_sha256': d.edits_sha256,
        'chars_changed': d.changed,
        'previous_scores': {k: d.old_ev.get(k) for k in ('quality', 'seo', 'grade')},
        'base': d.base,
        'scorer': new.get('scorer'),
        'thresholds': {'quality_min': ctx.op.QUALITY_MIN, 'seo_min': ctx.op.SEO_MIN},
        'tool': 'scripts/factory/revise-published.py',
        'tool_commit': ctx.tool_commit,
        'tool_sha256': sha(pathlib.Path(__file__).read_bytes()),
        **ctx.code_sha,
        'note': ('scored_at/published_at o cap tren giu moc lich su goc (watchdog doc chung nhu tin '
                 'hieu hoat dong); noi dung da duoc sua theo danh sach sua co sha256 nay, cham diem '
                 'doc lap luc revised_at'),
    }
    if d.proof:
        # evidence cu lech hash do doi domain: bang chung DOMAIN_ONLY_PROVEN (verify chung minh lai tu git)
        new['revision']['domain_only_proof'] = d.proof
    if history:
        new['revision']['history'] = history
    return new


def summary(ev):
    return {k: ev.get(k) for k in FRESH_FIELDS}


# --------------------------------------------------------------------- plan

def load_patches(obj):
    if not isinstance(obj, dict) or obj.get('schema') != PATCHES_SCHEMA:
        raise Refuse('BAD_PATCHES', 'schema patches khong dung (can %s)' % PATCHES_SCHEMA)
    for k in ('purpose', 'reason'):
        if not isinstance(obj.get(k), str) or not obj[k].strip():
            raise Refuse('BAD_PATCHES', 'patches thieu %s' % k)
    if not isinstance(obj.get('patches'), dict) or not obj['patches']:
        raise Refuse('BAD_PATCHES', 'patches rong')
    for aid, p in obj['patches'].items():
        if not isinstance(p, dict) or not isinstance(p.get('edits'), list):
            raise Refuse('BAD_PATCHES', '%s: thieu edits' % aid)
    return obj


def make_plan(ctx, patches, head_bound=True):
    patches = load_patches(patches)
    ctx.purpose, ctx.reason = patches['purpose'], patches['reason']
    entries, excluded = {}, collections.defaultdict(list)
    for aid, p in sorted(patches['patches'].items()):
        try:
            d = derive(ctx, aid, p['edits'])
        except Refuse as e:
            entries[aid] = {'id': aid, 'decision': e.code, 'reason': e.msg}
            excluded[e.code].append(aid)
            continue
        entries[aid] = {
            'id': aid, 'path': d.path, 'decision': ELIGIBLE,
            'base_post_sha256': sha(d.old_post), 'new_post_sha256': sha(d.new_post),
            'old_evidence_sha256': sha(d.old_ev_bytes), 'edits_sha256': d.edits_sha256,
            'edit_count': len(d.edits), 'chars_changed': d.changed,
            'before': summary(d.before), 'after': summary(d.after),
            'before_scores': {'quality': d.before.get('quality'), 'seo': d.before.get('seo')},
            'edits': d.edits,
            'base': d.base,
        }
        if d.proof:
            entries[aid]['domain_only_proof'] = d.proof
    eligible = sorted(i for i, e in entries.items() if e['decision'] == ELIGIBLE)
    return {
        'schema': MANIFEST_SCHEMA,
        'authority': 'PROPOSAL ONLY — apply kiem lai moi dieu kien tu git + byte hien tai',
        'purpose': patches['purpose'], 'reason': patches['reason'],
        'head': ctx.head,
        # True chi khi cay lam viec == HEAD luc plan (plan --allow-dirty => False; apply tu choi)
        'head_bound': bool(head_bound),
        'domain_drift': ctx.domain_drift,
        'matrix_sha256': sha((ctx.root / 'data/content-matrix.csv').read_bytes()),
        'thresholds': {'quality_min': ctx.op.QUALITY_MIN, 'seo_min': ctx.op.SEO_MIN},
        **ctx.code_sha,
        'counts': {'patched': len(entries), 'eligible': len(eligible),
                   'decisions': dict(collections.Counter(e['decision'] for e in entries.values()))},
        'eligible': eligible,
        'excluded': {k: sorted(v) for k, v in sorted(excluded.items())},
        'entries': entries,
    }


# --------------------------------------------------------------------- apply

def check_manifest(manifest):
    if manifest.get('schema') != MANIFEST_SCHEMA:
        raise Refuse('BAD_MANIFEST', 'schema manifest khong dung')
    if not isinstance(manifest.get('entries'), dict) or not isinstance(manifest.get('eligible'), list):
        raise Refuse('BAD_MANIFEST', 'manifest thieu entries/eligible')
    for k in ('purpose', 'reason'):
        if not isinstance(manifest.get(k), str) or not manifest[k].strip():
            raise Refuse('BAD_MANIFEST', 'manifest thieu %s' % k)
    if manifest.get('head_bound') is not True:
        raise Refuse('MANIFEST_NOT_HEAD_BOUND',
                     'manifest khong gan voi mot commit sach (plan --allow-dirty, hoac ban cu) — '
                     'chay lai plan tren cay lam viec sach')


def check_manifest_current(ctx, manifest):
    """Manifest phai lap bang CUNG scorer/facts/taxonomy/nguong voi hien tai: khac => du lieu da doi
    tu luc plan, chay lai plan (fail-closed)."""
    for k, v in ctx.code_sha.items():
        if manifest.get(k) != v:
            raise Refuse('SCORER_CHANGED_SINCE_PLAN',
                         '%s khac manifest (scorer/facts/taxonomy da doi) — chay lai plan' % k)
    if manifest.get('thresholds') != {'quality_min': ctx.op.QUALITY_MIN, 'seo_min': ctx.op.SEO_MIN}:
        raise Refuse('SCORER_CHANGED_SINCE_PLAN', 'nguong QA khac manifest — chay lai plan')
    if bool(manifest.get('domain_drift')) != ctx.domain_drift:
        raise Refuse('DOMAIN_DRIFT_MISMATCH', 'manifest lap %s --domain-drift ma apply %s — goi cung che do'
                     % ('CO' if manifest.get('domain_drift') else 'KHONG',
                        'CO' if ctx.domain_drift else 'KHONG'))


def require_clean_tree(root=ROOT):
    """Cay lam viec phai bang HEAD (cung phep kiem voi audit-legacy-qa.py): diem chi quy duoc cho mot
    commit khi matrix/bai/evidence/scorer/facts/taxonomy dung la cua no."""
    dirty = A.dirty_inputs(root)
    if dirty:
        raise Refuse('DIRTY_TREE', 'cay lam viec khac HEAD; commit/hoan tac truoc '
                     '(plan --allow-dirty chi de xem thu, manifest khong dung de apply)',
                     dirty=dirty[:20], dirty_count=len(dirty))


def prepare(ctx, manifest, aid):
    """Kiểm lại MỌI điều kiện cho một ID. Trả ('ready'|'already_current', Derived|None, new_ev|None)
    hoặc Refuse — không bao giờ ghi."""
    e = manifest['entries'].get(aid)
    if e is None or aid not in manifest['eligible'] or e.get('decision') != ELIGIBLE:
        raise Refuse('NOT_ELIGIBLE', '%s khong thuoc danh sach du dieu kien cua manifest' % aid)
    row = ctx.by_id.get(aid)
    if row is None or row['status'] != 'PUBLISHED':
        raise Refuse('NOT_PUBLISHED', '%s khong phai hang PUBLISHED' % aid)
    if not POST_RE.match(row.get('output_path') or ''):
        raise Refuse('BAD_OUTPUT_PATH', '%s: output_path %r khong nam trong _posts/' % (aid, row.get('output_path')))
    for k in ('base_post_sha256', 'new_post_sha256', 'old_evidence_sha256', 'edits_sha256'):
        if not isinstance(e.get(k), str):
            raise Refuse('BAD_MANIFEST', '%s: manifest thieu %s' % (aid, k))
    if e['edits_sha256'] != edits_digest(e.get('edits')):
        raise Refuse('BAD_MANIFEST', '%s: edits_sha256 khong khop danh sach sua trong manifest' % aid)
    ev_path = ctx.root / 'data/qa' / (aid + '.json')
    if not ev_path.is_file():
        raise Refuse('NO_EVIDENCE', '%s khong co evidence' % aid)
    cur = (ctx.root / row['output_path']).read_bytes()
    ev_bytes = ev_path.read_bytes()
    evidence = json.loads(ev_bytes)
    if sha(cur) == e['new_post_sha256']:
        rev = evidence.get('revision') or {}
        if (rev.get('edits_sha256') == e['edits_sha256']
                and rev.get('previous_content_sha256') == e['base_post_sha256']
                and rev.get('previous_evidence_sha256') == e['old_evidence_sha256']):
            # tu khai provenance khong du: diem tren dia phai dung la dau ra scorer cho byte hien tai
            fresh = score_candidate(ctx, row, cur)
            diff = score_diff(evidence, fresh)
            if (diff or evidence.get('content_sha256') != sha(cur)
                    or evidence.get('matrix_row_sha256') != A.fingerprint(row)
                    or evidence.get('article_id') != aid):
                raise Refuse('UNEXPECTED_CURRENT_EVIDENCE',
                             '%s: bai da la ban moi nhung evidence khong khop cham lai doc lap (%s) — '
                             'khong coi la da sua' % (aid, ', '.join(diff[:6])))
            return 'already_current', None, None
        raise Refuse('UNEXPECTED_CURRENT_EVIDENCE',
                     '%s: bai da la ban moi nhung evidence khong phai ket qua cua manifest nay' % aid)
    if sha(cur) != e['base_post_sha256']:
        raise Refuse('POST_CHANGED_SINCE_PLAN', '%s: bai da doi tu luc plan' % aid)
    if sha(ev_bytes) != e['old_evidence_sha256']:
        raise Refuse('EVIDENCE_CHANGED_SINCE_PLAN', '%s: evidence da doi tu luc plan' % aid)
    d = derive(ctx, aid, e['edits'])
    if sha(d.old_post) != e['base_post_sha256'] or sha(d.new_post) != e['new_post_sha256'] \
            or sha(d.old_ev_bytes) != e['old_evidence_sha256'] \
            or e.get('base', BASE_INTACT) != d.base or e.get('domain_only_proof') != d.proof:
        raise Refuse('INPUT_CHANGED_SINCE_PLAN', '%s: byte ung vien/evidence/nen chung minh khac manifest' % aid)
    return 'ready', d, build_new_evidence(ctx, d, e['old_evidence_sha256'])


def apply_batch(ctx, manifest, ids, dry_run=False, skip_ineligible=False):
    if not (ctx.approval_ref or '').strip():
        raise Refuse('NO_APPROVAL', '--approval-ref la bat buoc (ghi vao provenance)')
    check_manifest(manifest)
    check_manifest_current(ctx, manifest)
    ctx.purpose, ctx.reason = manifest['purpose'], manifest['reason']
    ids = sorted(set(ids))
    if not ids:
        raise Refuse('NO_IDS', 'khong co ID nao duoc chon')
    if len(ids) > MAX_BATCH:
        raise Refuse('BATCH_TOO_LARGE', 'toi da %d ID/lo (lo co gioi han)' % MAX_BATCH)
    bad = [a for a in ids if not isinstance(a, str) or not AID_RE.match(a)]
    if bad:
        raise Refuse('BAD_ID', 'ID sai dinh dang: %s' % bad[:5])
    if ctx.batch_id is not None and not BATCH_ID_RE.match(ctx.batch_id):
        raise Refuse('BAD_BATCH_ID', 'batch-id chi gom A-Za-z0-9._- (toi da 80 ky tu)')
    if not ctx.batch_id:
        ctx.batch_id = 'revise-%s-%s-%s' % (
            datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d'), ids[0], ids[-1])
    prepared, skipped, ineligible = [], [], []
    for aid in ids:                         # kiểm HẾT trước khi ghi bất kỳ thứ gì
        try:
            state, d, new_ev = prepare(ctx, manifest, aid)
        except Refuse as e:
            if skip_ineligible and e.code in SKIPPABLE:
                ineligible.append({'id': aid, 'code': e.code, 'reason': e.msg})
                continue
            raise
        if state == 'already_current':
            skipped.append(aid)
        else:
            prepared.append((aid, d, new_ev))
    report = {'ok': True, 'batch_id': ctx.batch_id, 'dry_run': dry_run,
              'would_write' if dry_run else 'written': [a for a, _, _ in prepared],
              'already_current': skipped, 'skipped_ineligible': ineligible}
    if dry_run or not prepared:
        return report
    if ctx.guard:
        ctx.guard()               # cay lam viec con sach NGAY TRUOC khi ghi (lo chay vai phut)
    backup_rel = '%s/%s.json' % (BACKUP_DIR, ctx.batch_id)
    backup_path = ctx.root / backup_rel
    if backup_path.parent.resolve() != (ctx.root / BACKUP_DIR).resolve():
        raise Refuse('BAD_BATCH_ID', 'sao luu phai nam truc tiep trong %s' % BACKUP_DIR)
    if backup_path.exists():
        raise Refuse('BATCH_EXISTS', 'sao luu %s da ton tai — dung batch-id khac' % backup_rel)
    backup = {'schema': BACKUP_SCHEMA, 'batch_id': ctx.batch_id, 'created_at': now_iso(),
              'approval_ref': ctx.approval_ref, 'purpose': ctx.purpose, 'reason': ctx.reason,
              'head_at_apply': ctx.head, 'tool_commit': ctx.tool_commit,
              'manifest_sha256': sha(doc_text(manifest).encode('utf-8')), 'entries': {}}
    new_blobs = {}
    for aid, d, new_ev in prepared:
        new_ev_bytes = evidence_text(new_ev).encode('utf-8')
        new_blobs[aid] = (d.new_post, new_ev_bytes)
        backup['entries'][aid] = {
            'path': d.path,
            'old_post_text': d.old_post.decode('utf-8'),
            'old_post_sha256': sha(d.old_post), 'new_post_sha256': sha(d.new_post),
            'old_evidence_text': d.old_ev_bytes.decode('utf-8'),
            'old_evidence_sha256': sha(d.old_ev_bytes), 'new_evidence_sha256': sha(new_ev_bytes),
            'edits_sha256': d.edits_sha256, 'edits': d.edits}
    atomic_write(backup_path, doc_text(backup).encode('utf-8'))
    if json.loads(backup_path.read_text(encoding='utf-8')) != json.loads(doc_text(backup)):
        backup_path.unlink()
        raise Refuse('BACKUP_READBACK_FAILED', 'doc lai sao luu khong khop — chua sua file nao')
    attempted = []
    try:
        for aid, d, _ in prepared:
            post_p = ctx.root / d.path
            ev_p = ctx.root / 'data/qa' / (aid + '.json')
            if post_p.read_bytes() != d.old_post or ev_p.read_bytes() != d.old_ev_bytes:
                raise Refuse('FILES_CHANGED_DURING_APPLY', '%s: bai/evidence doi trong luc apply' % aid)
            attempted.append(aid)                 # TRUOC khi ghi: ngat giua atomic_write van duoc tinh
            atomic_write(post_p, new_blobs[aid][0])
            atomic_write(ev_p, new_blobs[aid][1])
            if sha(post_p.read_bytes()) != sha(new_blobs[aid][0]) \
                    or sha(ev_p.read_bytes()) != sha(new_blobs[aid][1]):
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
    """Apply that bai giua chung: tra moi ID MA LAN CHAY NAY DA BAT DAU GHI ve byte cu (ke ca ID ma mot
    ngat o giua atomic_write da doi ten file nhung chua kip ghi nhan). Chi xoa sao luu khi MOI ID do da
    bang byte cu; neu khong, giu sao luu va bao ro de khoi phuc tay."""
    ids = set(attempted)
    try:
        rollback_backup(ctx.root, backup, ids=ids, force_ids=ids)
    except BaseException:
        pass                                  # van kiem ket qua that o duoi
    left = []
    for aid in sorted(ids):
        b = backup['entries'][aid]
        post_p = ctx.root / b['path']
        ev_p = ctx.root / 'data/qa' / (aid + '.json')
        if (not post_p.is_file() or sha(post_p.read_bytes()) != b['old_post_sha256']
                or not ev_p.is_file() or sha(ev_p.read_bytes()) != b['old_evidence_sha256']):
            left.append(aid)
    if left:
        raise Refuse('PARTIAL_APPLY_BACKUP_KEPT',
                     'apply loi (%s: %s) va %d ID chua ve byte cu: %s — GIU sao luu %s, khoi phuc bang '
                     '`rollback --backup`' % (type(exc).__name__, exc, len(left), ', '.join(left[:5]),
                                              backup_path.name), left=left) from exc
    backup_path.unlink()                      # file nay do chinh lan chay nay tao


# ------------------------------------------------------------ verify / rollback

def check_backup_shape(backup):
    if not isinstance(backup.get('entries'), dict) or not backup['entries']:
        raise Refuse('BAD_BACKUP', 'sao luu khong co entries')
    for aid, b in backup['entries'].items():
        if not AID_RE.match(aid) or not isinstance(b, dict):
            raise Refuse('BAD_BACKUP', 'khoa entries %r khong hop le' % (aid,))
        if not isinstance(b.get('path'), str) or not POST_RE.match(b['path']):
            raise Refuse('BAD_BACKUP', '%s: path khong nam trong _posts/' % aid)
        for k in ('old_post_text', 'old_post_sha256', 'new_post_sha256', 'old_evidence_text',
                  'old_evidence_sha256', 'new_evidence_sha256', 'edits_sha256'):
            if not isinstance(b.get(k), str):
                raise Refuse('BAD_BACKUP', '%s: thieu %s' % (aid, k))
        if not isinstance(b.get('edits'), list):
            raise Refuse('BAD_BACKUP', '%s: thieu edits' % aid)


def verify_backup(ctx, backup, rescore=True):
    """Tương đương kiểm của validate.py + provenance + (rescore) chấm lại ĐỘC LẬP: điểm trên đĩa phải
    đúng là đầu ra scorer cho byte/hàng hiện tại. Trả danh sách lỗi."""
    check_backup_shape(backup)
    problems = []
    for aid, b in sorted(backup['entries'].items()):
        post_p = ctx.root / b['path']
        ev_p = ctx.root / 'data/qa' / (aid + '.json')
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
        ev = json.loads(ev_raw)
        row = ctx.by_id.get(aid)
        if row is None or row['status'] != 'PUBLISHED' or row.get('output_path') != b['path']:
            problems.append('%s: khong con PUBLISHED / output_path doi' % aid)
            continue
        if ev.get('content_sha256') != sha(post_raw):
            problems.append('%s: content_sha256 khong khop bai hien tai' % aid)
        if ev.get('matrix_row_sha256') != A.fingerprint(row):
            problems.append('%s: matrix_row_sha256 khong khop hang hien tai' % aid)
        if ev.get('source_path') != row['output_path']:
            problems.append('%s: source_path != output_path' % aid)
        if ev.get('article_id') != aid:
            problems.append('%s: article_id trong evidence la %r' % (aid, ev.get('article_id')))
        if not score_ok(ev):
            problems.append('%s: diem/cong QA khong dat nguong' % aid)
        # bai cu + danh sach sua => dung byte bai hien tai; bat bien front matter/lien ket/heading
        old_text = b['old_post_text']
        if sha(old_text.encode('utf-8')) != b['old_post_sha256']:
            problems.append('%s: sao luu bai cu hong (sha khong khop)' % aid)
            continue
        try:
            replay, changed = apply_edits(old_text, b['edits'])
            check_invariants(old_text, replay, changed)
        except Refuse as e:
            problems.append('%s: danh sach sua khong hop le (%s)' % (aid, e.code))
            continue
        if replay.encode('utf-8') != post_raw:
            problems.append('%s: bai hien tai != bai cu + danh sach sua' % aid)
        if edits_digest(b['edits']) != b['edits_sha256']:
            problems.append('%s: edits_sha256 khong khop danh sach sua' % aid)
        rev = ev.get('revision') or {}
        old_ev_sha = sha(b['old_evidence_text'].encode('utf-8'))
        old_ev = json.loads(b['old_evidence_text'])
        old_post = old_text.encode('utf-8')
        if rev.get('base', BASE_INTACT) == BASE_DOMAIN:
            # nen lech hash: chung minh LAI tu lich su git (baseline ghim), khong tin bang chung trong sao luu
            try:
                proof = domain_drift_proof(ctx, row, old_post, old_ev)
            except Refuse as e:
                problems.append('%s: nen DOMAIN_ONLY_PROVEN khong chung minh lai duoc (%s)' % (aid, e.msg))
            else:
                if rev.get('domain_only_proof') != proof:
                    problems.append('%s: domain_only_proof trong evidence khac chung minh lai tu git' % aid)
        elif rev.get('base', BASE_INTACT) != BASE_INTACT:
            problems.append('%s: revision.base la %r' % (aid, rev.get('base')))
        elif (sha(old_post) != old_ev.get('content_sha256')
              or old_ev.get('matrix_row_sha256') != A.fingerprint(row)):
            problems.append('%s: bai cu/hang matrix khong khop evidence cu (nen INTACT)' % aid)
        if (b['old_evidence_sha256'] != old_ev_sha
                or rev.get('previous_evidence_sha256') != old_ev_sha
                or rev.get('previous_content_sha256') != old_ev.get('content_sha256')
                or rev.get('previous_matrix_row_sha256') != old_ev.get('matrix_row_sha256')
                or rev.get('new_content_sha256') != ev.get('content_sha256')
                or rev.get('edits_sha256') != b['edits_sha256']
                or not (rev.get('approval_ref') or '').strip()):
            problems.append('%s: provenance khong khop sao luu' % aid)
        for k in ('scored_at', 'published_at'):
            if old_ev.get(k) and ev.get(k) != old_ev.get(k):
                problems.append('%s: %s lich su khong duoc giu nguyen' % (aid, k))
        lost = sorted(k for k in old_ev if k not in ev and k != 'revision')
        if lost:
            problems.append('%s: mat chu thich lich su cua evidence cu: %s' % (aid, ', '.join(lost[:5])))
        if rescore:
            diff = score_diff(ev, score_candidate(ctx, row, post_raw))
            if diff:
                problems.append('%s: diem trong evidence khac diem cham lai doc lap (%s)'
                                % (aid, ', '.join(diff[:6])))
    return problems


def rollback_backup(root, backup, ids=None, dry_run=False, force_ids=None):
    """Khôi phục byte-exact bài + evidence cũ. Mỗi file chỉ được khôi phục khi còn đúng bản ĐÃ GHI
    (không đè thay đổi của người khác); `force_ids` (chỉ nội bộ, cho _abort_apply) khôi phục cả file
    đang ở bản cũ hoặc đã ghi dở."""
    check_backup_shape(backup)
    if ids is not None:
        unknown = sorted(set(ids) - set(backup['entries']))
        if unknown:
            raise Refuse('UNKNOWN_IDS', 'ID khong co trong sao luu: %s' % unknown[:5])
    out = {'restored': [], 'skipped_changed_since_apply': [], 'dry_run': dry_run}
    root = pathlib.Path(root)
    for aid, b in sorted(backup['entries'].items()):
        if ids is not None and aid not in ids:
            continue
        old_post = b['old_post_text'].encode('utf-8')
        old_ev = b['old_evidence_text'].encode('utf-8')
        if sha(old_post) != b['old_post_sha256'] or sha(old_ev) != b['old_evidence_sha256']:
            raise Refuse('BACKUP_CORRUPT', '%s: sao luu hong' % aid)
        post_p, ev_p = root / b['path'], root / 'data/qa' / (aid + '.json')
        forced = force_ids is not None and aid in force_ids
        plan = []
        for p, old, new_sha, old_sha in ((post_p, old_post, b['new_post_sha256'], b['old_post_sha256']),
                                         (ev_p, old_ev, b['new_evidence_sha256'], b['old_evidence_sha256'])):
            cur = sha(p.read_bytes()) if p.is_file() else None
            if cur == old_sha:
                continue                               # da o byte cu
            if cur != new_sha and not forced:
                plan = None
                break
            plan.append((p, old))
        if plan is None:
            out['skipped_changed_since_apply'].append(aid)
            continue
        if not dry_run:
            for p, old in plan:
                atomic_write(p, old)
                if sha(p.read_bytes()) != sha(old):
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
    p.add_argument('--patches', required=True)
    p.add_argument('--out')
    p.add_argument('--allow-dirty', action='store_true',
                   help='plan tren cay khac HEAD (manifest ghi head_bound: false, apply se tu choi)')
    p.add_argument('--domain-drift', action='store_true',
                   help='nhan evidence lech hash CHI KHI chung minh duoc DOMAIN_ONLY_PROVEN (baseline ghim)')
    a_ = sub.add_parser('apply')
    a_.add_argument('--manifest', required=True)
    a_.add_argument('--approval-ref', default='')
    a_.add_argument('--ids', default='')
    a_.add_argument('--limit', type=int, default=0)
    a_.add_argument('--offset', type=int, default=0)
    a_.add_argument('--batch-id', default=None)
    a_.add_argument('--dry-run', action='store_true')
    a_.add_argument('--skip-ineligible', action='store_true',
                    help='ID khong con du dieu kien luc apply bi BO QUA (bao cao) thay vi dung ca lo')
    a_.add_argument('--domain-drift', action='store_true',
                    help='bat buoc khi manifest lap bang plan --domain-drift')
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
            patches_path = os.path.abspath(a.patches)
            dirty = A.dirty_inputs(ROOT)
            if dirty and not a.allow_dirty:
                require_clean_tree(ROOT)
            patches = json.loads(pathlib.Path(patches_path).read_text(encoding='utf-8'))
            ctx = make_ctx(ROOT, domain_drift=a.domain_drift)
            manifest = make_plan(ctx, patches, head_bound=not dirty)
            text = doc_text(manifest)
            if out_path:
                atomic_write(out_path, text.encode('utf-8'))
                print(json.dumps({'ok': True, 'out': out_path, 'counts': manifest['counts'],
                                  'excluded': {k: len(x) for k, x in manifest['excluded'].items()}},
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
            ctx = make_ctx(ROOT, a.approval_ref, a.batch_id, domain_drift=a.domain_drift)
            ctx.guard = lambda: require_clean_tree(ROOT)
            print(json.dumps(apply_batch(ctx, manifest, ids, a.dry_run, a.skip_ineligible),
                             ensure_ascii=False, indent=2))
            return 0
        backup = json.loads(pathlib.Path(a.backup).read_text(encoding='utf-8'))
        if backup.get('schema') != BACKUP_SCHEMA:
            raise Refuse('BAD_BACKUP', 'schema sao luu khong dung')
        if a.cmd == 'verify':
            ctx = make_ctx(ROOT)
            problems = verify_backup(ctx, backup, rescore=not a.no_rescore)
            print(json.dumps({'ok': not problems, 'checked': len(backup['entries']),
                              'problems': problems}, ensure_ascii=False, indent=2))
            return 0 if not problems else 1
        ids = None
        if a.ids is not None:
            ids = set(_ids(a.ids))
            if not ids:
                raise Refuse('BAD_IDS', '--ids rong: bo --ids de khoi phuc ca lo')
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
