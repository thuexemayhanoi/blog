#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FACTORY OPERATOR — tay deterministic cho writer ngoài (external AI).

Mô hình (docs/PROC-PUBLISH.md):
  EXTERNAL AI (writer/coordinator, chỉ cần GitHub read/write)
    -> data/factory/operator-command.json (whitelist op)
    -> GitHub Actions (checkout + Python + Node + tooling chuẩn)
    -> scripts/factory/factory-operator.py (file này)

File này KHÔNG chứa AI, KHÔNG viết prose bài, KHÔNG bịa số liệu.
Mọi thao tác là deterministic trên engine chuẩn của /blog:
  - writer lock O_EXCL + ownership token (scripts/factory/publish-gate.py)
  - transaction + checkpoint chuẩn
  - publish-gate.py là cơ chế promote DUY NHẤT
  - refill-queue.py là refill DUY NHẤT

Ops whitelist:
  status                                  — in trạng thái (read-only)
  prepare-next [--count N]                — claim N hàng PLANNED (mặc định 5, tối đa 10)
  qa [--ids ID1,ID2]                      — QA deterministic cho hàng WRITING/QA/REPAIR
  publish --ids ID1,ID2                   — promote hàng PASS qua publish-gate.py
  recover                                — phục hồi transaction treo theo RECOVERY.md
  requeue --ids ID1                       — REPAIR/FAIL -> WRITING (tôn trọng budget)
  verify                                 — validate + capacity-audit + queue + tests
  refill                                 — chỉ khi dưới ngưỡng, chạy refill-queue.py
  reports                                — sinh reports/factory/*.md chuẩn

Thoát: 0 = thành công; 1 = từ chối an toàn (không mutate); 2 = lỗi dữ liệu.
"""
import argparse
import csv
import datetime
import glob
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

MATRIX = 'data/content-matrix.csv'
QA_DIR = 'data/qa'
ROWS_DIR = 'reports/factory/rows'
TXN = 'data/state/transaction.json'
CP = 'data/state/checkpoint.json'
LOCK = 'data/state/writer-lock.json'
LOCK_FILE = 'data/state/writer-lock.active'

MAX_CHUNK = 10
DEFAULT_CHUNK = 5
REPAIR_BUDGET = 3
QUALITY_MIN = 90
SEO_MIN = 90

# ---------------------------------------------------------------- engine load

_spec = importlib.util.spec_from_file_location(
    'publish_gate', os.path.join(ROOT, 'scripts/factory/publish-gate.py'))
pg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pg)  # publish-gate tự os.chdir(ROOT)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%S+00:00')


def today():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')


def read_json(path, default=None):
    if os.path.exists(path):
        return json.load(open(path, encoding='utf-8'))
    return default


def write_json_atomic(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_matrix():
    with open(MATRIX, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def save_matrix(rows):
    fields = list(rows[0].keys())
    with open(MATRIX, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def bail(msg, release=None):
    print('=== OPERATOR: TỪ CHỐI AN TOÀN ===')
    print(msg)
    if release is not None:
        try:
            release()
        except Exception:
            pass
    sys.exit(1)


# ---------------------------------------------------------------- lock helper

def lock_held_by_other():
    """True nếu sentinel tồn tại hoặc metadata locked=true mà không phải do
    tiến trình này. KHÔNG bao giờ force-unlock ownership không rõ (RECOVERY.md)."""
    if os.path.exists(LOCK_FILE):
        meta = read_json(LOCK, {}) or {}
        return True, meta
    meta = read_json(LOCK, {}) or {}
    if meta.get('locked'):
        # sentinel không còn nhưng metadata mồ côi -> lock treo, cần recover
        return True, meta
    return False, meta


def with_lock(holder):
    """Acquire lock chuẩn (token UUID, O_EXCL). Trả về release()."""
    return pg.acquire_lock(holder)


# ---------------------------------------------------------------- preflight

def preflight(require_clean_txn=True):
    """Kiểm tra trước mọi op mutating. Trả về (txn, cp, rows)."""
    ok = subprocess.run([sys.executable, 'scripts/factory/validate.py'],
                        capture_output=True, text=True)
    if ok.returncode != 0:
        print(ok.stdout[-2000:])
        bail('validate.py FAIL — không được mutate khi engine lệch.')

    txn = read_json(TXN, {'active': False, 'pending': None, 'history': []})
    if require_clean_txn and txn.get('active'):
        bail('transaction đang active (%s) — chạy op recover trước, '
             'KHÔNG nhận việc mới khi còn transaction treo.' % txn.get('pending'))

    held, meta = lock_held_by_other()
    if held:
        bail('writer-lock đang được giữ (holder=%s, token=%s) — từ chối; '
             'không force-unlock ownership không rõ (docs/RECOVERY.md).'
             % (meta.get('holder'), meta.get('token')))

    cp = read_json(CP)
    rows = load_matrix()
    return txn, cp, rows


def update_checkpoint(cp, rows, extra=None):
    counts = cp.setdefault('counts', {})
    for st in ('planned', 'writing', 'qa', 'pass', 'published',
               'repair', 'blocked', 'fail'):
        counts[st] = sum(1 for r in rows if r['status'] == st.upper())
    cp['updated_at'] = now_iso()
    if extra:
        cp.update(extra)
    write_json_atomic(CP, cp)


# ---------------------------------------------------------------- research class

def research_class(row, tax):
    if row['source_required'] == 'true' or row['legal_risk'] == 'high':
        return 'C'
    if 'PHAP' in row['parent_id'].upper():
        return 'C'
    if row['parent_hub'] in ('du-lich', 'cung-duong') or \
            row['group'] in ('DU-LICH', 'CUNG-DUONG') or \
            (row.get('location_scope') or ''):
        return 'B'
    return 'A'


# ---------------------------------------------------------------- manifests

def related_published(rows, row):
    out = []
    for r in rows:
        if r['id'] == row['id']:
            continue
        if r['status'] not in ('PUBLISHED', 'EXISTING'):
            continue
        if r['child_id'] == row['child_id'] or r['parent_id'] == row['parent_id']:
            out.append({'id': r['id'], 'title': r['title'],
                        'url': r['expected_url']})
    return out[:8]


def export_manifest(row, tax, biz, rows, draft_date):
    parents = {p['parent_id']: p for p in tax['parents']}
    children = {c['child_id']: c for c in tax['children']}
    p, c = parents[row['parent_id']], children[row['child_id']]
    date_url = '%s/%s/%s' % (draft_date[:4], draft_date[5:7], draft_date[8:])
    slug = row['output_path'][len('_posts/{date}-'):-3] \
        if row['output_path'].startswith('_posts/{date}-') else row['slug']
    manifest = {
        'article_id': row['id'],
        'status': row['status'],
        'title': row['title'],
        'intent': row['intent'],
        'primary_keyword': row['primary_keyword'],
        'secondary_keywords': row['secondary_keywords'].split('; ')
        if row['secondary_keywords'] else [],
        'group': row['group'],
        'taxonomy': {
            'parent_id': p['parent_id'], 'parent_hub': p['title'],
            'parent_hub_url': p['hub_url'],
            'child_id': c['child_id'], 'child_hub': c['title'],
            'child_hub_url': c['hub_url'],
        },
        'expected_url': row['expected_url'].replace('{date}', date_url),
        'output_path': row['output_path'],
        'draft_path': '_drafts/%s-%s.md' % (draft_date, slug),
        'canonical_url': row['canonical_url'].replace('{date}', date_url),
        'internal_links_matrix': row['internal_links'].split('; ')
        if row['internal_links'] else [],
        'commercial_intent': row['commercial_intent'],
        'cannibalization_key': row['cannibalization_key'],
        'word_target': int(row['word_target'] or 1200),
        'business_facts': {
            'source': 'data/business-facts.json',
            'approved_pricing': biz['approved_pricing'],
            'verified_facts': biz['verified_facts'],
            'forbidden_claims': biz['forbidden_claims'],
        },
        'source_required': row['source_required'] == 'true',
        'legal_risk': row['legal_risk'],
        'research_class': research_class(row, tax),
        'internal_link_candidates': related_published(rows, row),
        'qa_thresholds': {
            'quality_min': QUALITY_MIN, 'seo_min': SEO_MIN,
            'business_fact': 'PASS',
            'legal': 'PASS' if row['source_required'] == 'true'
            or row['legal_risk'] == 'high' else 'NOT_REQUIRED',
        },
        'matrix_row_sha256': pg.matrix_row_sha256(row),
        'notes': 'Writer ngoài viết draft đúng draft_path, tuân theo '
                 'docs/ARTICLE-RULES.md, docs/SOURCE-RESEARCH.md, '
                 'docs/INTERNAL-LINKING.md, docs/QUALITY-RUBRIC.md. '
                 'QA op chấm deterministic; publish chỉ qua publish-gate.py.',
    }
    os.makedirs(ROWS_DIR, exist_ok=True)
    path = os.path.join(ROWS_DIR, row['id'] + '.json')
    write_json_atomic(path, manifest)
    return path


# ---------------------------------------------------------------- QA scorer

APPROVED_AMOUNTS = set()


def build_amount_whitelist(biz):
    for _name, rates in biz['approved_pricing'].items():
        if not isinstance(rates, dict):
            continue
        for period in ('day', 'week', 'month'):
            v = rates.get(period)
            if isinstance(v, (int, float)):
                APPROVED_AMOUNTS.add(int(v))
            elif isinstance(v, str) and '-' in v:
                try:
                    lo, hi = [int(x) for x in v.split('-')]
                    for n in range(lo, hi + 1, 50000):
                        APPROVED_AMOUNTS.add(n)
                except ValueError:
                    pass
    # thêm số 0 và các mốc phạm vi lề cho an toàn hiển thị
    APPROVED_AMOUNTS.add(0)


FORBIDDEN_RE = [re.compile(p) for p in [
    r'khuyễn?\s?mãi|khuyến\s?mãi|khuyến\s?mại|giảm\s?giá',
    r'24/7|24/24',
    r'\b\d+\s*năm kinh nghiệm\b',
    r'cam kết hoàn tiền|bảo hành',
    r'thứ hạng|giải thưởng|top\s?\d',
    r'\d+\s*(khách|lượt)\s*(đã|đã từng)?\s*(phục vụ|thuê)',
    r'phí giao xe[^.]*\d',
    r'miễn phí giao',
]]

GOV_SOURCE_RE = re.compile(
    r'https?://[^\s\)]*'
    r'(chinhphu\.vn|moda\.gov\.vn|gov\.vn|csgt\.vn|luatvietnam\.vn)', re.I)
LEGAL_DISCLAIMER = 'có thể thay đổi'
HANOI_MARKERS = [
    'Hà Nội', 'Long Biên', 'Bồ Đề', 'Nguyễn Văn Cừ', 'Hoàn Kiếm',
    'Hồ Gươm', 'Ba Đình', 'Cầu Giấy', 'Tây Hồ', 'Hà Đông', 'Gia Lâm',
    'Văn Miếu', 'Đông Anh', 'Sóc Sơn', 'Thanh Xuân', 'Hai Bà Trưng',
    'Hoàng Mai', 'Nam Từ Liêm', 'Bắc Từ Liêm', 'Mê Linh', 'Phú Xuyên',
    'Thường Tín', 'Đan Phượng', 'Chương Mỹ', 'Mỹ Đức',
]



# ---------------------------------------------------- canonical route truth
# Base URL của site (GitHub Pages Jekyll): mọi liên kết nội bộ công khai
# PHẢI bắt đầu bằng /blog. Route thật sinh deterministic từ repository:
# frontmatter permalink của mọi trang + URL Jekyll của bài legacy.
# KHÔNG gọi network — route được kiểm against cây nguồn.

def _site_baseurl():
    cfg = open(os.path.join(ROOT, '_config.yml'), encoding='utf-8').read()
    m = re.search(r'^baseurl:\s*["\']?([^"\'\s#]+)', cfg, re.M)
    if not m or not m.group(1).startswith('/'):
        raise SystemExit('QA: không đọc được baseurl /blog từ _config.yml')
    return m.group(1).rstrip('/')


BASEURL = None
_ROUTES = None


def canonical_routes():
    """Tập route công khai dạng baseurl-đầy-đủ (/blog/...) từ repo truth."""
    global BASEURL, _ROUTES
    if _ROUTES is not None:
        return _ROUTES
    BASEURL = _site_baseurl()
    routes = set()
    excluded = {'scripts', 'assets', 'data', 'reports', 'docs', 'en',
                '_queue', '_drafts', 'gemfiles', 'node_modules',
                'vendor', '.git', '.jekyll-cache', '.sass-cache',
                '__pycache__'}
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in excluded]
        for fn in files:
            if not fn.endswith(('.md', '.html')):
                continue
            path = os.path.join(root, fn)
            try:
                text = open(path, encoding='utf-8').read()[:2500]
            except (OSError, UnicodeDecodeError):
                continue
            pm = re.search(r'^permalink:\s*(/\S+)', text, re.M)
            if pm:
                routes.add(BASEURL + pm.group(1))
    # bài legacy _posts không có permalink: URL do Jekyll tính
    # /blog/<category>/<Y>/<M>/<D>/<slug>/ (kèm biến thể lệch ngày UTC
    # vì Jekyll chuẩn hoá timezone — thêm cả hai để không false FAIL).
    posts_dir = os.path.join(ROOT, '_posts')
    for fn in sorted(os.listdir(posts_dir)):
        head = open(os.path.join(posts_dir, fn), encoding='utf-8').read()[:2500]
        if re.search(r'^permalink:', head, re.M):
            continue
        cm = re.search(r'^categories:\s*\[[^\]]*\]', head, re.M)
        dm = re.search(r'^date:\s*(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})'
                       r'(?::(\d{2}))?\s*([+-]\d{2})(\d{2})?', head, re.M)
        if not (cm and dm):
            continue
        cat = re.sub(r'^categories:\s*\[\s*|\s*\]\s*$', '', cm.group(0)).strip()
        y, mo, d = dm.group(1), dm.group(2), dm.group(3)
        slug = fn[11:-3]
        base = '%s/%s/' % (BASEURL, cat)
        routes.add('%s%s/%s/%s/%s/' % (base, y, mo, d, slug))
        # biến thể UTC (+07:00 phổ biến của site này -> ngày trừ 1)
        try:
            import datetime as _dt
            off = int(dm.group(7))
            t = _dt.datetime(int(y), int(mo), int(d)) - _dt.timedelta(hours=off)
            routes.add('%s%04d/%02d/%02d/%s/' % (base, t.year, t.month, t.day, slug))
        except Exception:
            pass
    _ROUTES = routes
    return routes


def link_route_ok(link):
    """Liên kết nội bộ chỉ PASS khi (1) có đủ baseurl /blog và
    (2) trỏ tới route thật trong cây nguồn. Anchor được tách trước
    khi đối chiếu; liên kết ngoài/anchor thuần không thuộc site."""
    link = (link or '').strip()
    if (not link or link.startswith('#')
            or link.startswith(('http://', 'https://', 'mailto:', 'tel:'))):
        return True
    if BASEURL is None:
        canonical_routes()   # khởi tạo BASEURL + route truth lần đầu
    if not link.startswith(BASEURL + '/'):
        return False
    route = link.split('#', 1)[0]
    if not route.endswith('/'):
        route += '/'
    return route in canonical_routes()

def norm_title(t):
    return re.sub(r'[^\w\sàáảãạăằắẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]',
                 '', (t or '').lower()).strip()


def find_draft(row):
    slug = row['output_path']
    if slug.startswith('_posts/{date}-'):
        slug = slug[len('_posts/{date}-'):-3]
    else:
        m = re.match(r'_posts/\d{4}-\d{2}-\d{2}-(.+)\.md$', slug)
        if not m:
            return None
        slug = m.group(1)
    hits = sorted(glob.glob('_drafts/*-%s.md' % slug))
    return (hits[0], slug) if hits else (None, slug)


def parse_frontmatter(text):
    fm = re.match(r'^---\n(.*?)\n---', text, re.S)
    if not fm:
        return None, ''
    front = {}
    for line in fm.group(1).splitlines():
        m = re.match(r'([a-z_]+):\s*(.*)$', line)
        if m:
            front[m.group(1)] = m.group(2).strip().strip('"')
    body = text[fm.end():]
    return front, body


def vnd_amounts(body):
    return set(int(m.replace('.', '')) for m in
               re.findall(r'\b\d{1,3}(?:\.\d{3})+\b', body))


def internal_links_in(body):
    # cho phép neo # (anchor): matrix có liên kết bắt buộc dạng
    # /bang-gia/#tinh-gia — regex cũ loại '#' khiến QA không bao giờ thấy
    # liên kết này, dù trang đích tồn tại và hợp lệ.
    return re.findall(r'\]\((/[^)\s]+)\)', body)


def qa_check_one(row, rows, biz, tax):
    """Trả về dict bằng chứng QA deterministic cho một hàng.
    Không bao giờ bịa điểm: mỗi tiêu chí chấm bằng kiểm tra đo được."""
    aid = row['id']
    ev = {
        'article_id': aid,
        'title': row['title'],
        'scored_at': now_iso(),
        'scorer': 'operator-qa-deterministic-v1',
        'checks': {},
    }
    draft, slug = find_draft(row)
    if draft is None:
        ev.update({'result': 'NO_DRAFT',
                   'message': 'không tìm thấy draft _drafts/*-%s.md' % slug})
        return ev
    text = open(draft, encoding='utf-8').read()
    front, body = parse_frontmatter(text)
    checks = ev['checks']

    # ---- cấu trúc draft
    checks['frontmatter_fields'] = all(
        k in front for k in ('title', 'date', 'description', 'permalink',
                             'article_id', 'parent_id', 'child_id')) \
        if front else False
    checks['draft_date'] = bool(front and re.match(
        r'\d{4}-\d{2}-\d{2}', front.get('date', '')) and
        os.path.basename(draft).startswith(front['date'][:10]))
    checks['slug_match'] = os.path.basename(draft) == '%s-%s.md' % (
        front['date'][:10], slug) if front else False
    d = front.get('date', '')[:10] if front else ''
    date_url = '%s/%s/%s' % (d[:4], d[5:7], d[8:]) if d else ''
    # permalink trong file là đường dẫn gốc-tương-đối (không tiền tố /blog,
    # baseurl thêm khi render); canonical_url/expected_url là URL công khai.
    expected_permalink = re.sub(r'^/blog', '',
                               row['canonical_url'].replace('{date}', date_url))
    checks['permalink_canonical'] = front and front.get('permalink') == \
        expected_permalink

    # ---- words
    words = body.split()
    target = int(row['word_target'] or 1200)
    checks['word_count'] = abs(len(words) - target) <= 0.15 * target
    ev['word_count'] = len(words)
    ev['word_target'] = target

    # ---- SEO checks
    checks['title_match'] = front and norm_title(front.get('title', '')) == \
        norm_title(row['title'])
    desc = front.get('description', '') if front else ''
    checks['description_length'] = 140 <= len(desc) <= 160
    checks['description_keyword'] = (row['primary_keyword'] or '').lower() in desc.lower()
    h2s = re.findall(r'^##\s+(.+)$', body, re.M)
    h3s = re.findall(r'^###\s+(.+)$', body, re.M)
    checks['h2_min'] = len(h2s) >= 2
    checks['no_h1_in_body'] = not re.search(r'^#\s+\S', body, re.M)
    heading_text = ' '.join(h2s + h3s).lower()
    sec_kw = row['secondary_keywords'].lower()
    checks['headings_intent'] = (row['primary_keyword'].lower() in heading_text
                                or (sec_kw and sec_kw in heading_text)
                                or row['intent'].lower() in heading_text)

    links = internal_links_in(body)
    required = [l for l in (row['internal_links'].split('; ')
                            if row['internal_links'] else []) if l]
    checks['links_matrix_required'] = all(any(l.startswith(r) for l in links)
                                          for r in required)
    parents = {p['parent_id']: p for p in tax['parents']}
    children = {c['child_id']: c for c in tax['children']}
    # hub trong taxonomy là URL công khai dạng /blog/... — liên kết trong
    # bài PHẢI mang đúng baseurl, không strip /blog nữa (QA hardening:
    # prefix khớp kiểu cũ cho /thue-xe/... chạy 404 là lỗi thật).
    hub = parents[row['parent_id']]['hub_url']
    checks['links_parent_hub'] = any(l.startswith(hub) for l in links)
    checks['links_count'] = 3 <= len(links) <= 8
    # route thật từ repository truth — liên kết chỉ PASS khi có /blog
    # VÀ trỏ tới route tồn tại (không chấp nhận khớp prefix suông).
    checks['links_routes_valid'] = all(link_route_ok(l) for l in links)
    ev['bad_routes'] = sorted(set(l for l in links if not link_route_ok(l)))
    checks['no_hardcoded_blog'] = not re.search(r'\]\(.*\/blog\/blog', body) \
        and '/blog/blog/' not in body

    # ---- cannibalization
    norm = norm_title(row['title'])
    clash = [r['id'] for r in rows
             if r['id'] != aid and r['status'] in ('PUBLISHED', 'EXISTING', 'REVIEW')
             and (r['child_id'] == row['child_id'])
             and (norm_title(r['title']) == norm
                  or (row['primary_keyword'] and
                      r['primary_keyword'] == row['primary_keyword']))]
    checks['cannibalization'] = not clash
    ev['cannibalization_clash'] = clash

    # ---- quality proxies
    opening = ' '.join(body.split()[:60])
    checks['intent_opening'] = (row['primary_keyword'].lower() in opening.lower()
                                or row['intent'].lower() in opening.lower())
    checks['hanoi_example'] = any(m in body for m in HANOI_MARKERS)
    sents = [s.strip() for s in re.split(r'[.!?]\s', body) if len(s.strip()) > 40]
    dup = len(sents) != len(set(sents))
    paras = [p for p in body.split('\n\n') if p.strip()]
    checks['reads_naturally_proxy'] = (not dup
                                      and all(len(p.split()) <= 160 for p in paras))
    checks['no_placeholder'] = ('lorem' not in body.lower()
                               and 'MẪU NHẬP BÀI' not in body)

    # ---- business facts (PASS-FAIL, không cho điểm)
    amounts = vnd_amounts(body)
    bad = sorted(a for a in amounts if a not in APPROVED_AMOUNTS)
    checks['business_amounts'] = not bad
    ev['non_approved_amounts'] = bad
    forbidden = [p.pattern for p in FORBIDDEN_RE if p.search(body)]
    checks['forbidden_claims'] = not forbidden
    ev['forbidden_hits'] = forbidden
    phone = biz['verified_facts']['phone'].replace(' ', '')
    phone_hits = re.findall(r'0\d{9}', body.replace(' ', ''))
    checks['phone_ok'] = all(p == phone for p in phone_hits)

    # ---- legal
    src_req = row['source_required'] == 'true' or row['legal_risk'] == 'high'
    if src_req:
        checks['legal_source'] = bool(GOV_SOURCE_RE.search(body))
        checks['legal_disclaimer'] = LEGAL_DISCLAIMER in body
        legal = 'PASS' if (checks['legal_source'] and checks['legal_disclaimer']) \
            else 'FAIL'
    else:
        legal = 'NOT_REQUIRED'

    critical = not (checks['business_amounts'] and checks['forbidden_claims']
                    and checks['phone_ok'] and checks['no_placeholder']
                    and checks['links_routes_valid'])

    # ---- điểm theo trọng số QUALITY-RUBRIC.md
    q_crit = [('intent_opening', 25), ('hanoi_example', 25),
              ('reads_naturally_proxy', 20), ('business_amounts', 20),
              ('no_placeholder', 10)]
    s_crit = [('title_match', 20), ('description_length', 15),
              ('headings_intent', 20), ('links_count', 15),
              ('cannibalization', 20), ('permalink_canonical', 10)]
    quality = sum(w for k, w in q_crit if checks.get(k))
    seo = sum(w for k, w in s_crit if checks.get(k))
    # business_fact là cổng PASS-FAIL riêng; chỉ tính điểm khi cổng sạch
    business_fact = 'PASS' if (checks['business_amounts']
                               and checks['forbidden_claims']
                               and checks['phone_ok']) else 'FAIL'

    ev.update({
        'quality': quality,
        'seo': seo,
        'business_fact': business_fact,
        'legal': legal,
        'critical_failure': critical,
        'checks': checks,
        'source_path': draft,
        'content_sha256': hashlib.sha256(
            open(draft, 'rb').read()).hexdigest(),
        'matrix_row_sha256': pg.matrix_row_sha256(row),
    })
    ev['result'] = 'PASS' if (quality >= QUALITY_MIN and seo >= SEO_MIN
                              and business_fact == 'PASS'
                              and legal in ('PASS', 'NOT_REQUIRED')
                              and not critical) else 'REPAIR'
    return ev


def op_qa(args, biz, tax):
    txn, cp, rows = preflight()
    ids = [i.strip() for i in (args.ids or '').split(',') if i.strip()]
    if not ids:
        ids = [r['id'] for r in rows if r['status'] in ('WRITING', 'QA', 'REPAIR')]
    if not ids:
        print('qa: không có hàng nào cần chấm (WRITING/QA/REPAIR trống).')
        return 0
    holder = 'operator-qa-%s' % uuid.uuid4().hex[:8]
    release = with_lock(holder)
    try:
        by_id = {r['id']: r for r in rows}
        outcomes = {}
        for aid in ids:
            if aid not in by_id:
                print('qa: KHÔNG có %s trong matrix — bỏ qua' % aid)
                continue
            row = by_id[aid]
            if row['status'] in ('PLANNED', 'PUBLISHED', 'EXISTING',
                                 'REVIEW', 'BLOCKED'):
                print('qa: %s trạng thái %s được bảo vệ — không chấm'
                      % (aid, row['status']))
                continue
            ev = qa_check_one(row, rows, biz, tax)
            os.makedirs(QA_DIR, exist_ok=True)
            write_json_atomic(os.path.join(QA_DIR, aid + '.json'), ev)
            if ev.get('result') == 'NO_DRAFT':
                row['status'] = 'WRITING'
                row['notes'] = (row['notes'] + ' | ' if row['notes'] else '') + \
                    'QA %s: chưa có draft' % now_iso()
                outcomes[aid] = 'NO_DRAFT'
                print('qa %s: NO_DRAFT — giữ WRITING' % aid)
                continue
            if ev['result'] == 'PASS':
                row['status'] = 'PASS'
                outcomes[aid] = 'PASS'
                print('qa %s: PASS quality=%d seo=%d'
                      % (aid, ev['quality'], ev['seo']))
            else:
                repair_n = int(row['repair_count'] or 0)
                row['status'] = 'REPAIR'
                fails = [k for k, v in ev['checks'].items() if not v]
                row['notes'] = (row['notes'] + ' | ' if row['notes'] else '') + \
                    'QA %s FAIL: %s' % (now_iso(), ','.join(fails[:6]))
                outcomes[aid] = 'REPAIR'
                print('qa %s: REPAIR quality=%d seo=%d fails=%s'
                      % (aid, ev['quality'], ev['seo'], fails))
        save_matrix(rows)
        update_checkpoint(cp, rows)
        write_json_atomic(os.path.join('reports/factory', 'qa-outcome.json'),
                          {'run_at': now_iso(), 'op': 'qa',
                           'outcomes': outcomes})
        if run_reports_checked('qa') != 0:
            return 1
        if validate_or_stop('qa') != 0:
            return 1
        print('qa: xong %d hàng, kết quả: %s'
              % (len(outcomes), json.dumps(outcomes, ensure_ascii=False)))
        return 0
    finally:
        release()


# ---------------------------------------------------------------- ops

def run_reports():
    """Sinh lại reports/factory chuẩn từ dữ liệu thật (deterministic).
    Bắt buộc sau mọi op đổi state để reports committed không lệch CI
    (factory-validate đối chiếu stable fields). Kèm generate-matrix.py:
    script idempotent, sinh lại matrix-report.md khớp đếm trạng thái
    hiện tại (PLANNED/PASS/PUBLISHED) — không đụng dữ liệu hàng."""
    r = subprocess.run([sys.executable, 'scripts/factory/generate-reports.py'],
                       capture_output=True, text=True)
    print(r.stdout[-600:])
    if r.returncode != 0:
        print(r.stderr[-600:])
    m = subprocess.run([sys.executable, 'scripts/factory/generate-matrix.py'],
                       capture_output=True, text=True)
    print(m.stdout[-400:])
    if m.returncode != 0:
        print(m.stderr[-600:])
    # listing/hub tĩnh cũng là output deterministic của tooling chuẩn:
    # bài mới xuất bản đổi đếm/phân trang -> sinh lại kèm mọi op đổi state.
    l = subprocess.run([sys.executable,
                        'scripts/factory/generate-listing-pages.py'],
                       capture_output=True, text=True)
    print(l.stdout[-400:])
    if l.returncode != 0:
        print(l.stderr[-600:])
    return r.returncode or m.returncode or l.returncode


def run_reports_checked(ctx):
    """run_reports() BAT BUOC thanh cong sau moi op doi state — KHONG
    bao gio nuot ma tra ve. Neu FAIL: op phai DUNG (return 1), khong
    khai thanh cong, khong sang phase san xuat khac. State da doi tren
    dia nhung workflow dung truoc buoc commit -> khong bao gio commit
    state lech; lan chay sau resume tu repository truth."""
    rc = run_reports()
    if rc != 0:
        print('%s: run_reports FAIL (rc=%d) — DỪNG, KHÔNG khai thành '
              'công. Chạy reports/verify trước khi làm tiếp.' % (ctx, rc))
        return 1
    return 0


def validate_or_stop(ctx):
    """validate.py chuan sau khi op doi state — FAIL thi DUNG, KHÔNG
    rollback tay (docs/RECOVERY.md)."""
    v = subprocess.run([sys.executable, 'scripts/factory/validate.py'],
                       capture_output=True, text=True)
    print(v.stdout[-1500:])
    if v.returncode != 0:
        print('%s: validate.py FAIL sau khi đổi state — DỪNG, KHÔNG '
              'rollback tay; chạy recover/verify trước khi làm tiếp.' % ctx)
    return v.returncode


def op_status(args):
    cp = read_json(CP)
    txn = read_json(TXN)
    held, meta = lock_held_by_other()
    rows = load_matrix()
    counts = {}
    for r in rows:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    def _head():
        try:
            return subprocess.run(['git', 'rev-parse', 'HEAD'],
                                   capture_output=True, text=True,
                                   timeout=10).stdout.strip() or None
        except Exception:
            return None
    print(json.dumps({
        'head': _head(),
        'checkpoint': {'status': cp.get('status'),
                       'last_completed': cp.get('last_completed_article_id'),
                       'next_claimable': cp.get('next_claimable_id'),
                       'in_progress_chunk': cp.get('in_progress_chunk')},
        'transaction_active': txn.get('active'),
        'lock_held': held, 'lock_holder': meta.get('holder'),
        'matrix_counts': counts,
    }, ensure_ascii=False, indent=2))
    return 0


def op_prepare_next(args, biz, tax):
    txn, cp, rows = preflight()
    count = min(int(args.count or DEFAULT_CHUNK), MAX_CHUNK)
    if count < 1:
        bail('count phải >= 1')
    # hòa giải việc dở trước: không claim mới khi còn hàng đang làm
    unfinished = [r['id'] for r in rows
                  if r['status'] in ('WRITING', 'QA', 'REPAIR', 'PASS')]
    if unfinished:
        bail('còn %d hàng chưa xong (%s...) — hoàn tất/QA/publish '
             'trước khi claim mới (không bỏ qua việc dở để lấy throughput).'
             % (len(unfinished), ','.join(unfinished[:5])))
    next_id = cp.get('next_claimable_id')
    planned = [r for r in rows if r['status'] == 'PLANNED']
    if next_id:
        planned.sort(key=lambda r: (r['id'] != next_id, r['id']))
    chunk = planned[:count]
    if not chunk:
        bail('không còn hàng PLANNED để claim.')
    holder = 'operator-prepare-%s' % uuid.uuid4().hex[:8]
    release = with_lock(holder)
    try:
        d = today()
        for r in rows:
            if r['id'] in {c['id'] for c in chunk}:
                r['status'] = 'WRITING'
        save_matrix(rows)
        ids = [c['id'] for c in chunk]
        cp['in_progress_chunk'] = ids
        cp['last_run_id'] = 'operator-prepare-next'
        remaining = [r['id'] for r in rows if r['status'] == 'PLANNED']
        cp['next_claimable_id'] = remaining[0] if remaining else None
        update_checkpoint(cp, rows)
        for c in chunk:
            path = export_manifest(c, tax, biz, rows, d)
            print('manifest: %s' % path)
        if run_reports_checked('prepare-next') != 0:
            return 1
        if validate_or_stop('prepare-next') != 0:
            return 1
        print('prepare-next: claim %d hàng: %s' % (len(ids), ','.join(ids)))
        return 0
    finally:
        release()


def op_publish(args):
    if not args.ids:
        bail('publish yêu cầu --ids (chỉ promote hàng PASS do caller cung cấp)')
    ids = [i.strip() for i in args.ids.split(',') if i.strip()]
    txn, cp, rows = preflight()
    by_id = {r['id']: r for r in rows}
    for aid in ids:
        row = by_id.get(aid)
        if row is None:
            bail('publish: %s không có trong matrix' % aid)
        if row['status'] != 'PASS':
            bail('publish: %s trạng thái %s — gate chỉ nhận PASS. '
                 'Chạy qa lại, KHÔNG hạ ngưỡng.' % (aid, row['status']))
        draft, slug = find_draft(row)
        if draft is None:
            bail('publish: %s thiếu draft' % aid)
    # publish-gate tự acquire lock/transaction từng bài; KHÔNG giữ lock ở đây
    ok_ids = []
    for aid in ids:
        row = by_id[aid]
        draft, _slug = find_draft(row)
        r = subprocess.run([sys.executable,
                            'scripts/factory/publish-gate.py',
                            '--draft', draft, '--id', aid],
                           capture_output=True, text=True)
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        if r.returncode != 0:
            print('publish: %s FAIL — dừng, các bài còn lại KHÔNG promote, '
                  'KHÔNG nhận hàng mới. Resume: qa -> publish lại.' % aid)
            return 1
        ok_ids.append(aid)
    # sau promote: chốt checkpoint TRƯỚC (xóa in_progress_chunk) rồi mới
    # sinh reports — nếu không latest.md sẽ giữ chunk đã xong (stale).
    cp = read_json(CP)
    rows2 = load_matrix()
    still = [r['id'] for r in rows2
             if r['id'] in ok_ids and r['status'] != 'PUBLISHED']
    if still:
        print('publish: %s chưa PUBLISHED sau gate — dừng.' % still)
        return 1
    cp['in_progress_chunk'] = None
    update_checkpoint(cp, rows2)
    if run_reports_checked('publish') != 0:
        return 1
    if validate_or_stop('publish') != 0:
        return 1
    print('publish: PUBLISHED %s' % ','.join(ok_ids))
    return 0


def op_requeue(args):
    if not args.ids:
        bail('requeue yêu cầu --ids')
    ids = [i.strip() for i in args.ids.split(',') if i.strip()]
    txn, cp, rows = preflight()
    by_id = {r['id']: r for r in rows}
    holder = 'operator-requeue-%s' % uuid.uuid4().hex[:8]
    release = with_lock(holder)
    try:
        for aid in ids:
            row = by_id.get(aid)
            if row is None:
                print('requeue: không có %s — bỏ qua' % aid)
                continue
            if row['status'] not in ('REPAIR', 'FAIL'):
                print('requeue: %s trạng thái %s được bảo vệ — bỏ qua'
                      % (aid, row['status']))
                continue
            n = int(row['repair_count'] or 0)
            if n >= REPAIR_BUDGET:
                row['status'] = 'BLOCKED'
                row['notes'] = (row['notes'] + ' | ' if row['notes'] else '') + \
                    'requeue %s: hết budget repair (%d) — BLOCKED' % (now_iso(), n)
                print('requeue: %s hết budget (%d) — BLOCKED' % (aid, n))
            else:
                row['status'] = 'WRITING'
                row['repair_count'] = str(n + 1)
                print('requeue: %s -> WRITING (repair_count=%d)' % (aid, n + 1))
        save_matrix(rows)
        update_checkpoint(cp, rows)
        # requeue là state mutation: bat ky op doi state phai de lai
        # matrix + checkpoint + reports + listing/index da tai sinh va
        # validate — neu regeneration/validation FAIL thi dung an toan.
        if run_reports_checked('requeue') != 0:
            return 1
        return validate_or_stop('requeue')
    finally:
        release()


def op_recover(args):
    txn = read_json(TXN, {'active': False, 'history': []})
    held, meta = lock_held_by_other()
    if held:
        print('recover: writer-lock đang giữ (holder=%s, expires=%s). '
              'Ownership không rõ -> STOP theo docs/RECOVERY.md; '
              'KHÔNG force-unlock.' % (meta.get('holder'), meta.get('expires_at')))
        return 1
    if not txn.get('active'):
        print('recover: transaction sạch (active=false) — không có gì phục hồi.')
        return 0
    pend = txn.get('pending') or {}
    aid = pend.get('article_id') or (pend.get('step') or '').replace('promote ', '')
    dest = pend.get('destination')
    draft = pend.get('draft')
    entry = txn['history'][-1] if txn.get('history') else {}
    dest = dest or entry.get('destination')
    draft = draft or entry.get('source')
    if dest and os.path.exists(dest):
        # promote đã xảy ra vật lý -> hoàn tất đóng transaction
        rows = load_matrix()
        for r in rows:
            if r['id'] == aid and r['status'] != 'PUBLISHED':
                r['status'] = 'PUBLISHED'
        save_matrix(rows)
        cp = read_json(CP)
        update_checkpoint(cp, rows)
        txn['history'][-1] = dict(entry, result='RECOVERED_COMPLETED',
                                   finished_at=now_iso())
        txn['active'] = False
        txn['pending'] = None
        txn['updated_at'] = now_iso()
        write_json_atomic(TXN, txn)
        # state mutation (PUBLISHED + checkpoint) -> resync + validate
        if run_reports_checked('recover') != 0:
            return 1
        if validate_or_stop('recover') != 0:
            return 1
        print('recover: transaction hoàn tất (đích đã tồn tại): %s' % dest)
        return 0
    if draft and os.path.exists(draft):
        # chưa promote -> trả draft về _drafts/, đóng transaction
        if dest and os.path.exists(dest):
            shutil.move(dest, draft)
        rows = load_matrix()
        for r in rows:
            if r['id'] == aid and r['status'] in ('PASS', 'QA', 'PUBLISHED'):
                r['status'] = 'QA'
                r['notes'] = (r['notes'] + ' | ' if r['notes'] else '') + \
                    'recover %s: promote dở, trả về QA' % now_iso()
        save_matrix(rows)
        cp = read_json(CP)
        update_checkpoint(cp, rows)
        txn['history'][-1] = dict(entry, result='RECOVERED_ROLLED_BACK',
                                  finished_at=now_iso())
        txn['active'] = False
        txn['pending'] = None
        txn['updated_at'] = now_iso()
        write_json_atomic(TXN, txn)
        # state mutation (row ve QA + checkpoint) -> resync + validate
        if run_reports_checked('recover') != 0:
            return 1
        if validate_or_stop('recover') != 0:
            return 1
        print('recover: transaction rollback (chưa promote): %s' % draft)
        return 0
    print('recover: transaction active nhưng không suy luận được trạng thái '
          'vật lý — STOP, không mutate thêm. Kiểm tra tay theo docs/RECOVERY.md.')
    return 1


def op_verify(args):
    steps = [
        ['scripts/factory/validate.py'],
        ['scripts/factory/capacity-audit.py'],
        ['scripts/factory/tests/test_publish_gate.py'],
        ['scripts/factory/tests/test_refill_safety.py'],
        ['scripts/factory/tests/test_operator.py'],
        ['scripts/factory/tests/test_link_integrity.py'],
    ]
    failed = []
    for cmd in steps:
        r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True)
        print('$ python3 %s -> %d' % (' '.join(cmd), r.returncode))
        print(r.stdout[-800:])
        if r.returncode != 0:
            failed.append(' '.join(cmd))
    r = subprocess.run([sys.executable, 'scripts/factory/queue.py', '--stats'],
                       capture_output=True, text=True)
    print(r.stdout)
    if failed:
        print('verify: FAIL ở %s' % failed)
        return 1
    print('verify: PASS (validate + capacity-audit + queue + tests)')
    return 0


def op_refill(args):
    r = subprocess.run([sys.executable, 'scripts/factory/queue.py',
                         '--needs-refill'], capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print('refill: chưa đến ngưỡng — KHÔNG refill (lazy capacity).')
        return 0
    _txn, _cp, rows = preflight()
    holder = 'operator-refill-%s' % uuid.uuid4().hex[:8]
    release = with_lock(holder)
    try:
        rr = subprocess.run([sys.executable, 'scripts/factory/refill-queue.py'],
                            capture_output=True, text=True)
        print(rr.stdout[-2000:])
        if rr.returncode != 0:
            print('refill: refill-queue.py FAIL — dừng.')
            return 1
        # refill them hang PLANNED -> matrix-report/doi dem phai tai sinh
        if run_reports_checked('refill') != 0:
            return 1
        return validate_or_stop('refill')
    finally:
        release()


def op_reports(args):
    r = subprocess.run([sys.executable, 'scripts/factory/generate-reports.py'],
                       capture_output=True, text=True)
    print(r.stdout[-1500:])
    print(r.stderr[-500:], file=sys.stderr)
    return r.returncode


OPS = {
    'status': op_status,
    'prepare-next': op_prepare_next,
    'qa': op_qa,
    'publish': op_publish,
    'recover': op_recover,
    'requeue': op_requeue,
    'verify': op_verify,
    'refill': op_refill,
    'reports': op_reports,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('op', choices=sorted(OPS))
    ap.add_argument('--ids')
    ap.add_argument('--count', type=int)
    args = ap.parse_args()
    biz = read_json('data/business-facts.json', {})
    tax = read_json('data/content-taxonomy.json', {})
    build_amount_whitelist(biz)
    fn = OPS[args.op]
    if args.op == 'status':
        return fn(args)
    if args.op in ('verify', 'reports', 'recover'):
        return fn(args)
    # các op còn lại cần biz/tax
    if args.op in ('prepare-next', 'qa'):
        return fn(args, biz, tax)
    return fn(args)


if __name__ == '__main__':
    sys.exit(main())
