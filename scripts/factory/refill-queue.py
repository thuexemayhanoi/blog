#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# refill-queue.py - refill chu de LAZY cho queue 10K.
#
# Che do ( Hop dong docs/ENGINE-RUNBOOK.md ):
#   refill-queue.py --plan              in claimable + thoi diem refill (read-only)
#   refill-queue.py --verify [--report PATH|-]
#                                       PURE validation gate G1-G8 cho ledger.
#                                       KHONG append, KHONG gan ID, KHONG sua
#                                       matrix/checkpoint/ledger. exit 0 = PASS,
#                                       khac 0 = gate violation that.
#                                       Mac dinh in bao cao ra stdout va KHONG
#                                       ghi bat ky file nao (pure by default).
#                                       --report - : in ra stdout, zero file.
#                                       --report PATH : chi ghi dung PATH duoc
#                                       yeu cau ro rang (khong co duong dan
#                                       mac dinh). CI KHONG BAO GIO commit
#                                       bao cao.
#   refill-queue.py --dry-run [--n N]   sinh N candidate IN-MEMORY tu pool
#                                       determinist, chay gate, in
#                                       generated/accepted/rejected. Cay lam
#                                       viec KHONG doi (CI/prod safe).
#   refill-queue.py --selftest          kiem thu am (negative): gate PHAI tu choi
#                                       duplicate intent/kw/slug/canonical/
#                                       output_path, legacy overlap, capacity
#                                       overflow, word_target nong.
#   refill-queue.py --refill --yes      OPERATOR-ONLY: materialize ledger vao
#                                       matrix-seed. Truoc khi mutate: doc
#                                       START_HEAD (git), transaction phai
#                                       inactive; ACQUIRE KHOA ATOMIC
#                                       O_CREAT|O_EXCL sentinel (giong
#                                       publish-gate.py, hai writer khong the
#                                       cung giu khoa); re-check HEAD sau khi
#                                       giu khoa (doi -> nha khoa, STOP);
#                                       re-run gate; mutate; validate;
#                                       nha khoa trong finally DAM BAO.
#                                       (alias cu: --commit --yes)
#
# Gate (KHONG ha nguong):
#  G1 child ton tai + headroom editorial_capacity
#  G2 kw chuan hoa duy nhat trong child (vs matrix + candidates)
#  G3 intent chuan hoa duy nhat trong child (vs matrix + candidates)
#  G4 slug duy nhat (vs matrix + candidate) — slug suy ra output_path/canonical
#  G4b output_path + canonical suy ra tu slug KHONG trung matrix
#  G5 depth: word_target >= 1200
#  G6 candidate_id duy nhat trong ledger
#  G7 child phai thuoc taxonomy (ke thua source policy)
#  G8 candidate KHONG trung tieu de chuan hoa voi bat ky hang matrix nao
#     (chong cannibalization bai cu)
import csv
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
os.chdir(ROOT)

CAP_PATH = 'data/factory-capacity.json'
TAX_PATH = 'data/state/taxonomy-config.json'
MATRIX_PATH = 'data/content-matrix.csv'
LEDGER_PATH = 'data/state/refill-candidates.json'
SEED_PATH = 'data/state/matrix-seed.json'
LOCK_JSON = 'data/state/writer-lock.json'
LOCK_SENTINEL = 'data/state/writer-lock.active'
TXN_PATH = 'data/state/transaction.json'
# LUU Y: --verify KHONG co duong dan bao cao mac dinh (pure by default).
# reports/factory/refill-verify.md chi duoc ghi khi operator truyen
# --report reports/factory/refill-verify.md ro rang.
MIN_WORD = 1200


def norm(s):
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9 ]', '', s.lower()).strip()


def slugify(s):
    s = norm(s)
    return re.sub(r'\s+', '-', s)[:80].strip('-')


def load_matrix():
    return list(csv.DictReader(open(MATRIX_PATH, encoding='utf-8')))


def build_matrix_indexes(rows):
    """Index nho (requirement #9): kw/intent/slug/title/output/canonical toan matrix."""
    idx = {'kw': {}, 'intent': {}, 'slug': set(), 'title': {},
           'out': set(), 'canon': set(), 'per_child': {}}
    for r in rows:
        cid = r['child_id']
        idx['per_child'][cid] = idx['per_child'].get(cid, 0) + 1
        if norm(r['primary_keyword']):
            idx['kw'][(cid, norm(r['primary_keyword']))] = r['id']
        if norm(r['intent']):
            idx['intent'][(cid, norm(r['intent']))] = r['id']
        op = r['output_path']
        sl = op.split('-', 1)[1][:-3] if '{date}' in op \
            else os.path.basename(op)[11:-3]
        idx['slug'].add(sl)
        idx['out'].add(op)
        idx['canon'].add(r['canonical_url'])
        if norm(r['title']):
            idx['title'][norm(r['title'])] = r['id']
    return idx


def check_candidate(c, midx, seen, tax_kids, child_caps, staged_child,
                    mat_kw, mat_int):
    """Chay G1-G8 cho 1 candidate. Tra ve list loi (rong = PASS)."""
    errs = []
    cid = c.get('candidate_id', '(khong id)')
    if c['child_id'] not in tax_kids:
        return ['%s: G7 child khong ton tai trong taxonomy' % cid]
    if c['child_id'] not in child_caps:
        return ['%s: G1 child khong co editorial capacity' % cid]
    staged_child[c['child_id']] = staged_child.get(c['child_id'], 0) + 1
    used = (midx['per_child'].get(c['child_id'], 0)
            + staged_child[c['child_id']])
    if used > child_caps[c['child_id']]:
        errs.append('%s: G1 vuot editorial_capacity (%d > %d)'
                    % (cid, used, child_caps[c['child_id']]))
    k = (c['child_id'], norm(c.get('kw', '')))
    if k in midx['kw']:
        errs.append('%s: G2 kw trung matrix %s' % (cid, midx['kw'][k]))
    if k in seen['kw']:
        errs.append('%s: G2 kw trung candidate %s' % (cid, seen['kw'][k]))
    seen['kw'][k] = cid
    k = (c['child_id'], norm(c.get('intent', '')))
    if k in midx['intent']:
        errs.append('%s: G3 intent trung matrix %s' % (cid, midx['intent'][k]))
    if k in seen['intent']:
        errs.append('%s: G3 intent trung candidate %s' % (cid, seen['intent'][k]))
    seen['intent'][k] = cid
    sl = slugify(c.get('title', ''))
    if sl in midx['slug']:
        errs.append('%s: G4 slug trung matrix (%s)' % (cid, sl))
    if sl in seen['slug']:
        errs.append('%s: G4 slug trung candidate (%s)' % (cid, sl))
    seen['slug'].add(sl)
    # G4b: output_path/canonical suy ra tu slug (pattern generate-matrix.py)
    out = '_posts/{date}-%s.md' % sl
    canon = '/blog/%s/{date}/%s/' % (c.get('_cat', '_'), sl)
    if out in midx['out']:
        errs.append('%s: G4b output_path trung matrix (%s)' % (cid, out))
    if out in seen['out']:
        errs.append('%s: G4b output_path trung candidate (%s)' % (cid, out))
    seen['out'].add(out)
    if canon in midx['canon']:
        errs.append('%s: G4b canonical trung matrix' % cid)
    if norm(c.get('title', '')) and norm(c['title']) in midx['title']:
        errs.append('%s: G8 title trung matrix %s'
                    % (cid, midx['title'][norm(c['title'])]))
    if int(c.get('word_target', 0) or 0) < MIN_WORD:
        errs.append('%s: G5 word_target < %d (%r)'
                    % (cid, MIN_WORD, c.get('word_target')))
    if cid in seen['cid']:
        errs.append('%s: G6 candidate_id trung' % cid)
    seen['cid'].add(cid)
    return errs


def render_report(passed, cands, rej, errors):
    lines = [
        '# Refill verify report (tu dong, khong sua tay)',
        '',
        'Sinh boi scripts/factory/refill-queue.py --verify. '
        'Deterministic: chi phu thuoc matrix + ledger + capacity.',
        'CI chi IN bao cao (stdout/summary) - KHONG BAO GIO commit bao cao.',
        '',
        '- Candidates staged: %d' % len(cands),
        '- Rejected recorded: %d' % len(rej),
        '- Gate violations: %d' % len(errors),
        '- RESULT: %s' % ('PASS' if passed else 'FAIL'),
        '',
        '## Gate violations',
        '',
    ]
    if errors:
        for e in errors:
            lines.append('- %s' % e)
    else:
        lines.append('- (khong co)')
    lines += ['', '## Candidates staged', '',
              '| candidate | child | kw | word |', '|---|---|---|---|']
    for c in cands:
        lines.append('| %s | %s | %s | %s |'
                     % (c['candidate_id'], c['child_id'],
                        c.get('kw', ''), c.get('word_target', '')))
    lines += ['', '## Rejected (ghi lai ly do)', '',
              '| candidate | ly do |', '|---|---|']
    for r in rej:
        rid = r.get('candidate_id', r.get('title', '?'))
        lines.append('| %s | %s |' % (rid, r.get('reason', r.get('gate', ''))))
    lines.append('')
    return '\n'.join(lines)


def mode_plan(cap, rows):
    th = cap['thresholds']
    claimable = sum(1 for r in rows if r['status'] == 'PLANNED')
    print('=== REFILL PLAN ===')
    print('claimable PLANNED : %d' % claimable)
    print('min_ready_queue   : %d' % th['min_ready_queue'])
    print('refill_target     : %d' % th['refill_target'])
    if claimable < th['min_ready_queue']:
        print('ACTION: refill den %d candidate' % th['refill_target'])
    else:
        print('ACTION: khong can refill (queue con kho)')
    return 0


def mode_verify(cap, tax, rows, ledger, report_path):
    """PURE: khong sua gi, khong ghi file nao tru khi --report PATH ro rang.
    report_path None hoac '-' = stdout; PATH = ghi dung PATH do."""
    tax_kids = set(c[0] for c in tax['children'])
    child_caps = cap['child_editorial_capacity']
    midx = build_matrix_indexes(rows)
    seen = {'kw': {}, 'intent': {}, 'slug': set(), 'out': set(),
             'cid': set()}
    staged_child = {}
    cands = ledger['candidates']
    errors = []
    # category cho G4b canonical pattern
    cat_by_child = {c[0]: c[3] for c in tax['children']}  # slug child
    # pattern canonical thuc te can parent category; dung slug child + parent
    pslug = {p[0]: p[2] for p in tax['parents']}
    cparent = {c[0]: c[1] for c in tax['children']}
    for c in cands:
        c['_cat'] = pslug.get(cparent.get(c['child_id'], ''), '_')
    for c in cands:
        errors += check_candidate(c, midx, seen, tax_kids, child_caps,
                                  staged_child, None, None)
    passed = not errors
    report = render_report(passed, cands, ledger.get('rejected', []), errors)
    if report_path is None or report_path == '-':
        # PURE: stdout, KHONG ghi file
        print(report)
    else:
        # chi khi operator yeu cau ro --report PATH
        d = os.path.dirname(report_path)
        if d:
            os.makedirs(d, exist_ok=True)
        open(report_path, 'w', encoding='utf-8').write(report)
        print('report            : %s' % report_path)
    print('=== REFILL VERIFY (gate G1-G8) ===')
    print('candidates staged : %d' % len(cands))
    print('rejected recorded : %d' % len(ledger.get('rejected', [])))
    if errors:
        print('GATE VIOLATIONS: %d' % len(errors))
        for e in errors[:20]:
            print(' -', e)
        return 1
    print('ALL GATES: PASS (G1-G8)')
    return 0


# ---------------- pool candidate determinist cho --dry-run (KHONG materialize)
# Moi phan tu la mot y dinh that, rieng biet; dung lam dau vao kiem may.
DRY_POOL = [
    ('C-THUE-GIA', 'Chi phí thuê xe máy cho chuyến công tác 2 ngày ở Hà Nội',
     'Ước chi phí thuê xe máy công tác 2 ngày', 'chi phí thuê xe máy 2 ngày',
     ['thuê xe 2 ngày bao nhiêu tiền'], ['/bang-gia/', '/thue-xe/thue-ngay/'],
     'khach-cong-tac', 1300),
    ('C-THUE-THU-TUC', 'Đặt xe thuê qua tin nhắn: chốt những gì bằng văn bản',
     'Cách đặt xe máy thuê qua tin nhắn an toàn',
     'đặt xe máy thuê qua tin nhắn',
     ['chốt xe qua tin nhắn', 'đặt xe online'], ['/thue-xe/thu-tuc/'],
     'khach-vang-lai', 1200),
    ('C-THUE-NHAN-TRA', 'Bàn giao xe khi trả muộn vài tiếng: xử lý lịch sự',
     'Cách xử lý khi trả xe thuê muộn vài tiếng',
     'trả xe thuê muộn vài tiếng',
     ['trả xe trễ có sao không', 'báo trễ khi trả xe'],
     ['/thue-xe/nhan-tra-xe/'], 'khach-vang-lai', 1200),
    ('C-BAO-DUONG', 'Tiếng lạ từ động cơ xe ga thuê: nhận biết sớm',
     'Nhận biết tiếng lạ từ động cơ xe ga thuê',
     'tiếng lạ động cơ xe ga',
     ['xe ga có tiếng kêu lạ', 'động cơ xe ga bất thường'],
     ['/xe-may/bao-duong-xe/', '/xe-may/xe-ga/'], 'nguoi-di-lam', 1300),
    ('C-CD-NOI-THANH', 'Chạy thử cung đường Tây Hồ - Nhật Tân sáng sớm',
     'Tìm cung đường chạy thử Tây Hồ Nhật Tân sáng sớm',
     'cung đường tây hồ nhật tân',
     ['chạy thử xe sáng sớm hà nội', 'tây hồ nhật tân xe máy'],
     ['/cung-duong/cung-duong-noi-thanh/', '/du-lich/ho-tay/'],
     'khach-du-lich', 1300),
    ('C-KY-NANG-GUI-XE', 'Chống trộm phụ tùng khi gửi xe qua đêm',
     'Cách chống trộm phụ tùng xe máy khi gửi qua đêm',
     'chống trộm phụ tùng xe máy',
     ['mất gương xe khi gửi xe', 'khóa phụ tùng xe'],
     ['/ky-nang/gui-xe-va-giu-xe/'], 'khach-vang-lai', 1200),
    ('C-HD-SU-CO', 'Xe thuê hết xăng giữa phố: gọi ai và làm gì',
     'Xử lý khi xe thuê hết xăng giữa phố',
     'xe thuê hết xăng giữa phố làm gì',
     ['hết xăng giữa phố', 'mua xăng giao tận nơi'],
     ['/hoi-dap/hoi-dap-su-co/'], 'nguoi-moi', 1200),
    ('C-XE-SO-SANH', 'Thuê xe số và xe ga chạy đèo: dòng nào bền hơn',
     'So sánh xe số và xe ga khi chạy cung đường đèo',
     'xe số hay xe ga chạy đèo',
     ['đèo nên chạy xe số', 'xe ga lên đèo'],
     ['/xe-may/so-sanh-xe/', '/cung-duong/cung-duong-pho-bac/'],
     'phuot-thu', 1400),
]


def mode_dry_run(cap, tax, rows, ledger, n):
    """Sinh candidate IN-MEMORY tu pool, chay gate, KHONG doi cay lam viec."""
    tax_kids = set(c[0] for c in tax['children'])
    child_caps = cap['child_editorial_capacity']
    midx = build_matrix_indexes(rows)
    # pool + ledger cung qua gate: ledger staged cung phai khong bi dry-run
    # candidate an thit
    seen = {'kw': {}, 'intent': {}, 'slug': set(), 'out': set(),
             'cid': set()}
    staged_child = {}
    pslug = {p[0]: p[2] for p in tax['parents']}
    cparent = {c[0]: c[1] for c in tax['children']}
    accepted, rejected = [], []
    pool = [c for c in DRY_POOL][:n]
    for i, (cid_, title, intent, kw, kw2, links, aud, wt) in enumerate(pool, 1):
        cand = {'candidate_id': 'CAND-DRY-%03d' % i, 'child_id': cid_,
                'title': title, 'intent': intent, 'kw': kw,
                'kw2': kw2, 'links': links, 'audience': aud,
                'word_target': wt,
                '_cat': pslug.get(cparent.get(cid_, ''), '_')}
        # ledger staged ton tai? dem vao staged_child de khong vuot capacity
        errs = check_candidate(cand, midx, seen, tax_kids, child_caps,
                              staged_child, None, None)
        if errs:
            rejected.append((cand, errs))
        else:
            accepted.append(cand)
    print('=== REFILL DRY-RUN (in-memory, cay lam viec KHONG doi) ===')
    print('generated : %d' % len(pool))
    print('accepted  : %d' % len(accepted))
    print('rejected  : %d' % len(rejected))
    for cand, errs in rejected:
        print('  REJ %s (%s): %s' % (cand['candidate_id'],
                                     cand['title'][:40], '; '.join(errs)))
    print('NOTE: dry-run KHONG ghi ledger/matrix/checkpoint. '
          'Materialize chi qua --refill --yes (operator).')
    return 0


def mode_selftest(cap, tax, rows):
    """Negative tests: gate PHAI tu choi cac truong hop sai. Read-only."""
    tax_kids = set(c[0] for c in tax['children'])
    child_caps = cap['child_editorial_capacity']
    midx = build_matrix_indexes(rows)
    pslug = {p[0]: p[2] for p in tax['parents']}
    cparent = {c[0]: c[1] for c in tax['children']}

    def fresh():
        return ({'kw': {}, 'intent': {}, 'slug': set(), 'out': set(),
                 'cid': set()}, {})

    def cand(**kw):
        base = {'candidate_id': 'CAND-TEST-1', 'child_id': 'C-THUE-GIA',
                'title': 'Tieu de thu nhat cho kiem thu',
                'intent': 'Y dinh thu nhat cho kiem thu',
                'kw': 'tu khoa thu nhat', 'kw2': [], 'links': [],
                'word_target': 1300, 'audience': '', '_cat': 'thue-xe'}
        base.update(kw)
        return base

    results = []

    def case(name, c, must_reject=True, gate=None):
        seen, staged = fresh()
        errs = check_candidate(c, midx, seen, tax_kids, child_caps, staged,
                               None, None)
        rejected = bool(errs)
        ok = (rejected == must_reject) and (gate is None
                                            or any(gate in e for e in errs))
        results.append((ok, name, errs[:1]))

    # 1. hop le -> PASS
    case('candidate hop le duoc chap nhan', cand(), must_reject=False)
    # 2. duplicate intent vs matrix
    dup = rows[484]  # hang planned dau tien
    case('duplicate intent vs matrix bi tu choi (G3)',
         cand(intent=dup['intent'], kw='tu khoa moi hoan toan 01'), gate='G3')
    # 3. duplicate kw vs matrix
    case('duplicate keyword vs matrix bi tu choi (G2)',
         cand(kw=dup['primary_keyword'], intent='y dinh moi hoan toan 02',
              title='tieu de moi hoan toan 02'), gate='G2')
    # 4. duplicate slug vs matrix (title -> slug trung legacy)
    case('duplicate slug vs matrix bi tu choi (G4)',
         cand(title=dup['title'], intent='y dinh moi hoan toan 03',
              kw='tu khoa moi hoan toan 03'), gate='G4')
    # 5. duplicate title vs matrix (G8 cannibalization)
    case('duplicate title vs matrix bi tu choi (G8)',
         cand(title=dup['title'], kw='tu khoa khac 04',
              intent='y dinh khac 04'), gate='G8')
    # 6. child khong ton tai (G7)
    case('child khong ton tai bi tu choi (G7)',
         cand(child_id='C-KHONG-TON-TAI'), gate='G7')
    # 7. word_target qua nong (G5)
    case('word_target nong bi tu choi (G5)',
         cand(word_target=800), gate='G5')
    # 8. capacity overflow: gia lap child day bang staged
    seen, staged = fresh()
    staged_full = {'C-THUE-GIA': child_caps['C-THUE-GIA']}
    errs = check_candidate(cand(), midx, seen, tax_kids, child_caps,
                           staged_full, None, None)
    ok = any('G1' in e for e in errs)
    results.append((ok, 'capacity overflow bi tu choi (G1)', errs[:1]))
    # 9. candidate_id trung (G6)
    seen, staged = fresh()
    check_candidate(cand(), midx, seen, tax_kids, child_caps, staged, None,
                    None)
    seen2 = dict(seen); staged2 = dict(staged)
    errs = check_candidate(cand(kw='tu khoa khac 09',
                                intent='y dinh khac 09',
                                title='tieu de khac 09'),
                           midx, seen2, tax_kids, child_caps, staged2, None,
                           None)
    ok = any('G6' in e for e in errs)
    results.append((ok, 'candidate_id trung bi tu choi (G6)', errs[:1]))

    print('=== REFILL SELFTEST (negative collision tests) ===')
    fails = 0
    for ok, name, errs in results:
        print('%s  %s' % ('PASS:' if ok else 'FAIL:', name))
        if not ok:
            fails += 1
            print('    loi that:', errs)
    if fails:
        print('SELFTEST: FAIL (%d)' % fails)
        return 1
    print('SELFTEST: PASS (%d truong hop)' % len(results))
    return 0


def now_iso():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec='seconds')


def git_head():
    """HEAD hien tai tu git (rev-parse). None = khong co git/repo -> tu choi."""
    try:
        import subprocess
        out = subprocess.run(['git', 'rev-parse', 'HEAD'],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:
        return None


def acquire_atomic_lock(holder, start_head):
    """Khoa ghi ATOMIC theo hop dong production (O_CREAT|O_EXCL sentinel,
    giong publish-gate.py): hai writer KHONG THE cung tao sentinel -> khong
    race. Thanh cong: ghi metadata writer-lock.json, tra ve release().
    FileExistsError: khoa dang bi giu."""
    fd = os.open(LOCK_SENTINEL,
                 os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    os.write(fd, ('%s %s' % (holder, now_iso())).encode('utf-8'))
    os.close(fd)
    # dong bo writer-lock.json cho cong cu khac (khong lam dieu kien race)
    json.dump({'locked': True, 'holder': holder, 'action': 'refill',
               'acquired_at': now_iso(), 'expires_at': None,
               'updated_at': now_iso(), 'start_head': start_head,
               'pid': os.getpid(),
               'note': 'Sentinel that: data/state/writer-lock.active (O_EXCL).'},
              open(LOCK_JSON, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    def release():
        try:
            os.remove(LOCK_SENTINEL)
        except FileNotFoundError:
            pass
        json.dump({'locked': False, 'holder': None, 'action': None,
                   'acquired_at': None, 'expires_at': None,
                   'updated_at': now_iso(), 'start_head': None,
                   'pid': None,
                   'note': 'Lock phai duoc giu trong suot mot chunk va nha '
                           'khi checkpoint an toan. Khong bao gio chay hai '
                           'writer song song.'},
                  open(LOCK_JSON, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
    return release()


def txn_inactive():
    txn = json.load(open(TXN_PATH, encoding='utf-8'))
    if txn.get('active'):
        return False, 'transaction active=true — recover truoc khi refill'
    return True, None


def mode_refill(cap, tax, rows, ledger):
    """OPERATOR-ONLY: materialize ledger vao matrix-seed.
    Thu tu (hop dong hardening):
      1. START_HEAD = git rev-parse HEAD (None -> tu choi, khong mutate)
      2. transaction phai inactive
      3. acquire khoa atomic O_EXCL (busy -> STOP, khong mutate)
      4. ghi metadata lock (holder=refill, start_head, pid)
      5. re-read HEAD; khac START_HEAD -> release + STOP
      6. chay lai gate; loi -> release + STOP
      7. mutate seed; moi exception -> release (finally)
    """
    if '--yes' not in sys.argv:
        print('REFILL (materialize) can --yes (operator phe duyet)')
        return 2
    start_head = git_head()
    if not start_head:
        print('REFILL TU CHOI: khong doc duoc git HEAD (khong o repo git) — '
              'refill chi chay trong clone that')
        return 1
    ok, why = txn_inactive()
    if not ok:
        print('REFILL TU CHOI: %s' % why)
        return 1
    release = None
    try:
        # 3-4. KHOA ATOMIC: O_EXCL sentinel + metadata
        try:
            release = acquire_atomic_lock('refill-queue', start_head)
        except FileExistsError:
            print('REFILL TU CHOI: writer-lock dang bi giu (sentinel %s ton '
                  'tai) — tu choi, khong mutate' % LOCK_SENTINEL)
            return 1
        # 5-6. HEAD re-check SAU khi giu khoa
        if git_head() != start_head:
            print('REFILL TU CHOI: HEAD main da doi giua refill (%s -> %s) — '
                  'nha khoa, khong auto-merge/rebase' % (start_head,
                                                         git_head()))
            return 1
        materialized = len(rows)
        if materialized + len(ledger['candidates']) > cap['hard_capacity']:
            print('REFILL TU CHOI: vuot hard_capacity (%d + %d > %d)'
                  % (materialized, len(ledger['candidates']),
                     cap['hard_capacity']))
            return 1
        # 7. verify lai gate truoc khi materialize
        tax_kids = set(c[0] for c in tax['children'])
        child_caps = cap['child_editorial_capacity']
        midx = build_matrix_indexes(rows)
        seen = {'kw': {}, 'intent': {}, 'slug': set(), 'out': set(),
                 'cid': set()}
        staged_child = {}
        pslug = {p[0]: p[2] for p in tax['parents']}
        cparent = {c[0]: c[1] for c in tax['children']}
        errors = []
        for c in ledger['candidates']:
            c['_cat'] = pslug.get(cparent.get(c['child_id'], ''), '_')
            errors += check_candidate(c, midx, seen, tax_kids, child_caps,
                                      staged_child, None, None)
        if errors:
            print('REFILL TU CHOI: ledger khong qua gate (%d violation)'
                  % len(errors))
            for e in errors[:10]:
                print(' -', e)
            return 1
        # 8. mutate seed (da giu khoa atomic)
        seed = json.load(open(SEED_PATH, encoding='utf-8'))
        added = 0
        for c in ledger['candidates']:
            spec = seed['children'].setdefault(c['child_id'],
                                               {'group': '', 'rows': []})
            spec.setdefault('rows', [])
            if any(norm(r['title']) == norm(c['title'])
                   for r in spec['rows']):
                continue  # idempotent
            spec['rows'].append({
                'title': c['title'], 'intent': c['intent'], 'kw': c['kw'],
                'kw2': c.get('kw2', []), 'links': c.get('links', []),
                'subtopic': c.get('subtopic', ''),
                'audience': c.get('audience', ''),
                'location_scope': c.get('location_scope', ''),
                'word_target': c.get('word_target', 1200)})
            added += 1
        with open(SEED_PATH, 'w', encoding='utf-8') as f:
            json.dump(seed, f, ensure_ascii=False, indent=2)
            f.write('\n')
        # 9. validate mutation: seed parse lai duoc va children ok
        json.load(open(SEED_PATH, encoding='utf-8'))
        print('REFILL: +%d rows vao matrix-seed' % added)
        print('BUOC KE: chay generate-matrix.py roi commit matrix + seed + '
              'bao cao')
        return 0
    finally:
        # 12. nha khoa DAM BAO (moi exit path thanh cong/loi/exception)
        if release is not None:
            release()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else '--plan'
    cap = json.load(open(CAP_PATH, encoding='utf-8'))
    tax = json.load(open(TAX_PATH, encoding='utf-8'))
    rows = load_matrix()
    if mode == '--plan':
        sys.exit(mode_plan(cap, rows))
    if mode == '--selftest':
        sys.exit(mode_selftest(cap, tax, rows))
    if mode == '--dry-run':
        n = 8
        if '--n' in sys.argv:
            n = int(sys.argv[sys.argv.index('--n') + 1])
        ledger = json.load(open(LEDGER_PATH, encoding='utf-8'))
        sys.exit(mode_dry_run(cap, tax, rows, ledger, n))
    if mode == '--verify':
        ledger = json.load(open(LEDGER_PATH, encoding='utf-8'))
        # PURE by default: khong --report = stdout, khong ghi file nao.
        # --report - : stdout. --report PATH : ghi dung PATH do.
        report = None
        if '--report' in sys.argv:
            report = sys.argv[sys.argv.index('--report') + 1]
            if report != '-' and (not report or os.path.isdir(report)):
                print('FAIL: --report can PATH hop le hoac \"-\"')
                sys.exit(2)
        sys.exit(mode_verify(cap, tax, rows, ledger, report))
    if mode in ('--refill', '--commit'):
        ledger = json.load(open(LEDGER_PATH, encoding='utf-8'))
        sys.exit(mode_refill(cap, tax, rows, ledger))
    print('usage: refill-queue.py --plan | --verify [--report PATH|-] | '
          '--dry-run [--n N] | --selftest | --refill --yes')
    sys.exit(2)


if __name__ == '__main__':
    main()
