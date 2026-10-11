#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""push-selection.py — CANONICAL queue selector của đường nóng publish.

Hợp đồng 6 workflow (docs/factory-workflow-contract.md): factory-publish.yml
gọi script NÀY để chọn queue từ push — KHÔNG còn selector Python inline
trùng lặp trong workflow YAML (một nguồn sự thật duy nhất, tránh drift
giữa hai implementation).

Input (giống capture push scope của workflow — output của git diff,
tách khỏi git để test fixture không cần git):
  --added <file>     path ADDED trong push    (git diff --diff-filter=A)
  --modified <file>  path MODIFIED trong push (git diff --diff-filter=M)
  --changed <file>   (tùy chọn) MỌI path đổi trong push — chỉ để CẢNH BÁO
                     writer chạm path ngoài phạm vi writer
  --backlog          DRAIN: ngoài draft của push này, quét luôn mọi draft
                     đang xếp hàng trong _drafts/ của cây làm việc (main
                     mới nhất). Run bị GitHub hủy (concurrency chỉ giữ 1
                     run chờ) KHÔNG làm mất draft: run kế tiếp nhặt lại.
  Mỗi dòng một path tương đối với gốc repo (ví dụ `_drafts/<file>.md`).

Output:
  - JSON deterministic trên stdout (kết quả selection cho test/log);
  - nếu env GITHUB_OUTPUT tồn tại: append `queue=`, `mode=`, `pairs=`
    (step outputs — mọi step sau của workflow đọc
    `steps.select.outputs.queue != ''` để biết có queue hay không).

Semantics (giữ NGUYÊN semantics của selector cũ; phần mới ghi rõ):
  - queue 2..10 draft/push: TỐI ĐA 10 ID (MAX_QUEUE_PER_PUSH; lease limit
    mỗi writer); KHÔNG có min — push 1 draft hợp lệ; queue LẺ được chia
    pair (pair cuối 1 ID). Với --backlog tổng queue một run tối đa 30 ID
    (MAX_QUEUE_PER_RUN = 3 writer x 10), phần dư chờ run kế;
  - EXACT article_id: regex `^article_id:\\s*(BLG-\\d+)` trong 2000 ký tự
    đầu của draft; file KHÔNG phải `.md` bị bỏ qua (kể cả `.nudge-Wx`);
    draft template (bài nhập mẫu) bị bỏ qua;
  - REFUSE (fail-closed, exit 3 — KHÔNG đổi gì) cho draft của PUSH:
      draft thiếu article_id trong frontmatter /
      ID trùng nhau trong cùng push /
      > 10 draft một push /
      ID không có trong matrix /
      hàng EXISTING, BLOCKED, REVIEW (bảo vệ — KHÔNG BAO GIỜ ghi đè) /
      registry hỏng (multi-writer mode không xác định được chủ);
  - RACE PUSH TRÙNG / RE-RUN (superseded — an toàn, KHÔNG refuse): hàng
      PUBLISHED trong push = chính push này đã được một queue run khác
      publish (hai push writer sát nhau; concurrency group
      factory-publish tuần tự hóa các run), hoặc draft đã được chuyển
      sang _posts/ rồi run cũ được chạy lại. Bỏ qua sạch
      (`published_edits`, exit 0 — run GREEN no-op, KHÔNG RED). Publisher
      KHÔNG BAO GIỜ đụng lại bài đã publish;
  - ENGINE-READY PREFLIGHT (engine_problem): draft "độc" bị chặn TRƯỚC khi vào
    queue — push: REFUSE; backlog: CÁCH LY. Gồm: không phải UTF-8; frontmatter
    thiếu `date`/title/categories/description (QA raise hoặc gate từ chối);
    còn placeholder; `date` sai dạng/lệch tên file; tên file khác
    YYYY-MM-DD-<slug hàng>.md; hai draft cho một hàng hoặc factory-operator
    (glob đầu tiên theo tên) sẽ chọn FILE KHÁC. Nhờ đó một draft hỏng KHÔNG
    làm MỌI run đỏ (backlog nạp lại mỗi run) và không kẹt PASS vô hạn;
  - PUSH BỊ TỪ CHỐI VẪN DRAIN: khi push vi phạm, selector không dừng ở exit 3
    nếu backlog có draft hợp lệ của writer khác (run chờ của họ có thể đã bị
    run này thay thế): queue backlog vẫn chạy, output `refused=true` để
    workflow làm ĐỎ run ở step cuối. Backlog rỗng: exit 3 ngay như cũ;
  - production-control paused: bỏ ID PLANNED khỏi queue, VẪN xử lý hàng
    in-flight (repair/PASS) — draft PLANNED không làm đói hàng đã claim;
  - draft trong BACKLOG (không thuộc push) được phân loại LENIENT: hợp lệ
    thì vào queue; không hợp lệ (thiếu id, ID lạ, trạng thái bảo vệ, thiếu
    lease, sai chủ) thì CÁCH LY (`quarantine`, báo trong log) — một draft
    hỏng KHÔNG BAO GIỜ chặn các draft khác (không deadlock queue chung);
    hàng REPAIR chỉ vào queue khi nội dung draft ĐỔI so với bằng chứng QA
    cuối (sha256) — không QA lại vô hạn bản đã FAIL;
  - deterministic: queue sắp theo THỨ TỰ MATRIX (không theo tên file);
  - mode: `new` (queue chứa hàng PLANNED cần claim) / `repair`
    (KHÔNG claim lại từ đầu — repair rows skip claim);
  - production-control enabled=false + lần chạy cần claim bài mới ->
    exit 0 sạch TRƯỚC khi claim (queue rỗng; push repair-only vẫn hợp lệ);
  - không draft trong push -> no-op exit 0;
  - OWNERSHIP MULTI-WRITER (chỉ KÍCH HOẠT khi data/state/writer-claims.json
    TỒN TẠI — presence = multi-writer mode ON; registry vắng = single-writer
    legacy, semantics cũ giữ nguyên; registry HỎNG = refuse fail-closed):
      * hàng PLANNED: PHẢI có lease sống (scripts/factory/writer-claim.py)
        và draft PHẢI khai `writer: Wx` khớp writer đang giữ lease của ID
        đó; nếu lease có session và draft khai `writer_session:` thì phải
        khớp (draft không khai -> cảnh báo, tương thích ngược);
      * hàng in-flight (WRITING/QA/PASS/REPAIR) có lease sống của writer
        KHÁC với draft đã ĐỔI nội dung -> sai chủ (không writer nào sửa
        draft thuộc writer khác); nội dung CHƯA đổi so với bằng chứng QA
        (đang chờ publish) không cần kiểm chủ (hết hạn lease không giam
        hàng); orphan (không lease sống) mà draft bị SỬA sau lần QA gần
        nhất phải được NHẬN trước (`begin --ids ... --adopt`) — refuse ở push,
        cách ly ở drain; orphan chưa có bằng chứng (publisher chạy dở) tiếp
        tục;
      * một ID nằm trong >= 2 lease SỐNG (merge git thô) -> registry mơ hồ
        chủ sở hữu -> refuse fail-closed như registry hỏng;
      * cắt trần 30 ID/run: hàng in-flight trước rồi PLANNED (mỗi nhóm theo
        matrix order); lọc production-control paused làm TRƯỚC khi cắt;
    vi phạm với draft của push -> REFUSE fail-closed exit 3 (KHÔNG đổi gì);
  - selector CHỈ ĐỌC: KHÔNG mutate matrix/checkpoint/production-control/
    bất kỳ file nào của repo (chỉ ghi stdout hoặc $GITHUB_OUTPUT);
  - KHÔNG AI, KHÔNG API, KHÔNG secrets.

Thoát: 0 = chọn xong (kể cả no-op/paused), 3 = refuse (fail-closed).
"""
import argparse
import csv
import glob
import hashlib
import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MATRIX = 'data/content-matrix.csv'
CONTROL = 'data/factory/production-control.json'
QA_DIR = 'data/qa'
DRAFTS_DIR = '_drafts'
REGISTRY_REL = 'data/state/writer-claims.json'

# Hợp đồng turbo queue: tối đa 10 draft/push; consume chia pair 2
# (pair cuối của queue lẻ có 1 ID). Một run (backlog) tối đa 30 ID.
MAX_QUEUE_PER_PUSH = 10
MAX_QUEUE_PER_RUN = 30
PAIR_SIZE = 2

FRONT_ID_RE = re.compile(r'^article_id:\s*(BLG-\d+)', re.M)
WRITER_RE = re.compile(r'^writer:\s*(W\d+)\s*$', re.M)
SESSION_RE = re.compile(r'^writer_session:\s*(\S+)\s*$', re.M)
# chuỗi GHÉP để file này không chứa slug template nguyên vẹn — draft-leak
# gate grep slug này trên cây build (scripts/ bị Jekyll copy)
TEMPLATE_SLUG = 'mau' + '-nhap' + '-bai' + '-moi'
# Hàng bị REFUSE khi xuất hiện trong push (vi phạm thật): EXISTING/BLOCKED/
# REVIEW. Hàng PUBLISHED KHÔNG nằm trong danh sách này — xem RACE PUSH
# TRÙNG ở docstring: bị bỏ qua sạch (published_edits, exit 0).
REFUSED_STATUSES = ('EXISTING', 'BLOCKED', 'REVIEW')
INFLIGHT = ('WRITING', 'QA', 'PASS', 'REPAIR')
# trạng thái engine xử lý được trong queue (PLANNED cần claim; còn lại
# resume): mọi trạng thái khác (FAIL lạ...) bị coi là không hợp lệ
ELIGIBLE = ('PLANNED',) + INFLIGHT + ('FAIL',)
# publish-gate.py đòi các khóa này trong frontmatter (QA KHÔNG chấm
# `categories`/`title` — draft thiếu vẫn PASS QA rồi bị gate từ chối)
GATE_FRONT_FIELDS = ('title:', 'date:', 'categories:', 'description:')
# path writer được phép chạm trong một push draft (chỉ để CẢNH BÁO)
WRITER_PATH_PREFIXES = ('_drafts/', 'data/factory/refill-batches/')
WRITER_PATH_FILES = (REGISTRY_REL, 'data/factory/refill-request.json',
                     'data/factory/extract-request.json')


class Refuse(Exception):
    """Push vi phạm hợp đồng queue — fail-closed, KHÔNG đổi gì."""


def load_control():
    try:
        with open(os.path.join(ROOT, CONTROL), encoding='utf-8') as f:
            c = json.load(f) or {}
        return bool(c.get('enabled', True))
    except Exception:
        return True


def load_matrix():
    with open(os.path.join(ROOT, MATRIX), encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    return {r['id']: r for r in rows}, rows


def read_paths(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return [ln.strip() for ln in f.read().splitlines() if ln.strip()]


def claim_registry():
    # Đọc writer-claims registry (CHỈ ĐỌC, KHÔNG prune/mutate). Trả
    # (reg, live) khi multi-writer mode ON; trả None khi registry KHÔNG
    # tồn tại (single-writer legacy — KHÔNG enforce ownership); registry
    # HỎNG -> raise Refuse (fail-closed, KHÔNG coi là rỗng/legacy). Nạp
    # writer-claim.py qua importlib (tên file có gạch ngang) để dùng
    # CHÍNH XÁC load_registry/_live_leases — một nguồn sự thật.
    path = os.environ.get(
        'WRITER_CLAIMS',
        os.path.join(ROOT, 'data', 'state', 'writer-claims.json'))
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location(
        'blog_writer_claim',
        os.path.join(ROOT, 'scripts', 'factory', 'writer-claim.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        reg = mod.load_registry(path)
    except mod.OwnershipConflict as e:
        raise Refuse('registry writer-claims khong nhat quan: %s — '
                     'khong rollback lease song; cho het TTL hoac coordinator '
                     'hoa giai co bang chung' % e)
    except mod.RegistryCorrupt as e:
        raise Refuse('registry writer-claims hong (%s) — multi-writer mode '
                     'khong xac dinh duoc chu; chay: writer-claim.py '
                     'repair-registry --from-git' % e)
    dup = mod.live_conflicts(reg)
    if dup:
        # cùng một ID thuộc >= 2 lease SỐNG: chủ sở hữu mơ hồ -> KHÔNG chọn
        # đại slot nào (fail-closed như registry hỏng)
        raise Refuse('registry writer-claims khong nhat quan: %s — moi ID chi '
                     'duoc mot lease song; sua bang writer-claim.py '
                     'repair-registry / release truoc khi publish tiep'
                     % '; '.join('%s giu boi %s' % (a, '+'.join(ws))
                                 for a, ws in sorted(dup.items())[:5]))
    return reg, mod._live_leases(reg)


def _sha256_file(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def evidence_sha(aid):
    p = os.path.join(ROOT, QA_DIR, aid + '.json')
    try:
        with open(p, encoding='utf-8') as f:
            return (json.load(f) or {}).get('content_sha256')
    except (OSError, ValueError):
        return None


def content_state(aid, rel):
    """(changed, modified) của draft so với bằng chứng QA của ID: `changed` =
    chưa có bằng chứng HOẶC sha khác; `modified` = CÓ bằng chứng và sha khác
    (draft bị sửa sau lần QA gần nhất)."""
    ev = evidence_sha(aid)
    if ev is None or rel is None:
        return True, False
    differs = _sha256_file(os.path.join(ROOT, rel)) != ev
    return differs, differs


def parse_draft(path):
    """(aid, writer, session) của một draft (đọc 2000 ký tự đầu). Raise
    OSError nếu không đọc được; trả aid None nếu thiếu article_id."""
    try:
        with open(path, encoding='utf-8') as fh:
            head = fh.read()[:2000]
    except UnicodeDecodeError as e:         # file nhị phân/không phải UTF-8
        raise OSError('khong phai UTF-8: %s' % e)
    m = FRONT_ID_RE.search(head)
    wm = WRITER_RE.search(head)
    sm = SESSION_RE.search(head)
    return (m.group(1) if m else None, wm.group(1) if wm else None,
            sm.group(1) if sm else None)


def row_slug(row):
    """Slug draft của một hàng matrix — CÙNG cách factory-operator.find_draft."""
    out = row.get('output_path') or ''
    if out.startswith('_posts/{date}-') and out.endswith('.md'):
        return out[len('_posts/{date}-'):-3]
    m = re.match(r'_posts/\d{4}-\d{2}-\d{2}-(.+)\.md$', out)
    return m.group(1) if m else None


def engine_problem(row, rel):
    """None nếu draft `rel` đi được qua factory-operator (QA) + publish-gate;
    ngược lại chuỗi mô tả. Chặn TRƯỚC khi vào queue các draft "độc" mà nếu để
    lọt sẽ làm MỌI run đỏ (backlog nạp lại mỗi run) hoặc kẹt PASS vô hạn:
      - không phải UTF-8 / frontmatter có `---` nhưng thiếu khóa `date` ⇒
        factory-operator.qa_check_one raise ⇒ FATAL cả queue;
      - thiếu title/date/categories/description, còn placeholder ⇒ QA vẫn PASS
        nhưng publish-gate từ chối ⇒ hàng PASS lặp mãi;
      - `date` không phải YYYY-MM-DD hoặc lệch tiền tố tên file (Jekyll hỏng
        khi build); tên file khác YYYY-MM-DD-<slug hàng>.md;
      - hai draft cho cùng một hàng, hoặc find_draft (glob đầu tiên theo tên)
        sẽ chọn FILE KHÁC file này ⇒ QA/publish nhầm bản (nhầm chủ).
    Draft KHÔNG có frontmatter vẫn để QA chấm (REPAIR có feedback cho chủ)."""
    aid = row['id']
    slug = row_slug(row)
    if not slug:
        return '%s: output_path matrix khong dung dinh dang (%s)' % (
            aid, row.get('output_path'))
    path = rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
    try:
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as e:
        return '%s: draft %s khong doc duoc (%s)' % (aid, rel,
                                                     e.__class__.__name__)
    base = os.path.basename(path)
    fm = re.match(r'^---\n(.*?)\n---', text, re.S)
    if fm:
        front_text = fm.group(1)
        front = {}
        for line in front_text.splitlines():
            m = re.match(r'([a-z_]+):\s*(.*)$', line)
            if m:
                front[m.group(1)] = m.group(2).strip()
        if 'date' not in front:
            return ('%s: frontmatter thieu khoa `date:` (QA khong chay duoc '
                    'tren draft nay)' % aid)
        lacking = [f for f in GATE_FRONT_FIELDS if f not in front_text]
        if lacking:
            return ('%s: frontmatter thieu %s (publish-gate se tu choi)'
                    % (aid, ' '.join(lacking)))
        if not re.search(r'^article_id:\s*BLG-\d+', front_text, re.M):
            return '%s: article_id phai nam TRONG frontmatter' % aid
        dm = re.match(r'(\d{4}-\d{2}-\d{2})', front.get('date', ''))
        if not dm:
            return ('%s: `date:` khong dung dang YYYY-MM-DD (%r)'
                    % (aid, front.get('date', '')[:30]))
        if base != '%s-%s.md' % (dm.group(1), slug):
            return ('%s: ten file phai la %s-%s.md (date frontmatter + slug '
                    'hang matrix), dang la %s' % (aid, dm.group(1), slug,
                                                  base))
    if 'MẪU NHẬP BÀI' in text or 'lorem' in text.lower():
        return '%s: draft con placeholder nhap mau (publish-gate tu choi)' % aid
    if not re.match(r'^\d{4}-\d{2}-\d{2}-%s\.md$' % re.escape(slug), base):
        return ('%s: ten file %s khong khop YYYY-MM-DD-%s.md cua hang matrix'
                % (aid, base, slug))
    d = os.path.join(ROOT, DRAFTS_DIR)
    exact = [fn for fn in (os.listdir(d) if os.path.isdir(d) else [])
             if re.match(r'^\d{4}-\d{2}-\d{2}-%s\.md$' % re.escape(slug), fn)]
    if len(exact) > 1:
        return ('%s: %d draft cho cung mot hang (%s) — chi giu MOT ban, xoa '
                'ban thua' % (aid, len(exact), ', '.join(sorted(exact)[:4])))
    hits = sorted(glob.glob(os.path.join(d, '*-%s.md' % slug)))
    if hits and os.path.abspath(hits[0]) != os.path.abspath(path):
        return ('%s: factory-operator se QA/publish file %s thay vi %s '
                '(glob dau tien theo ten) — doi ten/xoa ban thua'
                % (aid, os.path.basename(hits[0]), base))
    return None


def slug_of_path(f):
    m = re.match(r'^(?:.*/)?\d{4}-\d{2}-\d{2}-(.+)\.md$', f)
    return m.group(1) if m else None


def ids_from(paths, by_slug=None, stale=None):
    """EXACT article_id từ các path draft (port nguyên vẹn inline cũ):
    chỉ file `.md`; template bị bỏ qua; thiếu article_id -> REFUSE ngay
    (fail-closed, KHÔNG âm thầm bỏ qua draft thật). Draft đã biến mất vì
    ĐÃ publish (run cũ chạy lại — idempotent) -> ghi vào `stale`, bỏ qua.
    Trả list (aid, writer, session, path)."""
    out = []
    for f in paths:
        if not f.endswith('.md'):
            continue
        if TEMPLATE_SLUG in f:
            continue  # template bai nhap mau, khong phai bai that
        try:
            aid, writer, session = parse_draft(os.path.join(ROOT, f)
                                                if not os.path.isabs(f) else f)
        except OSError as e:
            row = (by_slug or {}).get(slug_of_path(f))
            if row is not None and row['status'] == 'PUBLISHED':
                if stale is not None:
                    stale.append(row['id'])
                continue
            # fail-closed: draft không đọc được -> REFUSE sạch (KHÔNG
            # âm thầm bỏ qua; inline cũ crash traceback, vẫn fail-closed)
            raise Refuse('draft %s khong doc duoc trong HEAD (%s)'
                         % (f, e.__class__.__name__))
        if not aid:
            raise Refuse('draft %s thieu article_id trong frontmatter' % f)
        out.append((aid, writer, session, f))
    return out


def ownership_problem(aid, status, writer, session, registry, changed,
                      modified=False):
    """None nếu hợp lệ, hoặc chuỗi mô tả vi phạm. `changed`: nội dung draft
    đã đổi so với bằng chứng QA (hoặc chưa có bằng chứng); `modified`: CÓ
    bằng chứng QA và draft khác nó (ai đó đã SỬA draft sau lần QA gần nhất)."""
    if registry is None:
        return None, None
    reg, live = registry
    holder = live.get(aid)
    if status == 'PLANNED':
        if holder is None:
            return ('%s: khong co lease song trong writer-claims '
                    'registry (multi-writer mode ON)' % aid), None
    else:
        # hàng in-flight: nội dung chưa đổi (đang chờ publish) không cần
        # kiểm chủ. Orphan (không lease sống) mà draft bị SỬA sau lần QA: phải
        # NHẬN trước (`begin --ids ... --adopt`) — "nhận việc orphan chỉ qua
        # --adopt" (AGENTS.md). Orphan chưa có bằng chứng (publisher chạy dở
        # trước khi QA) thì tiếp tục: không ai sửa gì.
        if not changed:
            return None, None
        if holder is None:
            if modified:
                return ('%s: hang %s khong co lease song (orphan) ma draft da '
                        'bi sua sau lan QA truoc — nhan bang `writer-session.py '
                        'begin --ids %s --adopt` roi push lai' % (aid, status,
                                                                    aid)), None
            return None, None
    hw, hl = holder
    if writer != hw:
        return ('%s: draft khai writer %s nhung lease dang thuoc writer %s'
                % (aid, writer, hw)), None
    lease_sess = hl.get('session')
    if lease_sess and session and session != lease_sess:
        return ('%s: draft khai writer_session %s nhung lease cua writer %s '
                'thuoc session %s' % (aid, session, hw, lease_sess)), None
    warn = None
    if lease_sess and not session:
        warn = ('%s: draft khong khai writer_session (lease writer %s co '
                'session %s) — nen khai de chong ghi de' % (aid, hw,
                                                           lease_sess))
    return None, warn


class PushRefuse(Refuse):
    """Push bị từ chối (fail-closed) — KHÔNG chặn việc drain backlog."""


def select(added, modified, backlog=False, changed=()):
    """Chọn queue từ push (+ backlog); chỉ ĐỌC repository state, trả dict
    deterministic (không side-effect)."""
    control_enabled = load_control()
    by_id, rows = load_matrix()
    order = {r['id']: i for i, r in enumerate(rows)}
    by_slug = {}
    for r in rows:
        if r['status'] == 'PUBLISHED':
            by_slug[r.get('slug') or ''] = r
            sl = slug_of_path(r.get('output_path') or '')
            if sl:
                by_slug.setdefault(sl, r)
    out = {
        'proceed': False, 'mode': 'skip', 'queue': [], 'claim_ids': [],
        'qa_ids': [], 'pairs': 0, 'refuse': None,
        'control_enabled': control_enabled,
        'multi_writer': False, 'writers': {},
        'published_edits': [], 'backlog': [], 'quarantine': [],
        'waiting_repair': [], 'warnings': [],
    }

    try:
        registry = claim_registry()
    except Refuse as e:
        out['multi_writer'] = True
        out['refuse'] = str(e)
        return out
    out['multi_writer'] = registry is not None

    # cảnh báo (KHÔNG chặn): push draft nhưng chạm path ngoài phạm vi writer
    if changed:
        odd = [p for p in changed
               if not p.startswith(WRITER_PATH_PREFIXES)
               and p not in WRITER_PATH_FILES]
        if odd:
            out['warnings'].append(
                'push draft chua path ngoai pham vi writer (%d): %s'
                % (len(odd), ', '.join(sorted(odd)[:8])))

    def validate_push():
        """Kiểm STRICT draft của push. Trả (queue, declared, declared_sess,
        push_paths); raise PushRefuse khi vi phạm (fail-closed)."""
        stale = []
        try:
            entries = (ids_from(added, by_slug, stale)
                       + ids_from(modified, by_slug, stale))
        except Refuse as e:
            raise PushRefuse(str(e))
        if stale:
            out['published_edits'] = sorted(set(stale),
                                            key=lambda i: order[i])
        queue = [a for a, _, _, _ in entries]
        declared = {a: w for a, w, _, _ in entries}
        declared_sess = {a: s for a, _, s, _ in entries}
        push_paths = {f for _, _, _, f in entries}

        if len(set(queue)) != len(queue):
            raise PushRefuse('id trung nhau trong cung mot push')
        if len(queue) > MAX_QUEUE_PER_PUSH:
            raise PushRefuse('%d draft > toi da 10 moi push (turbo queue)'
                             % len(queue))
        unknown = [i for i in queue if i not in by_id]
        if unknown:
            raise PushRefuse('id khong co trong matrix: %s'
                             % ','.join(unknown))
        # RACE PUSH TRÙNG (superseded): một queue run khác có thể đã publish
        # đúng các ID của push này giữa lúc writer tạo push và lần chạy này
        # refresh truth. Bỏ qua sạch — exit 0 no-op, KHÔNG refuse RED;
        # publisher KHÔNG BAO GIỜ đụng lại hàng PUBLISHED.
        published = sorted((i for i in queue
                            if by_id[i]['status'] == 'PUBLISHED'),
                           key=lambda i: order[i])
        if published:
            out['published_edits'] = sorted(
                set(out['published_edits']) | set(published),
                key=lambda i: order[i])
            queue = [i for i in queue
                     if by_id[i]['status'] != 'PUBLISHED']
        bad_status = [i for i in queue
                      if by_id[i]['status'] in REFUSED_STATUSES
                      or by_id[i]['status'] not in ELIGIBLE]
        if bad_status:
            raise PushRefuse('id da xong/khoa, khong duoc sua lai: %s'
                             % ','.join(bad_status))

        # ownership + engine-ready của draft PUSH (strict: vi phạm -> refuse)
        bad, warns = [], []
        for aid in queue:
            st = by_id[aid]['status']
            changed_content, edited = True, False
            fp = push_paths_of(aid, entries)
            if st != 'PLANNED':
                changed_content, edited = content_state(aid, fp)
            prob, warn = ownership_problem(aid, st, declared.get(aid),
                                           declared_sess.get(aid), registry,
                                           changed_content, edited)
            if prob:
                bad.append(prob)
            if warn:
                warns.append(warn)
            prob = engine_problem(by_id[aid], fp)
            if prob:
                bad.append(prob)
        if bad:
            raise PushRefuse('; '.join(bad))
        out['warnings'].extend(warns)
        return queue, declared, declared_sess, push_paths

    try:
        queue, declared, declared_sess, push_paths = validate_push()
        refused_paths = set()
    except PushRefuse as e:
        out['refuse'] = str(e)
        if not backlog:
            return out
        # push bị từ chối: vẫn DRAIN backlog (draft hợp lệ của writer khác
        # không được kẹt vì push hỏng của một writer — run chờ có thể đã bị
        # run này thay thế); draft của push hỏng bị cách ly ở dưới.
        queue, declared, declared_sess = [], {}, {}
        push_paths = set()
        refused_paths = {f for f in list(added) + list(modified)
                         if f.endswith('.md') and TEMPLATE_SLUG not in f}

    # ---- BACKLOG: drain draft đang xếp hàng (lenient, không chặn queue)
    if backlog:
        taken = set(queue) | set(out['published_edits'])
        seen_ids = {}
        d = os.path.join(ROOT, DRAFTS_DIR)
        files = sorted(fn for fn in (os.listdir(d) if os.path.isdir(d)
                                     else []) if fn.endswith('.md'))
        for fn in files:
            rel = '%s/%s' % (DRAFTS_DIR, fn)
            if TEMPLATE_SLUG in rel or rel in push_paths:
                continue
            if rel in refused_paths:
                out['quarantine'].append({
                    'path': rel,
                    'reason': 'thuoc push bi tu choi (xem REFUSED)'})
                continue
            try:
                aid, writer, session = parse_draft(os.path.join(d, fn))
            except OSError as e:
                out['quarantine'].append({'path': rel,
                                          'reason': 'khong doc duoc (%s)'
                                          % str(e)[:60]})
                continue
            if not aid:
                out['quarantine'].append({'path': rel,
                                          'reason': 'thieu article_id'})
                continue
            seen_ids.setdefault(aid, []).append(rel)
        for aid, paths in sorted(seen_ids.items(),
                                 key=lambda kv: order.get(kv[0], 10 ** 9)):
            if aid not in by_id:
                out['quarantine'].append({'id': aid, 'path': paths[0],
                                          'reason': 'id khong co trong matrix'})
                continue
            if aid in out['published_edits']:
                continue            # đã publish: bỏ qua sạch
            if len(paths) > 1 or aid in taken:
                out['quarantine'].append({
                    'id': aid, 'path': paths[0],
                    'reason': 'nhieu draft cung mot ID'})
                continue
            st = by_id[aid]['status']
            if st == 'PUBLISHED':
                out['published_edits'] = sorted(
                    set(out['published_edits']) | {aid},
                    key=lambda i: order[i])
                continue
            if st not in ELIGIBLE:
                out['quarantine'].append({'id': aid, 'path': paths[0],
                                          'reason': 'trang thai %s duoc '
                                          'bao ve' % st})
                continue
            _, writer, session = parse_draft(os.path.join(ROOT, paths[0]))
            changed_content, edited = True, False
            if st != 'PLANNED':
                changed_content, edited = content_state(aid, paths[0])
                if st == 'REPAIR' and not changed_content:
                    out['waiting_repair'].append(aid)
                    continue
            prob, warn = ownership_problem(aid, st, writer, session,
                                           registry, changed_content,
                                           edited)
            if prob:
                out['quarantine'].append({'id': aid, 'path': paths[0],
                                          'reason': prob})
                continue
            prob = engine_problem(by_id[aid], paths[0])
            if prob:
                out['quarantine'].append({'id': aid, 'path': paths[0],
                                          'reason': prob})
                continue
            if warn:
                out['warnings'].append(warn)
            queue.append(aid)
            out['backlog'].append(aid)
            declared[aid] = writer

    if not queue:
        # no-op sạch: không draft hợp lệ — KHÔNG đụng matrix
        return out

    # deterministic matrix order (KHÔNG theo tên file, KHÔNG theo thứ tự push)
    queue = sorted(set(queue), key=lambda i: order[i])

    if not control_enabled and any(by_id[i]['status'] == 'PLANNED'
                                   for i in queue):
        # production-control paused: KHÔNG claim bài mới. Bỏ ID PLANNED khỏi
        # queue nhưng vẫn xử lý hàng in-flight (repair/PASS) — một draft
        # PLANNED trong backlog không được làm đói các hàng đã claim. Làm
        # TRƯỚC khi cắt trần, kẻo PLANNED chiếm hết suất rồi bị bỏ đi.
        skipped = [i for i in queue if by_id[i]['status'] == 'PLANNED']
        queue = [i for i in queue if by_id[i]['status'] != 'PLANNED']
        out['warnings'].append(
            'production-control paused: bo %d ID PLANNED (khong claim bai '
            'moi): %s' % (len(skipped), ','.join(skipped[:10])))
        if not queue:
            out['backlog'] = []
            out['mode'] = 'paused'
            return out

    if len(queue) > MAX_QUEUE_PER_RUN:
        # cắt trần: hàng IN-FLIGHT trước (đúng thứ tự pair của
        # factory-queue.py), rồi PLANNED; trong mỗi nhóm theo matrix order
        keep = set(sorted(queue, key=lambda i: (by_id[i]['status'] == 'PLANNED',
                                                order[i]))[:MAX_QUEUE_PER_RUN])
        out['warnings'].append(
            'queue %d > %d: chi xu ly %d (hang in-flight truoc, roi matrix '
            'order), phan du cho run ke' % (len(queue), MAX_QUEUE_PER_RUN,
                                            MAX_QUEUE_PER_RUN))
        queue = [i for i in queue if i in keep]
    out['backlog'] = [i for i in out['backlog'] if i in set(queue)]

    needs_claim = any(by_id[i]['status'] == 'PLANNED' for i in queue)
    mode = 'new' if needs_claim else 'repair'
    out['mode'] = mode
    out['queue'] = queue
    # claim CHỈ hàng PLANNED; repair rows skip claim (KHÔNG claim lại
    # từ đầu) — consume của workflow chia pair và claim đúng subset này
    out['claim_ids'] = [i for i in queue if by_id[i]['status'] == 'PLANNED']
    out['qa_ids'] = list(queue)
    out['pairs'] = (len(queue) + 1) // 2

    if registry is not None and out['claim_ids']:
        out['writers'] = {a: declared[a] for a in out['claim_ids']}

    out['proceed'] = True
    return out


def push_paths_of(aid, entries):
    for a, _, _, f in entries:
        if a == aid:
            return f
    return None


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--added', default=None,
                    help='file chứa path ADDED, mỗi dòng một path')
    ap.add_argument('--modified', default=None,
                    help='file chứa path MODIFIED, mỗi dòng một path')
    ap.add_argument('--changed', default=None,
                    help='file chứa MỌI path đổi trong push (cảnh báo)')
    ap.add_argument('--backlog', action='store_true',
                    help='drain: gom luôn draft đang xếp hàng trong _drafts/')
    args = ap.parse_args()
    os.chdir(ROOT)
    out = select(read_paths(args.added), read_paths(args.modified),
                 backlog=args.backlog, changed=read_paths(args.changed))
    print(json.dumps(out, ensure_ascii=False))
    if out.get('published_edits'):
        print('selection: published_edits (race push trùng / re-run — ID đã '
              'được publish bởi run khác, bỏ qua sạch, KHÔNG sửa bài '
              'đã xuất bản): %s'
              % ','.join(out['published_edits']))
    for q in out.get('quarantine') or []:
        print('selection: CACH LY (khong chan queue): %s'
              % json.dumps(q, ensure_ascii=False))
    for w in out.get('warnings') or []:
        print('selection: CANH BAO: %s' % w)
        print('::warning::%s' % w)
    refused = bool(out['refuse'])
    if refused:
        print('REFUSED: %s' % out['refuse'], file=sys.stderr)
        if not out['queue']:
            return 3
        # push bị từ chối nhưng backlog có draft hợp lệ: tiếp tục xử lý chúng
        # (không kẹt writer khác); workflow đọc `refused=true` và làm ĐỎ run ở
        # step cuối SAU khi đã commit phần hợp lệ.
        print('selection: push REFUSED nhung backlog co %d ID hop le — van '
              'drain, run se DO o step cuoi' % len(out['queue']))
    if out['mode'] == 'skip':
        if out.get('published_edits'):
            print('selection: push trùng đã superseded — toàn bộ ID '
                  'PUBLISHED, no-op sạch (run GREEN)')
        else:
            print('selection: khong co draft trong push — no-op')
    elif out['mode'] == 'paused':
        print('selection: production-control paused — khong claim bai '
              'moi; exit sach')
    else:
        print('selection: mode=%s queue=%s pairs=%d%s'
              % (out['mode'], out['queue'], out['pairs'],
                 (' backlog=%s' % out['backlog']) if out['backlog'] else ''))
    # workflow (Actions) đọc step outputs từ $GITHUB_OUTPUT; local/test
    # KHÔNG có biến này — stdout JSON ở trên là kết quả đầy đủ
    gout = os.environ.get('GITHUB_OUTPUT')
    if gout:
        with open(gout, 'a', encoding='utf-8') as f:
            f.write('queue=%s\n' % ','.join(out['queue']))
            f.write('mode=%s\n' % out['mode'])
            f.write('pairs=%s\n' % out['pairs'])
            f.write('refused=%s\n' % ('true' if refused else 'false'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
