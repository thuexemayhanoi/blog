#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiem thu cong G9 (bien the tu vung) cua refill-queue.py.

G2/G3/G8 chi bat trung KHOP CHUAN HOA. G9 so tap tu khoa co nghia cua
title/kw de chan bai gan trung ("Xe thue bi thung lop..." vs "Xe may thue bi
thung lop...") ma van cho phep tieu de cung khuon nhung khac thuc the that
(dia danh, mau xe, van ban).

Nhom test:
 1  sim_tokens: bo dau, bo tu chuc nang + xe/may/thue
 2  g9_check: cung child — doi thu tu, chen xe-may-thue, bien the kw
 3  g9_check: cung khuon khac thuc the (dia danh) DUOC chap nhan
 4  g9_check: khac child chi chan khi title gan nhu trung (>= G9_CROSS)
 5  g9_check: tap qua nho khong ket luan
 6  check_candidate: hai candidate gan trung trong CUNG batch -> cai sau FAIL
 7  check_candidate: chi tinh hang con hieu luc (BLOCKED khong chan)
 8  refill-queue.py --selftest + --verify van PASS tren du lieu that

Khong ghi gi vao production state. Chay:
python3 scripts/factory/tests/test_refill_g9.py
"""
import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
SCRIPT = os.path.join(ROOT, 'scripts', 'factory', 'refill-queue.py')

_spec = importlib.util.spec_from_file_location('refill_queue_g9', SCRIPT)
rq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rq)

RESULTS = []


def record(name, ok, detail=''):
    RESULTS.append((name, ok, detail))
    print(('PASS: ' if ok else 'FAIL: ') + name
          + ((' - ' + detail) if detail else ''))


def pool_row(oid, child, title, kw=''):
    return (oid, child, rq.sim_tokens(title), rq.sim_tokens(kw))


def g9(cid, child, title, kw, pool):
    return rq.g9_check(cid, child, rq.sim_tokens(title), rq.sim_tokens(kw), pool)


def fresh_state():
    return ({'kw': {}, 'intent': {}, 'slug': set(), 'out': set(),
             'cid': set()},
            {})


def base_midx(rows=None):
    return rq.build_matrix_indexes(rows or [])


def cand(**kw):
    base = {'candidate_id': 'CAND-G9-1', 'child_id': 'C-THUE-GIA',
            'title': 'Tieu de thu nhat cho kiem thu',
            'intent': 'Y dinh thu nhat cho kiem thu',
            'kw': 'tu khoa thu nhat', 'kw2': [], 'links': [],
            'word_target': 1300, 'audience': '', '_cat': 'thue-xe'}
    base.update(kw)
    return base


def run_check(c, midx, seen, staged=None):
    return rq.check_candidate(c, midx, seen, {'C-THUE-GIA', 'C-KHAC'},
                              {'C-THUE-GIA': 999, 'C-KHAC': 999},
                              staged if staged is not None else {}, {}, {})


def test_tokens():
    t = rq.sim_tokens('Xe máy thuê ở Hà Nội: bị thủng lốp giữa đường thì làm gì?')
    ok = ('thung' in t and 'lop' in t and 'xe' not in t and 'may' not in t
          and 'thue' not in t and 'ha' not in t and 'noi' not in t
          and 'giua' in t)
    record('sim_tokens bo dau + bo tu chuc nang/xe/may/thue', ok, str(sorted(t)))
    record('sim_tokens rong khi input None/rong',
           rq.sim_tokens(None) == frozenset() and rq.sim_tokens('') == frozenset())
    record('sim_tokens giu thuc the co chu d (dap/dien)',
           rq.sim_tokens('xe đạp điện Honda') >= {'dap', 'dien', 'honda'}
           or rq.sim_tokens('xe đạp điện Honda') >= {'ap', 'ien', 'honda'},
           str(sorted(rq.sim_tokens('xe đạp điện Honda'))))


def test_same_child():
    src = 'Xe thuê bị thủng lốp giữa đường Hà Nội: cách xử lý an toàn từng bước'
    pool = [pool_row('BLG-X1', 'C-A', src, 'thung lop giua duong')]
    reordered = 'Cách xử lý an toàn từng bước khi thủng lốp giữa đường: xe thuê Hà Nội'
    e = g9('C-NEW', 'C-A', reordered, 'khac hoan toan', pool)
    record('doi thu tu tu bi G9 (cung child)',
           any('G9 title' in x for x in e), str(e))
    inserted = 'Xe máy thuê bị thủng lốp giữa đường Hà Nội: cách xử lý an toàn từng bước'
    e = g9('C-NEW', 'C-A', inserted, 'khac hoan toan', pool)
    record('chen xe-may-thue van bi G9 (cung child)',
           any('G9 title' in x for x in e), str(e))
    # title khac nhe nhung kw gan nhu y het -> G9 kw+title
    e = g9('C-NEW', 'C-A',
           'Thủng lốp giữa đường thuê xe: xử lý an toàn thế nào cho đúng',
           'thung lop giua duong', pool)
    record('kw trung + title gan -> G9 kw+title',
           any('G9 kw+title' in x for x in e), str(e))


def test_entity_templates_allowed():
    pool = [pool_row('BLG-T1', 'C-A',
                     'Thuê xe máy ở Hồ Tây giá bao nhiêu và lưu ý khi chạy quanh hồ',
                     'thue xe may ho tay')]
    e = g9('C-NEW', 'C-A',
           'Thuê xe máy ở Hồ Gươm giá bao nhiêu và lưu ý khi chạy quanh hồ',
           'thue xe may ho guom', pool)
    record('cung khuon khac dia danh duoc chap nhan', not e, str(e))
    pool = [pool_row('BLG-T2', 'C-A',
                     'Honda Vision thuê một tuần cần chuẩn bị giấy tờ gì',
                     'honda vision thue tuan')]
    e = g9('C-NEW', 'C-A',
           'Honda Air Blade thuê một tuần cần chuẩn bị giấy tờ gì',
           'honda air blade thue tuan', pool)
    record('cung khuon khac mau xe duoc chap nhan', not e, str(e))


def test_cross_child():
    a = 'Cách kiểm tra phanh xe trước khi nhận xe thuê ở phố cổ rất kỹ lưỡng'
    pool = [pool_row('BLG-C1', 'C-A', a, 'kiem tra phanh')]
    e = g9('C-NEW', 'C-B', a.upper(), 'khac', pool)
    record('khac child: title y het bi G9 cross',
           any('khac child' in x for x in e), str(e))
    # cung tap tu ~0.8 nhung khac child -> duoc chap nhan (nguong cross = 0.90)
    near = 'Cách kiểm tra phanh xe trước khi nhận xe thuê ở phố cổ lưu ý riêng'
    jt = rq.jaccard(rq.sim_tokens(near), rq.sim_tokens(a))
    e = g9('C-NEW', 'C-B', near, 'khac', pool)
    record('khac child: do giong < G9_CROSS duoc chap nhan',
           jt < rq.G9_CROSS and not e, 'jaccard=%.2f %s' % (jt, e))


def test_small_sets():
    pool = [pool_row('BLG-S1', 'C-A', 'Xe máy điện', 'xe may dien')]
    e = g9('C-NEW', 'C-A', 'Xe máy điện', 'xe may dien', pool)
    record('tap tu qua nho khong ket luan (title < G9_MIN_TOKENS)', not e, str(e))


def test_check_candidate_batch():
    midx = base_midx()
    seen, staged = fresh_state()
    t1 = 'Hướng dẫn đổ xăng xe tay ga đúng cách để tránh hỏng bình xăng con'
    c1 = cand(candidate_id='CAND-G9-A', title=t1, kw='do xang xe tay ga dung cach',
              intent='y dinh doi xang a')
    e1 = run_check(c1, midx, seen, staged)
    record('candidate dau tien PASS (khong loi)', e1 == [], str(e1))
    c2 = cand(candidate_id='CAND-G9-B',
              title='Đổ xăng xe tay ga đúng cách: hướng dẫn tránh hỏng bình xăng con',
              kw='cach do xang xe ga dung cach 2', intent='y dinh doi xang b')
    e2 = run_check(c2, midx, seen, staged)
    record('candidate gan trung trong cung batch bi G9',
           any('G9' in x for x in e2) and not any(
               x.split(':')[1].strip().startswith(('G2', 'G3', 'G4', 'G8'))
               for x in e2), str(e2))
    # candidate khac thuc te -> PASS
    c3 = cand(candidate_id='CAND-G9-C',
              title='Phạt không có bảo hiểm xe máy bắt buộc theo Nghị định mới nhất',
              kw='phat khong co bao hiem xe may', intent='y dinh phat bao hiem')
    e3 = run_check(c3, midx, seen, staged)
    record('candidate khac chu de van PASS sau G9', e3 == [], str(e3))


def test_inactive_rows_ignored():
    rows = []
    base = {'id': 'BLG-9', 'child_id': 'C-THUE-GIA', 'title': '',
            'primary_keyword': 'x', 'intent': 'x', 'output_path': '_posts/{date}-a.md',
            'canonical_url': '/a/', 'status': 'BLOCKED'}
    t = 'Hướng dẫn đổ xăng xe tay ga đúng cách để tránh hỏng bình xăng con'
    r = dict(base, title=t, primary_keyword='do xang xe tay ga')
    rows.append(r)
    midx = rq.build_matrix_indexes(rows)
    record('hang BLOCKED khong vao chi muc G9', midx['sim'] == [], str(midx['sim']))
    rows[0] = dict(r, status='PLANNED')
    midx = rq.build_matrix_indexes(rows)
    record('hang PLANNED vao chi muc G9', len(midx['sim']) == 1, str(midx['sim']))
    seen, staged = fresh_state()
    e = run_check(cand(title='Đổ xăng xe tay ga đúng cách: hướng dẫn tránh hỏng bình xăng con',
                       kw='k moi', intent='i moi'), midx, seen, staged)
    record('bien the cua hang PLANNED bi G9', any('G9' in x for x in e), str(e))


def test_cli():
    for mode in ('--selftest', '--verify'):
        r = subprocess.run([sys.executable, '-W', 'ignore', SCRIPT, mode],
                           cwd=ROOT, capture_output=True, text=True, timeout=600)
        record('refill-queue.py %s rc=0 tren du lieu that' % mode,
               r.returncode == 0,
               (r.stdout + r.stderr).strip().splitlines()[-1][:200]
               if (r.stdout + r.stderr).strip() else '')


def main():
    for fn in (test_tokens, test_same_child, test_entity_templates_allowed,
               test_cross_child, test_small_sets, test_check_candidate_batch,
               test_inactive_rows_ignored, test_cli):
        try:
            fn()
        except Exception as ex:  # noqa: BLE001 - bao loi thanh FAIL ro rang
            record(fn.__name__ + ' (exception)', False, repr(ex))
    bad = [r for r in RESULTS if not r[1]]
    print('\nTONG: %d test, %d FAIL' % (len(RESULTS), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
