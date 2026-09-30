#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PUBLISH GATE cứng v3 — kiểm tra trạng thái + bằng chứng GẮNG VỚI NỘI DUNG.

Lệnh:

  python3 scripts/factory/publish-gate.py --draft _drafts/2026-09-27-slug.md --id BLG-00484

Chuỗi promote an toàn (theo đúng thứ tự, không rút ngắn):
  1. atomically ACQUIRE writer lock (O_EXCL — hai writer không thể cùng thấy
     "lock tự do").
  2. kiểm tra không có transaction conflicting đang active.
  3. kiểm tra hàng matrix = PASS.
  4. kiểm tra bằng chứng data/qa/<id>.json: quality>=75, seo>=70,
     business_fact=PASS, legal=PASS|NOT_REQUIRED, critical_failure=false.
  5. GẮNG VỚI NỘI DUNG: sha256 draft HIỆN TẠI phải == qa.content_sha256
     (khớp -> QA chấm đúng nội dung này; lệch -> STALE_QA_EVIDENCE, từ chối).
  6. GẮNG VỚI HÀNG MATRIX: vân tay (title/intent/keyword/URL/path) của hàng
     hiện tại phải == qa.matrix_row_sha256 (lệch sau QA -> từ chối).
  7. mở transaction, promote draft -> _posts/, matrix -> PUBLISHED (chốt ngày
     thật vào URL), cập nhật checkpoint (updated_at = giờ chạy thật).
  8. APPEND vào transaction history (không reset), đóng transaction, RELEASE lock.

FAIL bất kỳ: trả draft về _drafts/ nếu đã dời, đóng transaction, RELEASE lock, exit 1.
Rollback: revert commit promote; chạy lại generate-reports.py.
"""
import argparse, csv, datetime, hashlib, json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
MATRIX = 'data/content-matrix.csv'
QA_DIR = 'data/qa'
LOCK = 'data/state/writer-lock.json'
LOCK_FILE = 'data/state/writer-lock.active'  # atomic O_EXCL sentinel
TXN = 'data/state/transaction.json'
CP = 'data/state/checkpoint.json'
HISTORY_MAX = 50

QUALITY_MIN = 75
SEO_MIN = 70


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')


def sha256_file(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def matrix_row_sha256(r):
    """Vân tay hàng matrix — trùng định nghĩa khi QA chấm (docs/CONTENT-FACTORY.md)."""
    basis = {k: r[k] for k in ('title', 'intent', 'primary_keyword',
                               'expected_url', 'output_path', 'canonical_url')}
    return hashlib.sha256(json.dumps(basis, ensure_ascii=False, sort_keys=True)
                          .encode('utf-8')).hexdigest()


def fail(msgs, release=None):
    print('=== PUBLISH GATE: TỪ CHỐI ===')
    for m in msgs:
        print('FAIL:', m)
    if release is not None:
        release()
    sys.exit(1)


def _write_json_atomic(path, obj):
    """Ghi JSON an toan: ghi file .tmp, flush, fsync, os.replace (atomic
    rename). Khong bao gio de writer-lock.json o trang thai nua chua."""
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _unlocked_meta(note):
    return {'locked': False, 'holder': None, 'acquired_at': None,
            'expires_at': None, 'updated_at': now_iso(),
            'note': note}


def acquire_lock(holder):
    """O_EXCL sentinel: hai tiến trình không thể cùng tạo tệp -> không race.
    Trả về hàm release(); nếu không acquire được -> fail an toàn.

    OWNERSHIP TOKEN (đồng bộ với refill-queue.py): mỗi lần acquire sinh
    token UUID riêng; sentinel chứa token; writer-lock.json lưu cùng
    token. release() chỉ thao khi token khớp — writer cũ gọi release
    muộn KHÔNG xóa sentinel hay ghi locked=false đè metadata của writer
    mới (token khác -> NO-OP an toàn).

    PARTIAL FAILURE: lỗi sau khi tạo sentinel nhưng trước khi acquire
    hoàn tất -> cleanup sentinel do chính writer này vừa tạo, đưa
    metadata về unlocked nhất quán (atomic write), re-raise."""
    import uuid
    token = uuid.uuid4().hex
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        fail(['writer-lock đang bị giữ (sentinel %s tồn tại) — từ chối, không promote.' % LOCK_FILE])
    # từ sau điểm này mọi lỗi phải cleanup sentinel + metadata rồi re-raise
    try:
        os.write(fd, token.encode('utf-8'))
        os.close(fd)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.remove(LOCK_FILE)  # sentinel do chính writer này vừa tạo
        except FileNotFoundError:
            pass
        _write_json_atomic(LOCK, _unlocked_meta(
            'Lock acquire thất bại giữa chừng — cleanup partial failure.'))
        raise
    try:
        _write_json_atomic(LOCK, {
            'locked': True, 'holder': holder, 'acquired_at': now_iso(),
            'expires_at': None, 'updated_at': now_iso(),
            'token': token,
            'note': 'Sentinel thật: data/state/writer-lock.active (O_EXCL).'})
    except Exception:
        try:
            os.remove(LOCK_FILE)
        except FileNotFoundError:
            pass
        _write_json_atomic(LOCK, _unlocked_meta(
            'Lock acquire thất bại giữa chừng — cleanup partial failure.'))
        raise

    def release():
        """Chỉ thao lock khi token sentinel (hoặc token metadata khi
        sentinel đã mất) khớp token của writer này. Token khác -> NO-OP,
        không mutate sentinel/metadata của writer mới."""
        try:
            with open(LOCK_FILE, encoding='utf-8') as f:
                cur = f.read().strip()
        except FileNotFoundError:
            # sentinel không còn: nếu metadata token khớp token này thì
            # đưa metadata về unlocked; token khác -> NO-OP.
            try:
                meta = json.load(open(LOCK, encoding='utf-8'))
            except FileNotFoundError:
                return
            if meta.get('token') == token:
                _write_json_atomic(LOCK, _unlocked_meta(
                    'Lock đã được release (sentinel không còn, token khớp).'))
            return
        if cur != token:
            # sentinel thuộc writer khác -> NO-OP an toàn
            return
        os.remove(LOCK_FILE)
        _write_json_atomic(LOCK, _unlocked_meta(
            'Lock phải được giữ trong suốt một chunk và nhả khi checkpoint an toàn. '
            'Không bao giờ chạy hai writer song song.'))
    return release


def txn_append(txn, entry, active, pending=None):
    """APPEND history (có giới hạn), KHÔNG reset history cũ."""
    hist = txn.get('history') or []
    hist.append(entry)
    txn['active'] = active
    txn['updated_at'] = now_iso()
    txn['pending'] = pending
    txn['history'] = hist[-HISTORY_MAX:]
    txn['note'] = txn.get('note') or ('Ghi transaction trước khi mutate. Nếu pending khác null '
                                      'ở lần chạy sau: recover/hoàn tất trước khi làm việc mới.')
    json.dump(txn, open(TXN, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def commit_sha():
    try:
        import subprocess
        out = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True,
                             text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--draft', required=True)
    ap.add_argument('--id', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    errs = []
    aid = args.id
    holder = 'publish-gate-%s' % aid

    # 1. acquire lock TRƯỚC mọi kiểm tra (race-safe)
    if args.dry_run:
        # dry-run: chỉ đọc, không giữ lock lâu — vẫn kiểm tra lock không bị giữ
        if os.path.exists(LOCK_FILE):
            fail(['writer-lock đang bị giữ — từ chối dry-run.'])
    else:
        release = acquire_lock(holder)

    def cleanup():
        if not args.dry_run:
            try:
                release()
            except NameError:
                pass

    # 2. transaction conflicting?
    txn = json.load(open(TXN, encoding='utf-8')) if os.path.exists(TXN) else {
        'active': False, 'updated_at': now_iso(), 'pending': None, 'history': []}
    if txn.get('active'):
        fail(['transaction đang active (%s) — recover/hoàn tất trước khi promote.'
              % txn.get('pending')], release=cleanup if not args.dry_run else None)

    # 3. matrix hàng PASS
    if not os.path.exists(MATRIX):
        fail(['matrix thiếu — không thể promote'], release=cleanup if not args.dry_run else None)
    with open(MATRIX, encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    row = next((r for r in rows if r['id'] == aid), None)
    if row is None:
        fail(['không tìm thấy %s trong matrix' % aid], release=cleanup if not args.dry_run else None)
    if row['status'] != 'PASS':
        fail(['trạng thái %s là %s — gate chỉ promote hàng PASS (WRITING/QA/PLANNED bị từ chối)'
              % (aid, row['status'])], release=cleanup if not args.dry_run else None)

    # 4. bằng chứng QA
    qa_path = os.path.join(QA_DIR, aid + '.json')
    if not os.path.exists(qa_path):
        fail(['thiếu bằng chứng chấm điểm: %s' % qa_path], release=cleanup if not args.dry_run else None)
    qa = json.load(open(qa_path, encoding='utf-8'))
    if qa.get('quality', 0) < QUALITY_MIN:
        errs.append('quality %s < %d' % (qa.get('quality'), QUALITY_MIN))
    if qa.get('seo', 0) < SEO_MIN:
        errs.append('seo %s < %d' % (qa.get('seo'), SEO_MIN))
    if qa.get('business_fact') != 'PASS':
        errs.append('business_fact phải PASS, có %s' % qa.get('business_fact'))
    if qa.get('legal') not in ('PASS', 'NOT_REQUIRED'):
        errs.append('legal phải PASS/NOT_REQUIRED, có %s' % qa.get('legal'))
    if qa.get('critical_failure', True):
        errs.append('critical_failure phải là false')
    if errs:
        fail(errs, release=cleanup if not args.dry_run else None)

    # 5. draft tồn tại + frontmatter + KHÔNG placeholder
    if not os.path.exists(args.draft) or not args.draft.startswith('_drafts/'):
        fail(['draft không tồn tại hoặc không nằm trong _drafts/: %s' % args.draft],
             release=cleanup if not args.dry_run else None)
    text = open(args.draft, encoding='utf-8').read()
    fm = re.match(r'^---\n(.*?)\n---', text, re.S)
    if not fm:
        fail(['draft thiếu frontmatter'], release=cleanup if not args.dry_run else None)
    front = fm.group(1)
    for field in ('title:', 'date:', 'categories:', 'description:'):
        if field not in front:
            fail(['draft thiếu frontmatter: %s' % field], release=cleanup if not args.dry_run else None)
    if 'MẪU NHẬP BÀI' in text or 'lorem' in text.lower():
        fail(['draft còn placeholder nháp'], release=cleanup if not args.dry_run else None)

    # 6. GẮNG NỘI DUNG: sha256 draft hiện tại == qa.content_sha256
    draft_sha = sha256_file(args.draft)
    if not qa.get('content_sha256'):
        fail(['bằng chứng QA thiếu content_sha256 (bắt buộc từ phiên bản gate v3)'],
             release=cleanup if not args.dry_run else None)
    if draft_sha != qa['content_sha256']:
        fail(['STALE_QA_EVIDENCE: sha256 draft (%s) != qa.content_sha256 (%s) — '
              'nội dung đã đổi sau khi QA chấm. Chấm lại QA trước khi promote.'
              % (draft_sha[:12], qa['content_sha256'][:12])],
             release=cleanup if not args.dry_run else None)

    # 7. GẮNG HÀNG MATRIX: vân tay hàng hiện tại == qa.matrix_row_sha256
    if not qa.get('matrix_row_sha256'):
        fail(['bằng chứng QA thiếu matrix_row_sha256 (bắt buộc từ phiên bản gate v3)'],
             release=cleanup if not args.dry_run else None)
    row_fp = matrix_row_sha256(row)
    if row_fp != qa['matrix_row_sha256']:
        fail(['MATRIX_ROW_MISMATCH: vân tay hàng matrix (%s) != qa.matrix_row_sha256 (%s) — '
              'title/slug/URL/intent/keyword đổi sau khi QA. Cập nhật QA hoặc hàng matrix.'
              % (row_fp[:12], qa['matrix_row_sha256'][:12])],
             release=cleanup if not args.dry_run else None)

    # 8. slug/đường dẫn khớp hàng matrix
    dm = re.match(r'(\d{4}-\d{2}-\d{2})-', os.path.basename(args.draft))
    if not dm:
        fail(['tên draft phải dạng YYYY-MM-DD-slug.md: %s' % args.draft],
             release=cleanup if not args.dry_run else None)
    date_part = dm.group(1)
    op = row['output_path']
    if op.startswith('_posts/{date}-'):
        slug_want = op[len('_posts/{date}-'):-3]
    else:
        om = re.match(r'_posts/\d{4}-\d{2}-\d{2}-(.+\.md)$', op)
        if not om:
            fail(['output_path matrix sai định dạng: %s' % op],
                 release=cleanup if not args.dry_run else None)
        slug_want = om.group(1)[:-3]
    slug_have = os.path.basename(args.draft)[11:-3]
    if slug_have != slug_want:
        fail(['slug draft (%s) != slug matrix (%s)' % (slug_have, slug_want)],
             release=cleanup if not args.dry_run else None)
    dest = '_posts/%s-%s.md' % (date_part, slug_want)

    if args.dry_run:
        print('=== PUBLISH GATE: DRY-RUN PASS (không đổi gì) ===')
        print('sẽ promote %s -> %s' % (args.draft, dest))
        return

    # 9. mở transaction -> promote -> đóng, append history
    entry = {'article_id': aid, 'started_at': now_iso(),
             'source': args.draft, 'destination': dest,
             'result': None, 'commit_sha': commit_sha()}
    txn_append(txn, entry, active=True, pending={'step': 'promote %s' % aid, 'draft': args.draft})

    try:
        shutil.move(args.draft, dest)
        for r in rows:
            if r['id'] == aid:
                r['status'] = 'PUBLISHED'
                r['output_path'] = dest
                r['expected_url'] = r['expected_url'].replace(
                    '{date}', '%s/%s/%s' % (date_part[:4], date_part[5:7], date_part[8:]))
                r['canonical_url'] = r['expected_url']
        fields = list(rows[0].keys())
        with open(MATRIX, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
            w.writeheader()
            w.writerows(rows)

        # ---- đồng bộ bằng chứng QA sau promote (gate là chủ sở hữu của
        # chuyển tiếp WRITING/PASS -> PUBLISHED): hàng matrix được chốt
        # {date} thật và nguồn chuyển _drafts -> _posts, nên vân tay hàng
        # và source_path trong bằng chứng phải được làm mới cùng lúc.
        # Nội dung bài không đổi khi move -> content_sha256 giữ nguyên.
        qap = os.path.join(QA_DIR, aid + '.json')
        if os.path.exists(qap):
            qev = json.load(open(qap, encoding='utf-8'))
            qev['source_path'] = dest
            qev['matrix_row_sha256'] = matrix_row_sha256(
                next(r for r in rows if r['id'] == aid))
            qev['published_at'] = now_iso()
            _write_json_atomic(qap, qev)

        cp = json.load(open(CP, encoding='utf-8'))
        planned_left = [r['id'] for r in rows if r['status'] == 'PLANNED']
        cp['last_completed_article_id'] = aid
        cp['next_claimable_id'] = planned_left[0] if planned_left else None
        cp['updated_at'] = now_iso()  # state đổi vật lý — giờ thật
        cp['last_run_id'] = 'publish-gate-' + aid
        cp['counts']['planned'] = sum(1 for r in rows if r['status'] == 'PLANNED')
        cp['counts']['published'] = sum(1 for r in rows if r['status'] == 'PUBLISHED')
        json.dump(cp, open(CP, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

        entry['finished_at'] = now_iso()
        entry['result'] = 'PUBLISHED'
        entry['destination'] = dest
        entry['rollback'] = 'revert commit promote; chạy lại generate-reports.py'
        txn['history'][-1] = entry
        txn_append(txn, None, active=False, pending=None)
        release()
        print('=== PUBLISH GATE: PROMOTED ===')
        print('%s -> %s' % (args.draft, dest))
        print('checkpoint: last_completed=%s next_claimable=%s' % (aid, cp['next_claimable_id']))
        print('history: %d mục (không reset)' % len(txn['history']))
    except Exception:
        # dở dang: trả draft về _drafts/, ghi history FAIL, đóng transaction, release lock
        if os.path.exists(dest) and not os.path.exists(args.draft):
            shutil.move(dest, args.draft)
        entry['finished_at'] = now_iso()
        entry['result'] = 'FAIL'
        txn['history'][-1] = entry
        txn_append(txn, None, active=False, pending=None)
        release()
        raise


if __name__ == '__main__':
    main()
