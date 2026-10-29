#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Registry + trang chuyển hướng cho di trú slug đ -> d (Issue #77). Module dùng chung, KHÔNG ghi gì khi import.

GitHub Pages không có HTTP 301 theo đường dẫn (bằng chứng runner: server GitHub.com, không lớp edge). Chủ repo đã chọn:
URL CŨ = trang HTTP 200 với `<meta http-equiv="refresh" content="0; url=MỚI">` + canonical MỚI, bị loại khỏi sitemap;
URL MỚI = bài thật. Báo cáo luôn gọi đúng tên "HTTP 200 + meta refresh", KHÔNG gọi là 301.

Quyết định chủ 2026-10-27 (sau khi di trú xong): URL cũ không cần giữ lịch sử. Dòng registry được chuyển MIGRATED -> RETIRED
(retire-slug-stubs.py, chỉ khi không còn liên kết nào trỏ URL cũ và URL mới đã được audit live xác nhận HTTP 200): trang chuyển hướng
bị gỡ, URL cũ trả 404 (đúng kỳ vọng), registry vẫn giữ ánh xạ cũ -> mới để chặn liên kết mới vào URL đã gỡ.

Ba nguồn sự thật (đều nằm trong repo):
  slug-d-baseline.csv          danh sách ĐÓNG BĂNG 1.410 bài đã xuất bản có slug thiếu chữ d (sha256 được ghim trong test);
                               đây là tập "ngoại lệ lịch sử": chỉ co lại khi bài được di trú, không bao giờ thêm.
  slug-redirect-registry.csv   các bài ĐÃ di trú (do migrate-slug-urls.py ghi); dòng MIGRATED sinh đúng một trang chuyển hướng,
                               dòng RETIRED không có trang nào (URL cũ đã gỡ).
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
RETIRED = 'RETIRED'            # URL cũ đã gỡ: không còn trang chuyển hướng, URL cũ trả 404; bài vẫn ở URL mới
STATUSES = (MIGRATED, RETIRED)
AID_RE = re.compile(r'^BLG-\d{5,}\Z')
# Thư mục/tệp gốc KHÔNG dựng thành trang site (khớp `exclude:` của _config.yml; redirects/ = chính các trang chuyển hướng;
# thư mục ẩn như .github): không quét liên kết trong đó — chỉ trang thật mới tạo liên kết 404.
SOURCE_SKIP_DIRS = {'_site', '.git', '.jekyll-cache', '.sass-cache', 'node_modules', 'vendor', 'docs', 'reports', 'scripts', 'data',
                    '_drafts', 'redirects', 'tests', 'bin', 'build_info', 'cache', 'en', 'gemfiles', '_queue'}
SOURCE_SKIP_ROOT_FILES = {'AGENTS.md', 'README.md', 'THEME_UPGRADE_MATRIX.md'}
SOURCE_EXT = ('.md', '.html', '.yml', '.yaml', '.json')
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
    """Bài đã chuyển sang URL mới (còn trang chuyển hướng hoặc URL cũ đã gỡ)."""
    return {r['article_id'] for r in load_registry(root) if r.get('status') in STATUSES}


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


def literal_union_regex(strings):
    """Regex khớp chuỗi DÀI NHẤT trong `strings` (khác rỗng) tại vị trí trái nhất — cùng kết quả với
    '|'.join(re.escape(s) for s in sorted(strings, key=len, reverse=True)), nhưng dựng dạng trie. sre thử từng nhánh
    của alternation phẳng tại MỌI vị trí (hàng nghìn URL x mọi ký tự của ~6.000 tệp = validate chậm vài giây); trie
    chỉ đi đúng một nhánh. Nhánh con đặt trước điểm kết thúc (`(?:...)?` tham lam) nên khớp dài nhất thắng."""
    trie = {}
    for s in strings:
        node = trie
        for ch in s:
            node = node.setdefault(ch, {})
        node[''] = {}                               # '' = có chuỗi kết thúc tại nút này (ký tự thật luôn dài 1)

    def build(node):
        head = []
        while '' not in node and len(node) == 1:         # chuỗi một nhánh: nối thẳng, chỉ đệ quy ở điểm rẽ/kết thúc
            (ch, node), = node.items()
            head.append(re.escape(ch))
        alts = [re.escape(ch) + build(child) for ch, child in sorted(node.items()) if ch]
        if not alts:
            return ''.join(head)
        body = alts[0] if len(alts) == 1 else '(?:%s)' % '|'.join(alts)
        return ''.join(head) + ('(?:%s)?' % body if '' in node else body)

    if not trie or '' in trie:
        raise ValueError('literal_union_regex cần tập chuỗi khác rỗng, không chứa chuỗi rỗng')
    try:
        return re.compile(build(trie))
    except RecursionError:                               # trie lồng quá sâu (chuỗi dài bất thường): alternation phẳng, cùng kết quả
        return re.compile('|'.join(re.escape(s) for s in sorted(strings, key=len, reverse=True)))


def source_link_hits(urls, root=None, include_drafts=False):
    """{tệp tương đối: số liên kết} trỏ tới `urls` trong NGUỒN site (bài, include, layout, trang, _data), không cần build.
    Mỗi lần xuất hiện của URL (có/không '/' cuối, đủ token) = một liên kết; bỏ qua SOURCE_SKIP_DIRS ở gốc repo.
    include_drafts=True quét thêm _drafts/ (draft đang xếp hàng sẽ thành bài: gỡ URL khi draft còn trỏ vào là tạo 404)."""
    root = root or ROOT
    skip = SOURCE_SKIP_DIRS - ({'_drafts'} if include_drafts else set())
    forms = set()
    for u in urls:
        forms.add(u)
        forms.add(u.rstrip('/'))
    forms.discard('')
    if not forms:
        return {}
    pat = literal_union_regex(forms)
    # Lọc nhanh trên BYTES khi mọi URL là ASCII (URL registry luôn ASCII): byte ASCII không bao giờ nằm trong một ký tự UTF-8
    # nhiều byte, nên tệp KHÔNG khớp bản bytes thì chắc chắn không khớp bản str — bỏ qua bước giải mã ~28.000 tệp mỗi lần
    # validate (phần lớn thời gian của mục slug_policy). Tệp có khớp vẫn giải mã và đếm đúng quy tắc token như cũ.
    try:
        bpat = re.compile(pat.pattern.encode('ascii')) if all(f.isascii() for f in forms) else None
    except (UnicodeEncodeError, re.error):
        bpat = None
    hits = {}
    for dp, dns, fns in os.walk(root):
        at_root = os.path.relpath(dp, root) == '.'
        if at_root:
            dns[:] = [d for d in dns if d not in skip and not d.startswith('.')]
        for fn in fns:
            if not fn.endswith(SOURCE_EXT) or (at_root and fn in SOURCE_SKIP_ROOT_FILES):
                continue
            path = os.path.join(dp, fn)
            try:
                with open(path, 'rb') as f:
                    raw = f.read()
            except OSError:
                continue
            if bpat is not None and not bpat.search(raw):
                continue
            text = raw.decode('utf-8', errors='replace')
            n = 0
            for m in pat.finditer(text):
                if m.group(0).endswith('/') or not re.match(r'[\w\-/]', text[m.end():m.end() + 1]):
                    n += 1
            if n:
                hits[os.path.relpath(path, root).replace(os.sep, '/')] = n
    return hits


RETIRE_BACKUP_DIR = 'reports/qa-audit/retire'


def retire_provenance(root=None):
    """{article_id: [đường dẫn sao lưu]} từ các sao lưu retire-slug-stubs.py (reports/qa-audit/retire/*.json): mỗi dòng RETIRED
    phải đi qua công cụ (chủ duyệt + bằng chứng live), không được gỡ tay. Trả cả dòng registry cũ để đối chiếu."""
    d = _p(root, RETIRE_BACKUP_DIR)
    out = {}
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if not fn.endswith('.json'):
            continue
        try:
            with open(os.path.join(d, fn), encoding='utf-8') as f:
                b = json.load(f)
        except (OSError, ValueError):
            continue
        if b.get('schema') != 'retire-backup/1' or not str(b.get('approval_ref', '')).strip() \
                or not str(b.get('live_ref', '')).strip():
            continue
        for aid, e in (b.get('entries') or {}).items():
            if isinstance(e, dict) and isinstance(e.get('registry_row'), dict):
                out.setdefault(aid, []).append(('%s/%s' % (RETIRE_BACKUP_DIR, fn), e['registry_row']))
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
        if r.get('status') not in STATUSES:
            errs.append('registry %s: status %r không thuộc %s' % (aid, r.get('status'), STATUSES))
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
    # dòng RETIRED phải có sao lưu retire-slug-stubs.py khớp (dòng cũ MIGRATED, cùng các cột) — không gỡ tay
    retired_rows = [r for r in reg if r.get('status') == RETIRED]
    prov = retire_provenance(root) if retired_rows else {}
    for r in retired_rows:
        want = {k: r.get(k, '') for k in REGISTRY_COLUMNS if k != 'status'}
        if not any(old.get('status') == MIGRATED and {k: old.get(k, '') for k in REGISTRY_COLUMNS if k != 'status'} == want
                   for _, old in prov.get(r['article_id'], [])):
            errs.append('registry %s: RETIRED nhưng không có sao lưu retire-slug-stubs.py khớp (%s) — không gỡ tay'
                        % (r['article_id'], RETIRE_BACKUP_DIR))
    # URL cũ đã gỡ trả 404: KHÔNG một liên kết nào trong nguồn site được trỏ vào (ngưỡng cứng 0, không ratchet)
    retired = [r['old_url'] for r in retired_rows]
    for rel, n in sorted(source_link_hits(retired, root).items()):
        errs.append('%s: %d liên kết tới URL cũ ĐÃ GỠ (RETIRED, 404) — trỏ thẳng URL mới' % (rel, n))
    return errs


# output_path = _posts/<{date}|YYYY-MM-DD>-<slug>.md; MỘT regex biên dịch sẵn (không dựng regex riêng cho từng hàng matrix)
OUTPUT_PATH_RE = re.compile(r'^_posts/(?:\{date\}|\d{4}-\d{2}-\d{2})-(.+)\.md\Z')


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
        om = OUTPUT_PATH_RE.match(r.get('output_path', ''))
        if not om or om.group(1) != slug:
            errs.append('output_path %s: %r không khớp slug %r' % (aid, r.get('output_path'), slug))
        if slug in seen:
            errs.append('slug trùng giữa %s và %s: %s' % (seen[slug], aid, slug))
        seen[slug] = aid
    return errs
