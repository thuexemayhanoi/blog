#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Registry + trang chuyển hướng cho di trú slug đ -> d (Issue #77). Module dùng chung, KHÔNG ghi gì khi import.

GitHub Pages không có HTTP 301 theo đường dẫn (bằng chứng runner: server GitHub.com, không lớp edge). Chủ repo đã chọn:
URL CŨ = trang HTTP 200 với `<meta http-equiv="refresh" content="0; url=MỚI">` + canonical MỚI, bị loại khỏi sitemap;
URL MỚI = bài thật. Báo cáo luôn gọi đúng tên "HTTP 200 + meta refresh", KHÔNG gọi là 301.

Ba nguồn sự thật (đều nằm trong repo):
  slug-d-baseline.csv          danh sách ĐÓNG BĂNG 1.410 bài đã xuất bản có slug thiếu chữ d (sha256 được ghim trong test);
                               đây là tập "ngoại lệ lịch sử": chỉ co lại khi bài được di trú, không bao giờ thêm.
  slug-redirect-registry.csv   các bài ĐÃ di trú (do migrate-slug-urls.py ghi); mỗi dòng sinh đúng một trang chuyển hướng.
  redirects/slug-d/<ID>.html   trang chuyển hướng nguồn (front matter, không thân); tệp phải KHỚP BYTE với `stub_source()`.

validate.py (`slug_policy`), check-slug-redirects.py (trên _site) và test_slug_policy.py đều dùng module này.
"""
import csv
import hashlib
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BASELINE_REL = 'reports/factory/seo-master/slug-d-baseline.csv'
REGISTRY_REL = 'reports/factory/seo-master/slug-redirect-registry.csv'
RATCHET_REL = 'reports/factory/seo-master/slug-stub-link-ratchet.json'
BASELINE_SHA256 = '6a91c1c7e18ad2b6c0a85d309ae9939cc91c06e54106bf22f46280194222197c'   # đóng băng: đổi = đổi mã + review
STUB_DIR = 'redirects/slug-d'
STUB_LAYOUT = 'redirect-stub'
REGISTRY_COLUMNS = ['article_id', 'title', 'old_url', 'new_url', 'old_slug', 'new_slug', 'old_output_path',
                    'new_output_path', 'status', 'batch_id', 'migrated_at']
MIGRATED = 'MIGRATED'
AID_RE = re.compile(r'^BLG-\d{5,}\Z')
SITE_URL = 'https://blog.thuexemaynguyentu.com'


def _p(root, rel):
    return os.path.join(root or ROOT, rel)


def read_csv_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def baseline_sha256(root=None):
    with open(_p(root, BASELINE_REL), 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_baseline(root=None):
    """{article_id: dòng} của danh sách đóng băng."""
    return {r['article_id']: r for r in read_csv_rows(_p(root, BASELINE_REL))}


def load_registry(root=None):
    return read_csv_rows(_p(root, REGISTRY_REL))


def registry_text(rows):
    """CSV registry tất định: sắp theo article_id, LF, cột cố định."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=REGISTRY_COLUMNS, lineterminator='\n')
    w.writeheader()
    for r in sorted(rows, key=lambda x: x['article_id']):
        w.writerow({k: r.get(k, '') for k in REGISTRY_COLUMNS})
    return buf.getvalue()


def migrated_ids(root=None):
    return {r['article_id'] for r in load_registry(root) if r.get('status') == MIGRATED}


def pending_ids(root=None):
    """Bài còn lại trong danh sách đóng băng chưa được di trú: được phép giữ slug cũ (thiếu d)."""
    return set(load_baseline(root)) - migrated_ids(root)


def stub_relpath(aid):
    if not AID_RE.match(aid or ''):
        raise ValueError('article_id sai dạng: %r' % (aid,))
    return '%s/%s.html' % (STUB_DIR, aid)


def stub_source(entry):
    """Nội dung TỆP NGUỒN của trang chuyển hướng (Jekyll dựng HTML bằng _layouts/redirect-stub.html)."""
    for k in ('article_id', 'old_url', 'new_url', 'title'):
        if not entry.get(k):
            raise ValueError('registry thiếu %s' % k)
    return ('---\n'
            'layout: %s\n'
            'permalink: %s\n'
            'redirect_to: %s\n'
            'redirect_title: %s\n'
            'article_id: %s\n'
            'sitemap: false\n'
            '---\n') % (STUB_LAYOUT, entry['old_url'], entry['new_url'],
                        json.dumps(entry['title'], ensure_ascii=False), entry['article_id'])


def expected_stub_files(root=None):
    """{đường dẫn tương đối: nội dung} cho mọi dòng MIGRATED của registry."""
    return {stub_relpath(r['article_id']): stub_source(r)
            for r in load_registry(root) if r.get('status') == MIGRATED}


def actual_stub_files(root=None):
    d = _p(root, STUB_DIR)
    out = {}
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if os.path.isfile(os.path.join(d, fn)):
                with open(os.path.join(d, fn), encoding='utf-8') as f:
                    out['%s/%s' % (STUB_DIR, fn)] = f.read()
    return out


def has_migration_provenance(ev, new_url):
    """Evidence mang dấu vết di trú permalink đúng URL mới: ở khối `revision` hiện tại HOẶC trong chuỗi `revision.history`
    (các công cụ chính thức sau đó — links-apply, revise-published — đẩy khối cũ xuống history, không xóa)."""
    rv = ev.get('revision') or {}
    chain = [rv] + [h for h in (rv.get('history') or []) if isinstance(h, dict)]
    return any(x.get('kind') == 'permalink-migration' and x.get('new_url') == new_url for x in chain)


def source_errors(root=None, matrix_rows=None, evidence=True):
    """Kiểm tra NGUỒN (không cần build): registry <-> matrix <-> bài <-> evidence <-> tệp chuyển hướng.
    Trả danh sách lỗi (rỗng = sạch). Dùng bởi validate.py và test."""
    errs = []
    root = root or ROOT
    if baseline_sha256(root) != BASELINE_SHA256:
        errs.append('slug-d-baseline.csv bị sửa (sha256 khác bản đóng băng) — danh sách ngoại lệ lịch sử là bất biến')
    base = load_baseline(root)
    reg = load_registry(root)
    seen_old, seen_new, ids = set(), set(), set()
    if matrix_rows is None:
        matrix_rows = read_csv_rows(_p(root, 'data/content-matrix.csv'))
    by_id = {r['id']: r for r in matrix_rows}
    urls_in_matrix = {}
    for r in matrix_rows:
        for k in ('expected_url', 'canonical_url'):
            urls_in_matrix.setdefault(r[k], set()).add(r['id'])
    for r in reg:
        aid = r.get('article_id', '')
        if r.get('status') != MIGRATED:
            errs.append('registry %s: status %r != %s' % (aid, r.get('status'), MIGRATED))
            continue
        if aid in ids:
            errs.append('registry trùng article_id %s' % aid)
        ids.add(aid)
        if aid not in base:
            errs.append('registry %s không thuộc danh sách đóng băng slug-d-baseline.csv' % aid)
        for key, seen in (('old_url', seen_old), ('new_url', seen_new)):
            if r[key] in seen:
                errs.append('registry trùng %s %s' % (key, r[key]))
            seen.add(r[key])
        mrow = by_id.get(aid)
        if mrow is None or mrow['status'] != 'PUBLISHED':
            errs.append('registry %s không phải hàng PUBLISHED trong matrix' % aid)
            continue
        want = {'slug': r['new_slug'], 'expected_url': r['new_url'], 'canonical_url': r['new_url'],
                'output_path': r['new_output_path']}
        for k, v in want.items():
            if mrow[k] != v:
                errs.append('registry %s: matrix %s = %r, registry nói %r' % (aid, k, mrow[k], v))
        if r['old_url'] == r['new_url'] or r['old_slug'] == r['new_slug']:
            errs.append('registry %s: OLD == NEW' % aid)
        owners = urls_in_matrix.get(r['old_url'], set())
        if owners:
            errs.append('registry %s: URL cũ %s vẫn là URL của hàng matrix %s' % (aid, r['old_url'], sorted(owners)))
        post = _p(root, r['new_output_path'])
        if not os.path.isfile(post):
            errs.append('registry %s: thiếu bài %s' % (aid, r['new_output_path']))
        else:
            with open(post, encoding='utf-8') as f:
                head = f.read(3000)
            pm = re.search(r'^permalink:\s*(\S+)\s*$', head, re.M)
            if not pm or pm.group(1) != r['new_url']:
                errs.append('registry %s: permalink trong bài (%s) != new_url (%s)'
                            % (aid, pm.group(1) if pm else None, r['new_url']))
        if os.path.exists(_p(root, r['old_output_path'])):
            errs.append('registry %s: tệp bài cũ %s còn tồn tại' % (aid, r['old_output_path']))
        if evidence:
            evp = _p(root, 'data/qa/%s.json' % aid)
            if not os.path.isfile(evp):
                errs.append('registry %s: thiếu evidence QA' % aid)
            else:
                with open(evp, encoding='utf-8') as f:
                    ev = json.load(f)
                if ev.get('source_path') != r['new_output_path']:
                    errs.append('registry %s: evidence source_path %r != %r'
                                % (aid, ev.get('source_path'), r['new_output_path']))
                if os.path.isfile(post):
                    with open(post, 'rb') as f:
                        if hashlib.sha256(f.read()).hexdigest() != ev.get('content_sha256'):
                            errs.append('registry %s: evidence content_sha256 không khớp bài' % aid)
                if not has_migration_provenance(ev, r['new_url']):
                    errs.append('registry %s: evidence thiếu provenance permalink-migration đúng URL' % aid)
    want_files = expected_stub_files(root)
    have_files = actual_stub_files(root)
    for rel in sorted(set(want_files) - set(have_files)):
        errs.append('thiếu trang chuyển hướng %s' % rel)
    for rel in sorted(set(have_files) - set(want_files)):
        errs.append('trang chuyển hướng %s không có trong registry (lạ)' % rel)
    for rel in sorted(set(want_files) & set(have_files)):
        if want_files[rel] != have_files[rel]:
            errs.append('trang chuyển hướng %s không khớp registry (phải sinh bằng công cụ, không sửa tay)' % rel)
    # không chuỗi/vòng: URL MỚI không được là URL CŨ của mục khác
    for u in sorted(seen_new & seen_old):
        errs.append('chuỗi chuyển hướng: %s vừa là OLD vừa là NEW' % u)
    return errs


def policy_errors(matrix_rows, root=None):
    """Chính sách slug cho mọi hàng factory (source `planned:`); legacy (slug theo tên tệp) không thuộc phạm vi.
    Ngoại lệ DUY NHẤT: bài còn trong danh sách đóng băng chưa di trú, và chỉ khi slug đúng bằng slug lỗi cũ
    (đ bị xóa) — không dùng ngoại lệ để che lỗi khác."""
    import slugkit
    errs = []
    pending = pending_ids(root)
    seen = {}
    for r in matrix_rows:
        if not r.get('source', '').startswith('planned:'):
            continue
        aid, slug, title = r['id'], r.get('slug', ''), r.get('title', '')
        if not slugkit.is_valid_slug(slug):
            errs.append('slug %s: %r không hợp lệ (chỉ a-z0-9 và gạch ngang đơn, <= %d ký tự)'
                        % (aid, slug, slugkit.MAX_SLUG_LEN))
            continue
        want = slugkit.slugify(title)
        if aid in pending:
            if slug != slugkit.slugify_legacy_without_d(title):
                errs.append('slug %s: ngoại lệ lịch sử nhưng slug %r != slug lỗi cũ của tiêu đề' % (aid, slug))
        elif slug != want:
            errs.append('slug %s: %r != slugify(title) %r — mọi slug phải do slugkit.slugify sinh ra' % (aid, slug, want))
        for k in ('expected_url', 'canonical_url'):
            u = r.get(k, '')
            if not slugkit.is_factory_url(u):
                errs.append('URL %s %s: %r không đúng chính sách ASCII/hình dạng' % (aid, k, u))
            elif not u.endswith('-' + slug + '/') and not u.endswith('/' + slug + '/'):
                errs.append('URL %s %s: %r không kết thúc bằng slug %r' % (aid, k, u, slug))
        if not re.match(r'^_posts/(?:\{date\}|\d{4}-\d{2}-\d{2})-%s\.md\Z' % re.escape(slug), r.get('output_path', '')):
            errs.append('output_path %s: %r không khớp slug %r' % (aid, r.get('output_path'), slug))
        if slug in seen:
            errs.append('slug trùng giữa %s và %s: %s' % (seen[slug], aid, slug))
        seen[slug] = aid
    return errs
