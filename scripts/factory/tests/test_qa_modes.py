#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test QA modes (FAST/DEEP/FULL) + release-chunk + bất biến sản xuất thủ công.

Chạy: python3 scripts/factory/tests/test_qa_modes.py (từ gốc repository)

Chứng minh (docs/PROC-PUBLISH.md "QA modes"):
  - FAST (scope chunk) CHỈ kiểm chunk hiện tại + nền bắt buộc: một lỗi
    toàn site (URL legacy sai, hash QA bài PUBLISHED ngoài chunk) KHÔNG
    chặn FAST, nhưng DEEP/FULL phát hiện được.
  - FAST vẫn chấm đầy đủ từng bài (ngưỡng 90/90, legal, business facts)
    và VẪN publish được khi FULL audit FAIL (lỗi ngoài chunk).
  - release-chunk: pause an toàn — chỉ trả hàng WRITING chưa có draft;
    hàng có draft/QA evidence được giữ; PUBLISHED không bị hạ.
  - prepare-next: chặn khi còn hàng dở (resume-first), kẹp max 10.
  - lock O_EXCL chặn hai writer; recover hoàn tất transaction treo.
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

IGNORE = shutil.ignore_patterns('.git', '_site', '.jekyll-cache', '__pycache__',
                                'node_modules', 'vendor', '*.pyc')


def run_py(args, cwd):
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True,
                       cwd=cwd)
    return r


def matrix_rows(fx):
    with open(os.path.join(fx, 'data/content-matrix.csv'), encoding='utf-8',
              newline='') as f:
        return list(csv.DictReader(f))


def save_matrix(fx, rows):
    with open(os.path.join(fx, 'data/content-matrix.csv'), 'w', encoding='utf-8',
              newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def cp_json(fx, rel):
    return json.load(open(os.path.join(fx, rel), encoding='utf-8'))


def write_json(fx, rel, obj):
    p = os.path.join(fx, rel)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def corrupt_legacy_url(fx):
    """Lỗi toàn site: đổi current_url của 1 bài legacy trong inventory."""
    p = os.path.join(fx, 'data/content-inventory.csv')
    rows = list(csv.DictReader(open(p, encoding='utf-8')))
    rows[0]['current_url'] = '/blog/kinh-nghiem/1999/01/01/sai-url-danh-roi/'
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def corrupt_published_qa_hash(fx, aid):
    p = os.path.join(fx, 'data/qa', aid + '.json')
    qa = json.load(open(p, encoding='utf-8'))
    qa['content_sha256'] = '0' * 64
    json.dump(qa, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def first_writing(fx):
    return next(r for r in matrix_rows(fx) if r['status'] == 'WRITING')


def first_published_planned(fx):
    return next(r for r in matrix_rows(fx)
                if r['status'] == 'PUBLISHED' and r['source'].startswith('planned:'))


def borrow_planned_row(fx, count=1, skip_ids=None):
    """Hermetic khi queue cạn: repo thật có thể đã publish hết hàng planned
    (không còn PLANNED, không còn chunk đang làm). Mượn ĐỦ `count` hàng
    planned:PUBLISHED của BẢN SAO về đúng trạng thái TRƯỚC promote (top-up:
    chỉ mượn phần thiếu so với số hàng PLANNED đã có): xóa bài _posts +
    evidence QA tương ứng trong bản sao, trả hàng về PLANNED, hạ
    in_progress_chunk, đồng bộ checkpoint và tái sinh outputs
    deterministic (như pause an toàn). No-op khi đã đủ hàng PLANNED thật.
    skip_ids: KHÔNG mượn lại những ID này (soak test dài nhiều vòng: mượn
    lại hàng đã mượn tạo duplicate PUBLISHED trong transaction history).
    Repo thật KHÔNG bị đụng."""
    rows = matrix_rows(fx)
    need = count - sum(1 for r in rows if r['status'] == 'PLANNED')
    if need <= 0:
        return
    skip = set(skip_ids or ())
    cp = cp_json(fx, 'data/state/checkpoint.json')
    cands = [x for x in rows
             if x['status'] == 'PUBLISHED'
             and x['source'].startswith('planned:')
             and x['id'] not in skip
             # Hermetic đúng trạng thái trước promote: chỉ mượn hàng ĐÃ
             # CÓ batch_id — hàng PLANNED thật luôn có batch_id (schema
             # v2, validate.py bắt buộc). Mượn hàng planned:PUBLISHED
             # không batch_id về PLANNED sẽ bị generate-matrix.py đánh
             # lô mới sau max (ví dụ B011) ngay tại vị trí đầu file,
             # phá bất biến "batch_id không giảm theo thứ tự file" mà
             # validate.py kiểm ở mọi scope (fail tại BLG-00486).
             and (x.get('batch_id') or '').strip()]
    assert len(cands) >= need, ('không còn đủ hàng planned:PUBLISHED có '
                                'batch_id để mượn (cần %d, có %d)'
                                % (need, len(cands)))
    taken = cands[:need]
    for r in taken:
        post = os.path.join(fx, r['output_path'])
        if os.path.exists(post):
            os.remove(post)
        evp = os.path.join(fx, 'data', 'qa', r['id'] + '.json')
        if os.path.exists(evp):
            os.remove(evp)
    taken_ids = set(r['id'] for r in taken)
    for x in rows:
        if x['id'] in taken_ids:
            x['status'] = 'PLANNED'
    save_matrix(fx, rows)
    counts = {}
    for x in rows:
        counts[x['status']] = counts.get(x['status'], 0) + 1
    cp['in_progress_chunk'] = None
    nc = min(x['id'] for x in taken)
    cur = cp.get('next_claimable_id')
    if cur is None or nc < cur:
        cp['next_claimable_id'] = nc
    cp['counts'] = {'legacy_total': cp['counts'].get('legacy_total', 483),
                    'existing': counts.get('EXISTING', 0),
                    'review': counts.get('REVIEW', 0),
                    'planned': counts.get('PLANNED', 0),
                    'writing': counts.get('WRITING', 0),
                    'qa': counts.get('QA', 0),
                    'pass': counts.get('PASS', 0),
                    'published': counts.get('PUBLISHED', 0),
                    'repair': counts.get('REPAIR', 0),
                    'blocked': counts.get('BLOCKED', 0),
                    'fail': counts.get('FAIL', 0)}
    write_json(fx, 'data/state/checkpoint.json', cp)
    for script in ('generate-reports.py', 'generate-matrix.py',
                   'generate-listing-pages.py'):
        rr = run_py(['scripts/factory/' + script], fx)
        assert rr.returncode == 0, script + ': ' + rr.stdout + rr.stderr


# draft mẫu đạt gate cho hàng cho trước. Sau QA hardening của engine,
# draft mẫu PHẢI: (i) permalink gốc-tương-đối — bóc tiền tố /blog khỏi
# canonical_url (baseurl chỉ thêm khi render); (ii) chứa đủ liên kết theo
# cột internal_links của chính hàng đó + hub cha, tổng 3-8 liên kết hợp
# lệ; (iii) đủ số từ trong dải word_target ±15% của hàng — phần đệm là
# prose Việt trung lập, câu duy nhất, đoạn dưới 160 từ, không số tiền,
# không số điện thoại, không cam kết (forbidden_claims).
DRAFT_TMPL = """---
date: {date} 09:00:00 +0700
layout: post
title: "{title}"
author: "Nguyễn Tú"
description: "{desc}"
categories: [An toàn pháp lý]
lang: vi
tags: [{tag}]
permalink: {permalink}
parent_id: {parent_id}
child_id: {child_id}
article_id: {aid}
---

{kw} là câu hỏi của nhiều người đi xe máy quanh Hà Nội. Bài này tóm tắt
cách nhận biết trường hợp thiếu bảo hiểm và việc cần làm tiếp theo.

## {kw} theo quy định hiện hành

Khi bị kiểm tra trên đường ở khu vực Long Biên hoặc Hoàn Kiếm, người lái
xe cần xuất trình giấy chứng nhận bảo hiểm trách nhiệm dân sự còn hiệu
lực. Thiếu giấy này, cán bộ xử phạt sẽ lập biên bản theo quy định.

## Cần làm gì khi thiếu bảo hiểm

{links_md}

## Nguồn tham khảo

Văn bản chính thức: https://vanban.chinhphu.vn/?pageid=1

Lưu ý: mức phạt và quy định có thể thay đổi, kiểm tra văn bản mới nhất
trước khi áp dụng.
"""

FILLER_SUBJ = ['Người lái xe', 'Người thuê xe', 'Người đi đường',
               'Người mới lái xe', 'Khách thuê xe cuối tuần',
               'Người đi làm buổi sáng']
FILLER_VERB = ['nên kiểm tra', 'nên đối chiếu', 'nên chuẩn bị',
               'nên lưu ý', 'nên xem lại', 'nên sắp xếp']
FILLER_OBJ = ['giấy tờ cá nhân trước khi xuất phát',
              'trạng thái đèn và còi của xe',
              'lốp và áp suất bánh trước chuyến đi dài',
              'tuyến đường dự phòng khi trung tâm ùn tắc',
              'thời tiết trong ngày để chọn giờ đi hợp lý',
              'nơi gửi xe an toàn gần điểm đến']


def _hub_url(fx, parent_id):
    tax = json.load(open(os.path.join(fx, 'data/content-taxonomy.json'),
                         encoding='utf-8'))
    for p in tax.get('parents', []):
        if p.get('parent_id') == parent_id:
            return p.get('hub_url')
    return None


def make_draft(fx, row):
    d = '2026-09-28'
    slug = row['output_path'][len('_posts/{date}-'):-3]
    desc = ('%s: cách xác định trường hợp thiếu bảo hiểm khi lưu thông ở Hà Nội, '
            'thủ tục cần làm và nguồn văn bản chính thức để đối chiếu.'
            % row['primary_keyword'])
    if len(desc) < 140:
        desc += ' Đối chiếu văn bản hiện hành trước khi áp dụng.'
    if len(desc) < 140:
        desc += ' Nội dung mang tính tham khảo.'
    desc = desc[:160]
    assert 140 <= len(desc) <= 160, len(desc)
    required = [l for l in (row['internal_links'].split('; ')
                            if row['internal_links'] else []) if l]
    hub = _hub_url(fx, row['parent_id'])
    links = list(required)
    if hub and not any(l.startswith(hub) for l in links):
        links.append(hub)
    backup = [x for x in (hub, '/blog/an-toan-phap-ly/', '/blog/thue-xe/')
              if x]
    for cand in backup:
        if len(links) >= 3:
            break
        if not any(l == cand for l in links):
            links.append(cand)
    links = links[:8]
    anchors = ['xem nhóm bài liên quan', 'đọc chủ đề hướng dẫn',
               'đối chiếu trang chủ đề', 'xem thêm bài cùng chủ đề',
               'tham khảo trang chủ đề', 'đọc nhóm bài liên quan',
               'xem chủ đề tổng hợp', 'đối chiếu nhóm bài liên quan']
    parts = ['[%s](%s)' % (anchors[i % len(anchors)], l)
             for i, l in enumerate(links)]
    links_md = ('Người thuê xe nên đọc lần lượt ' + ', '.join(parts[:-1])
                + ' và ' + parts[-1] + ' trước khi tiếp tục hành trình.')
    text = DRAFT_TMPL.format(
        date=d, title=row['title'], desc=desc, tag='bao-hiem',
        kw=row['primary_keyword'],
        permalink=re.sub(r'^/blog', '',
                         row['canonical_url'].replace('{date}', '2026/09/28')),
        parent_id=row['parent_id'], child_id=row['child_id'], aid=row['id'],
        links_md=links_md)
    # đệm prose đến đúng dải word_target ±15% của hàng (engine đọc lại
    # word_target từ matrix được sinh lại từ seed, không dùng chỉ số cố định)
    target = int(row['word_target'] or 1200)
    fm_end = text.index('\n---\n') + len('\n---\n')
    body = text[fm_end:]
    words = len(body.split())
    i = 0
    extra = []
    while words < target and i < 216:
        para = []
        for _ in range(6):
            if words >= target or i >= 216:
                break
            s = '%s %s %s.' % (
                FILLER_SUBJ[i % len(FILLER_SUBJ)],
                FILLER_VERB[(i // len(FILLER_SUBJ)) % len(FILLER_VERB)],
                FILLER_OBJ[(i // (len(FILLER_SUBJ) * len(FILLER_VERB)))
                           % len(FILLER_OBJ)])
            para.append(s)
            words += len(s.split())
            i += 1
        extra.append(' '.join(para))
    if extra:
        text = text[:fm_end] + body + '\n\n' + '\n\n'.join(extra)
    if len(desc) < 140:
        desc += ' Đối chiếu văn bản hiện hành trước khi áp dụng.'

    open(os.path.join(fx, '_drafts', '%s-%s.md' % (d, slug)), 'w',
         encoding='utf-8').write(text)
    return os.path.join(fx, '_drafts', '%s-%s.md' % (d, slug))


def set_word_target(fx, aid, n):
    rows = matrix_rows(fx)
    for r in rows:
        if r['id'] == aid:
            r['word_target'] = str(n)
    save_matrix(fx, rows)


class FxTestCase(unittest.TestCase):
    """Sao chép repository thật vào thư mục tạm cho MỖI test — mọi mutation
    xảy ra trên bản sao riêng, test độc lập với nhau."""

    def setUp(self):
        base = tempfile.mkdtemp(prefix='qa-modes-')
        self.fx = os.path.join(base, 'repo')
        shutil.copytree(ROOT, self.fx, ignore=IGNORE)
        # hermetic: fixture KHÔNG mang draft của repo thựt — mọi draft
        # cần cho test đều do make_draft() tạo trong fixture. Trạng thái
        # WRITING của repo thựt có thể đã có draft (writer đã push), làm
        # lệch tiền đề "WRITING chưa có draft" của release-chunk
        # và prepare-next trong bộ test này.
        drafts_dir = os.path.join(self.fx, '_drafts')
        for fn in os.listdir(drafts_dir):
            os.remove(os.path.join(drafts_dir, fn))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)

    def py(self, *args):
        return run_py(list(args), self.fx)

    def validate(self, scope, ids=''):
        cmd = ['scripts/factory/validate.py', '--scope', scope]
        if ids:
            cmd += ['--ids', ids]
        return self.py(*cmd)

    def operator(self, *args):
        return self.py('scripts/factory/factory-operator.py', *args)

    def pause_in_progress_chunk(self):
        """Hermetic: repo thật có thể đang giữ in_progress_chunk với hàng
        đã claim/chưa publish (WRITING/QA/REPAIR/PASS) — prepare-next đúng
        chuẩn TỪ CHỐI claim mới (resume-first). Fixture mô phỏng pause an
        toàn: trả hàng chunk chưa PUBLISHED về PLANNED (đúng trạng thái
        trước khi claim), xóa chunk + evidence QA của các hàng đó, đồng bộ
        checkpoint + outputs deterministic (không đụng repo thật)."""
        rows = matrix_rows(self.fx)
        cp = cp_json(self.fx, 'data/state/checkpoint.json')
        chunk = cp.get('in_progress_chunk') or []
        if not chunk:
            return
        reset_ids = [r['id'] for r in rows
                     if r['id'] in chunk
                     and r['status'] in ('WRITING', 'QA', 'REPAIR', 'PASS')]
        if not reset_ids:
            return
        for r in rows:
            if r['id'] in reset_ids:
                r['status'] = 'PLANNED'
        save_matrix(self.fx, rows)
        for aid in reset_ids:
            evp = os.path.join(self.fx, 'data', 'qa', aid + '.json')
            if os.path.exists(evp):
                os.remove(evp)
        counts = {}
        for r in rows:
            counts[r['status']] = counts.get(r['status'], 0) + 1
        cp['in_progress_chunk'] = None
        nc = min(reset_ids)
        cur = cp.get('next_claimable_id')
        if cur is None or nc < cur:
            cp['next_claimable_id'] = nc
        cp['counts'] = {'legacy_total': cp['counts'].get('legacy_total', 483),
                        'existing': counts.get('EXISTING', 0),
                        'review': counts.get('REVIEW', 0),
                        'planned': counts.get('PLANNED', 0),
                        'writing': counts.get('WRITING', 0),
                        'qa': counts.get('QA', 0),
                        'pass': counts.get('PASS', 0),
                        'published': counts.get('PUBLISHED', 0),
                        'repair': counts.get('REPAIR', 0),
                        'blocked': counts.get('BLOCKED', 0),
                        'fail': counts.get('FAIL', 0)}
        write_json(self.fx, 'data/state/checkpoint.json', cp)
        for script in ('generate-reports.py', 'generate-matrix.py',
                       'generate-listing-pages.py'):
            rr = self.py('scripts/factory/' + script)
            self.assertEqual(rr.returncode, 0,
                             script + ': ' + rr.stdout + rr.stderr)

    def ensure_writing_chunk(self, count=10):
        """Test resume/release cần trạng thái 'đang làm chunk' HOÀN TOÀN do
        fixture tự tạo. Repository thật có thể đang giữ chunk HỢP LỆ giữa
        đợt (hàng WRITING/QA/REPAIR/PASS, kèm draft/evidence QA) — nếu các
        hàng đó rò vào fixture thì operator đúng chuẩn từ chối/đếm sai so
        với kỳ vọng của test. Hermetic: đưa MỌI hàng đang làm của fixture
        vào in_progress_chunk (chỉ trong fixture), pause an toàn (trả về
        PLANNED, xóa evidence QA đúng các hàng đó — draft đã bị setUp xóa)
        rồi claim lại đúng count hàng. FULL verify phải chạy được cả khi
        repo thật đang có chunk đang làm."""
        rows = matrix_rows(self.fx)
        doing = [r['id'] for r in rows
                 if r['status'] in ('WRITING', 'QA', 'REPAIR', 'PASS')]
        if doing:
            cp = cp_json(self.fx, 'data/state/checkpoint.json')
            chunk = set(cp.get('in_progress_chunk') or []) | set(doing)
            cp['in_progress_chunk'] = sorted(chunk)
            write_json(self.fx, 'data/state/checkpoint.json', cp)
        self.pause_in_progress_chunk()
        # Queue cạn (không đủ PLANNED): mượn thêm hàng trong bản sao.
        borrow_planned_row(self.fx, count)
        r = self.operator('prepare-next', '--count', str(count))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class TestScopeGating(FxTestCase):

    def test_sections_by_scope(self):
        r = self.validate('chunk')
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('"scope": "chunk"', r.stdout)
        self.assertNotIn('"live_sitemap"', r.stdout)
        self.assertNotIn('"inventory_legacy_urls"', r.stdout)
        r = self.validate('batch')
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('"inventory_legacy_urls"', r.stdout)
        self.assertNotIn('"live_sitemap"', r.stdout)
        r = self.validate('full')
        self.assertIn('"live_sitemap"', r.stdout)

    def test_site_wide_legacy_url_breaks_deep_and_full_not_fast(self):
        corrupt_legacy_url(self.fx)
        r = self.validate('chunk')
        self.assertEqual(r.returncode
, 0, r.stdout + r.stderr)
        r = self.validate('batch')
        self.assertEqual(r.returncode, 1)
        self.assertIn('URL legacy sai', r.stdout)
        r = self.validate('full')
        self.assertEqual(r.returncode, 1)

    def test_qa_evidence_outside_chunk_ignored_by_fast(self):
        self.ensure_writing_chunk()
        pub = first_published_planned(self.fx)
        corrupt_published_qa_hash(self.fx, pub['id'])
        writing = first_writing(self.fx)
        # FAST (chunk, theo checkpoint chunk hiện tại) không kiểm bài ngoài chunk
        r = self.validate('chunk', writing['id'])
        self.assertEqual(r.returncode, 0, r.stdout)
        # FAST khi bài đó nằm trong ids -> phải FAIL
        r = self.validate('chunk', pub['id'])
        self.assertEqual(r.returncode, 1)
        self.assertIn('content_sha256', r.stdout)
        # DEEP kiểm toàn bộ -> FAIL
        r = self.validate('batch')
        self.assertEqual(r.returncode, 1)

    def test_bad_scope_rejected(self):
        r = self.validate('khongtoncai')
        self.assertNotEqual(r.returncode, 0)


class TestReleaseChunk(FxTestCase):

    def test_release_writing_rows_without_drafts(self):
        self.ensure_writing_chunk()
        rows = matrix_rows(self.fx)
        writing = [r['id'] for r in rows if r['status'] == 'WRITING']
        self.assertEqual(len(writing), 10)
        planned_before = sum(1 for r in rows if r['status'] == 'PLANNED')
        r = self.operator('release-chunk')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = matrix_rows(self.fx)
        for aid in writing:
            self.assertEqual(next(x['status'] for x in rows if x['id'] == aid),
                             'PLANNED')
        cp = cp_json(self.fx, 'data/state/checkpoint.json')
        self.assertIsNone(cp['in_progress_chunk'])
        self.assertEqual(cp['next_claimable_id'], min(writing))
        self.assertEqual(cp['counts']['planned'], planned_before + len(writing))
        self.assertEqual(cp['counts']['writing'], 0)

    def test_release_keeps_rows_with_drafts(self):
        self.ensure_writing_chunk()
        rows = matrix_rows(self.fx)
        keep = first_writing(self.fx)
        make_draft(self.fx, keep)
        r = self.operator('release-chunk')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = matrix_rows(self.fx)
        self.assertEqual(next(x['status'] for x in rows if x['id'] == keep['id']),
                         'WRITING')
        cp = cp_json(self.fx, 'data/state/checkpoint.json')
        self.assertEqual(cp['in_progress_chunk'], [keep['id']])

    def test_release_refuses_published(self):
        pub = first_published_planned(self.fx)
        r = self.operator('release-chunk', '--ids', pub['id'])
        self.assertEqual(r.returncode, 0)
        rows = matrix_rows(self.fx)
        self.assertEqual(next(x['status'] for x in rows if x['id'] == pub['id']),
                         'PUBLISHED')

    def test_published_not_regressed_by_qa(self):
        pub = first_published_planned(self.fx)
        r = self.operator('qa', '--ids', pub['id'])
        self.assertEqual(r.returncode, 0)
        rows = matrix_rows(self.fx)
        self.assertEqual(next(x['status'] for x in rows if x['id'] == pub['id']),
                         'PUBLISHED')


class TestManualProductionFlow(FxTestCase):

    def test_prepare_next_resumes_writing_first_and_clamps_10(self):
        self.ensure_writing_chunk()
        # còn hàng WRITING -> từ chối nhận mới (resume-first)
        r = self.operator('prepare-next', '--count', '5')
        self.assertEqual(r.returncode, 1)
        self.assertIn('chưa xong', r.stdout)
        # release chunk để tiếp tục kẹp max
        self.assertEqual(self.operator('release-chunk').returncode, 0)
        r = self.operator('prepare-next', '--count', '15')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = matrix_rows(self.fx)
        self.assertEqual(len([x for x in rows if x['status'] == 'WRITING']), 10)
        cp = cp_json(self.fx, 'data/state/checkpoint.json')
        self.assertEqual(len(cp['in_progress_chunk']), 10)
        # next_claimable nhảy đúng: 10 ID đầu (theo thứ tự id)
        self.assertTrue(all(cp['next_claimable_id'] not in cp['in_progress_chunk']
                            for _ in [0]))

    def test_fast_qa_publishes_while_full_audit_fails(self):
        self.ensure_writing_chunk()
        corrupt_legacy_url(self.fx)          # lỗi toàn site
        r = self.validate('full')
        self.assertEqual(r.returncode, 1)   # FULL phát hiện
        row = first_writing(self.fx)
        # make_draft tự đệm prose tới đúng dải word_target ±15% của hàng
        make_draft(self.fx, row)
        r = self.operator('qa', '--scope', 'fast', '--ids', row['id'])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('PASS', r.stdout)
        rows = matrix_rows(self.fx)
        self.assertEqual(next(x['status'] for x in rows if x['id'] == row['id']),
                         'PASS')
        r = self.operator('publish', '--scope', 'fast', '--ids', row['id'])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('PUBLISHED', r.stdout)
        # bài thật nằm trong _posts, hàng matrix chốt PUBLISHED, URL có ngày thật
        rows = matrix_rows(self.fx)
        m = next(x for x in rows if x['id'] == row['id'])
        self.assertEqual(m['status'], 'PUBLISHED')
        self.assertNotIn('{date}', m['expected_url'])
        self.assertTrue(os.path.exists(os.path.join(self.fx, m['output_path'])))

    def test_fast_qa_repair_when_seo_below_threshold(self):
        self.ensure_writing_chunk()
        row = first_writing(self.fx)
        set_word_target(self.fx, row['id'], 100)
        p = make_draft(self.fx, row)
        # phá meta description (ngắn, thiếu từ khóa) -> seo < 90 -> REPAIR,
        # KHÔNG hạ ngưỡng
        text = open(p, encoding='utf-8').read()
        text = re.sub(r'^description: .*$', 
'description: "ngắn"',
                      text, count=1, flags=re.M)
        open(p, 'w', encoding='utf-8').write(text)
        r = self.operator('qa', '--scope', 'fast', '--ids', row['id'])
        self.assertEqual(r.returncode, 0)
        self.assertIn('REPAIR', r.stdout)
        rows = matrix_rows(self.fx)
        self.assertEqual(next(x['status'] for x in rows if x['id'] == row['id']),
                         'REPAIR')

    def test_threshold_constants_unchanged(self):
        self.assertEqual(op_mod().SEO_MIN, 90)
        self.assertEqual(op_mod().QUALITY_MIN, 90)
        self.assertEqual(op_mod().MAX_CHUNK, 10)

    def test_lock_blocks_second_writer(self):
        code = (
            "import importlib.util, os\n"
            "spec = importlib.util.spec_from_file_location('pg', "
            "'scripts/factory/publish-gate.py')\n"
            "pg = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(pg)\n"
            "r1 = pg.acquire_lock('test-writer-1')\n"
            "print('first-ok')\n"
            "try:\n"
            "    pg.acquire_lock('test-writer-2')\n"
            "    raise SystemExit('writer-2 duoc phep: SAI')\n"
            "except SystemExit as e:\n"
            "    if 'SAI' in str(e):\n"
            "        raise\n"
            "    print('writer-2 bi chan: OK')\n"
            "finally:\n"
            "    r1()\n"
        )
        r = subprocess.run([sys.executable, '-c', code], capture_output=True,
                           text=True, cwd=self.fx)
        self.assertIn('first-ok', r.stdout)
        self.assertIn('writer-2 bi chan: OK', r.stdout)
        # lock đã được nhả sạch sau test
        self.assertFalse(os.path.exists(os.path.join(
            self.fx, 'data/state/writer-lock.active')))

    def test_recover_completes_hanging_transaction(self):
        pub = first_published_planned(self.fx)
        txn = cp_json(self.fx, 'data/state/transaction.json')
        txn['active'] = True
        txn['pending'
] = {'article_id': pub['id'], 'step': 'promote',
                          'destination': pub['output_path'],
                          'source': '_drafts/2026-09-27-x.md'}
        write_json(self.fx, 'data/state/transaction.json', txn)
        r = self.operator('recover')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('transaction hoàn tất', r.stdout)
        txn = cp_json(self.fx, 'data/state/transaction.json')
        self.assertFalse(txn['active'])
        last = next((h for h in reversed(txn.get('history') or []) if h), None)
        self.assertIsNotNone(last)
        self.assertEqual(last.get('result'), 'RECOVERED_COMPLETED')


def op_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'factory_operator_test', os.path.join(ROOT, 'scripts/factory/factory-operator.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


if __name__ == '__main__':
    unittest.main(verbosity=2)
