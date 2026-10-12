#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_faq.py — kiểm tra nguồn FAQ dùng chung `_data/faq/*.json` (READ-ONLY, chỉ stdlib).

  python3 scripts/faq/validate_faq.py [--root <repo>] [--json]

Mỗi vi phạm là ERROR (exit 1). Không có thư mục/file FAQ => OK (hạ tầng mặc định không làm gì).

Cấu trúc một file `_data/faq/<khoá>.json`:
  {"schema": true|false, "heading": "Câu hỏi thường gặp" (tuỳ chọn),
   "items": [{"q": "…?", "a": "…", "src": "body"|"page"}, …]}
  khoá = slug bài (src "body") hoặc front matter `faq_key:` của trang tĩnh/hub/topic (src "page").

Quy tắc:
  F1  JSON hợp lệ; khoá cấp 1 chỉ gồm schema/heading/items; schema là boolean.
  F2  2–8 mục; mỗi mục có đúng q/a/src; q kết thúc "?", 12–140 ký tự; a 30–700 ký tự; văn bản thuần
      (không HTML, không Liquid, không link/markdown); mỗi câu của a có >= 3 từ.
  F3  khoá phải có ĐÍCH: đúng 1 file `_posts/*-<khoá>.md` (src body) hoặc đúng 1 trang có `faq_key: <khoá>`
      (src page). File FAQ không đích ("mồ côi") là lỗi.
  F4  NGUYÊN VĂN: mọi câu trong `a` phải xuất hiện nguyên văn (bỏ dấu câu/hoa thường/markdown) trong nguồn của
      đích => FAQ KHÔNG thêm sự thật mới (cùng nguyên tắc rubric audit: không bịa số, không bịa chính sách).
  F5  Chủ đề BLOCKED của chủ xe (cọc, phí trả trễ, bảo hiểm, giữ giấy tờ, mũ bảo hiểm, hoàn tiền: xem
      reports/factory/policy-conflicts.md): câu nhắc tới chủ đề này chỉ được là lời dặn "xác nhận trực tiếp/liên hệ",
      TUYỆT ĐỐI không kèm con số. Cụm bị cấm trong data/business-facts.json (khuyến mại, 24/7, "hàng nghìn khách"…)
      và mọi số tiền không nằm trong bảng giá đã duyệt đều là lỗi.
  F6  Không trùng: câu hỏi chuẩn hoá trùng nhau (cả giữa các trang), gần trùng (Jaccard >= 0.8), hoặc câu trả lời
      dài trùng hệt giữa hai trang khác nhau => lỗi (tránh FAQ boilerplate/cannibalization).
"""
import argparse
import glob
import itertools
import json
import os
import re
import sys
import unicodedata

KEYS = {'schema', 'heading', 'items'}
ITEM_KEYS = {'q', 'a', 'src'}
SRC = {'body', 'page'}
MIN_ITEMS, MAX_ITEMS = 2, 8
Q_MIN, Q_MAX, A_MIN, A_MAX = 12, 140, 30, 700

SKIP_DIRS = {'_posts', '_drafts', '_site', '.git', 'reports', 'docs', 'data', 'scripts', '_queue', '_listing',
             'node_modules', 'assets', '_data', '_includes', '_layouts', 'vendor', '.jekyll-cache', 'en'}

BLOCKED_TOPIC = re.compile(
    r'(đặt cọc|tiền cọc|\bcọc\b|phí (?:trễ|trả trễ|trả muộn|quá giờ)|trả (?:xe )?(?:muộn|trễ)|quá giờ|bảo hiểm|'
    r'giữ (?:giấy tờ|cmnd|cccd|hộ chiếu|passport|bằng lái)|giấy tờ gốc|hoàn (?:tiền|cọc|trả tiền)|bồi thường)')
HEDGE = re.compile(r'(xác nhận (?:trực tiếp|với|trước|lại)|liên hệ|hỏi (?:trực tiếp|rõ|nguyễn tú|cửa hàng))')
FORBIDDEN = re.compile(
    r'(khuyến (?:mại|mãi)|giảm giá|ưu đãi|24/7|hỗ trợ 24|hàng (?:nghìn|ngàn|trăm) (?:khách|lượt|người)|'
    r'\d+\s*năm kinh nghiệm|uy tín nhất|rẻ nhất|số 1 (?:hà nội|việt nam|thị trường)|số một|hàng đầu|đứng đầu|\btop \d|giải thưởng|cam kết hoàn|bảo hành)')
AMOUNT = re.compile(r'(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*(triệu|tr\b|nghìn|ngàn|k\b|đ\b|vnd|vnđ|đồng)?')
UNIT = {'triệu': 1_000_000, 'tr': 1_000_000, 'nghìn': 1000, 'ngàn': 1000, 'k': 1000, 'đ': 1, 'vnd': 1, 'vnđ': 1, 'đồng': 1}


def nfc(s):
    return unicodedata.normalize('NFC', s)


def norm_match(s):
    """Chuẩn hoá để so khớp nguyên văn: NFC, hạ chữ, mọi ký tự không phải chữ/số -> khoảng trắng."""
    s = nfc(s).casefold()
    s = re.sub(r'[^\w]+|_', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def strip_front_matter(text):
    m = re.match(r'\A---\s*\n(.*?)\n---\s*\n?', text, re.S)
    return (m.group(1), text[m.end():]) if m else ('', text)


def plain_text(md):
    """Markdown/HTML/Liquid -> văn bản thuần (đủ để so khớp câu)."""
    s = re.sub(r'\{%.*?%\}|\{\{.*?\}\}', ' ', md, flags=re.S)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', s)
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s)
    s = re.sub(r'(?m)^\s*(?:#{1,6}\s+|>\s*|[-*+]\s+|\d+[.)]\s+)', '', s)
    s = re.sub(r'[*_`|]', ' ', s)
    return s


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def approved_amounts(root):
    """Mọi số trong approved_pricing của data/business-facts.json (kể cả khoảng 'a - b')."""
    out = set()
    p = os.path.join(root, 'data', 'business-facts.json')
    if not os.path.exists(p):
        return out

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            out.add(int(o))
        elif isinstance(o, str):
            for n in re.findall(r'\d{4,}', o):
                out.add(int(n))
    walk(load_json(p).get('approved_pricing', {}))
    return out


def find_targets(root):
    posts, dup_posts = {}, set()
    for f in sorted(glob.glob(os.path.join(root, '_posts', '*.md'))):
        m = re.match(r'\d{4}-\d{2}-\d{2}-(.+)\.md$', os.path.basename(f))
        if not m:
            continue
        slug = m.group(1)
        if slug in posts:
            dup_posts.add(slug)
        posts[slug] = f
    pages, dup_pages = {}, set()
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith('.')]
        for fn in fns:
            if not fn.endswith(('.md', '.html')):
                continue
            path = os.path.join(dp, fn)
            try:
                with open(path, encoding='utf-8') as fh:
                    head, _ = strip_front_matter(fh.read())
            except (OSError, UnicodeDecodeError):
                continue
            m = re.search(r'(?m)^faq_key:\s*["\']?([A-Za-z0-9][A-Za-z0-9_\-]*)["\']?\s*$', head)
            if m:
                if m.group(1) in pages:
                    dup_pages.add(m.group(1))
                pages[m.group(1)] = path
    return posts, dup_posts, pages, dup_pages


def split_sentences(a):
    return [x.strip() for x in re.split(r'(?<=[.!?…])\s+', a.strip()) if x.strip()]


def check_blocked(sentence, where, err, is_question=False):
    """Câu hỏi được NHẮC chủ đề BLOCKED (không kèm số); chỉ CÂU TRẢ LỜI mới phải là lời dặn xác nhận trực tiếp."""
    ns = nfc(sentence).casefold()
    if BLOCKED_TOPIC.search(ns):
        if re.search(r'\d', ns):
            err('%s: chủ đề BLOCKED (cọc/phí trễ/bảo hiểm/giữ giấy tờ/mũ/hoàn tiền) kèm con số: %r' % (where, sentence[:90]))
        elif not is_question and not HEDGE.search(ns):
            err('%s: chủ đề BLOCKED chỉ được nhắc dưới dạng "xác nhận trực tiếp/liên hệ": %r' % (where, sentence[:90]))
    if FORBIDDEN.search(ns):
        err('%s: cụm bị cấm trong business-facts (khuyến mại/24/7/cam kết…): %r' % (where, sentence[:90]))


def check_amounts(text, approved, where, err):
    for m in AMOUNT.finditer(nfc(text).casefold()):
        num, unit = m.group(1), m.group(2)
        digits = re.sub(r'[.,]', '', num) if re.fullmatch(r'\d{1,3}(?:[.,]\d{3})+', num) else None
        try:
            val = float(digits) if digits is not None else float(num.replace(',', '.'))
        except ValueError:
            continue
        if unit:
            val *= UNIT.get(unit.strip(), 1)
        elif digits is None:
            continue  # số trần nhỏ (ngày/giờ/tuổi…) không phải tiền
        if (unit or digits is not None) and int(round(val)) not in approved and val >= 1000:
            err('%s: số tiền %s%s không nằm trong bảng giá đã duyệt (data/business-facts.json)'
                % (where, num, (' ' + unit) if unit else ''))


def validate(root):
    errors, stats = [], {'files': 0, 'items': 0, 'schema_true': 0}

    def err(msg):
        errors.append(msg)

    faq_dir = os.path.join(root, '_data', 'faq')
    files = sorted(glob.glob(os.path.join(faq_dir, '*.json'))) if os.path.isdir(faq_dir) else []
    if not files:
        return errors, stats
    posts, dup_posts, pages, dup_pages = find_targets(root)
    approved = approved_amounts(root)
    all_q = []  # (key, idx, normalized question)
    all_a = []  # (key, idx, normalized answer)
    for path in files:
        key = os.path.splitext(os.path.basename(path))[0]
        stats['files'] += 1
        try:
            data = load_json(path)
        except (ValueError, OSError) as exc:
            err('%s: JSON không hợp lệ (%s)' % (key, exc))
            continue
        if not isinstance(data, dict) or not set(data) <= KEYS or 'items' not in data:
            err('%s: phải là object chỉ gồm %s và có "items"' % (key, sorted(KEYS)))
            continue
        if 'schema' in data and not isinstance(data['schema'], bool):
            err('%s: "schema" phải là boolean' % key)
        if 'heading' in data and not (isinstance(data['heading'], str) and 3 <= len(data['heading']) <= 80):
            err('%s: "heading" phải là chuỗi 3–80 ký tự' % key)
        if data.get('schema') is True:
            stats['schema_true'] += 1
        items = data['items']
        if not isinstance(items, list) or not (MIN_ITEMS <= len(items) <= MAX_ITEMS):
            err('%s: "items" phải là danh sách %d–%d mục (hiện %s)' % (key, MIN_ITEMS, MAX_ITEMS, len(items) if isinstance(items, list) else type(items).__name__))
            continue
        # F3: đích
        src_kinds = {it.get('src') for it in items if isinstance(it, dict)}
        in_posts, in_pages = key in posts, key in pages
        if key in dup_posts or key in dup_pages or (in_posts and in_pages):
            err('%s: khoá không duy nhất (bài/trang trùng slug hoặc faq_key)' % key)
        if not (in_posts or in_pages):
            err('%s: FAQ mồ côi — không có bài `_posts/*-%s.md` hay trang `faq_key: %s`' % (key, key, key))
            continue
        target = posts[key] if in_posts else pages[key]
        want_src = 'body' if in_posts else 'page'
        if src_kinds - {want_src}:
            err('%s: src phải là "%s" (đích là %s)' % (key, want_src, 'bài viết' if in_posts else 'trang'))
        with open(target, encoding='utf-8') as fh:
            _, body = strip_front_matter(fh.read())
        haystack = ' %s ' % norm_match(plain_text(body))
        for i, it in enumerate(items, 1):
            where = '%s#%d' % (key, i)
            stats['items'] += 1
            if not isinstance(it, dict) or set(it) != ITEM_KEYS:
                err('%s: mục phải có đúng khoá q/a/src' % where)
                continue
            q, a, src = it['q'], it['a'], it['src']
            if not (isinstance(q, str) and isinstance(a, str) and isinstance(src, str)):
                err('%s: q/a/src phải là chuỗi' % where)
                continue
            if src not in SRC:
                err('%s: src "%s" không hợp lệ (body|page)' % (where, src))
            if not (Q_MIN <= len(q) <= Q_MAX) or not q.rstrip().endswith('?'):
                err('%s: câu hỏi phải %d–%d ký tự và kết thúc bằng "?"' % (where, Q_MIN, Q_MAX))
            if not (A_MIN <= len(a) <= A_MAX):
                err('%s: câu trả lời phải %d–%d ký tự' % (where, A_MIN, A_MAX))
            for field, txt in (('q', q), ('a', a)):
                if re.search(r'[<>]|\{\{|\{%|\]\(|\*\*|`', txt):
                    err('%s: %s phải là văn bản thuần (không HTML/Liquid/markdown)' % (where, field))
            for field, txt in (('q', q), ('a', a)):
                for sent in split_sentences(txt):
                    check_blocked(sent, '%s.%s' % (where, field), err, is_question=(field == 'q'))
                check_amounts(txt, approved, '%s.%s' % (where, field), err)
            # F4: nguyên văn
            sents = split_sentences(a)
            if not sents or max(len(norm_match(s).split()) for s in sents) < 8:
                err('%s: câu trả lời phải có ít nhất một câu >= 8 từ' % where)
            for s in sents:
                ns = norm_match(s)
                if len(ns.split()) < 3:
                    err('%s: câu quá ngắn để xác minh nguyên văn: %r' % (where, s[:60]))
                elif ' %s ' % ns not in haystack:
                    err('%s: câu trả lời không trích nguyên văn từ nguồn: %r' % (where, s[:90]))
            all_q.append((key, i, norm_match(q)))
            all_a.append((key, i, norm_match(a)))
    # F6: trùng lặp
    seen = {}
    for key, i, nq in all_q:
        if nq in seen:
            err('%s#%d: câu hỏi trùng với %s#%d' % (key, i, seen[nq][0], seen[nq][1]))
        else:
            seen[nq] = (key, i)
    toks = [(k, i, n, set(n.split())) for k, i, n in all_q]
    for (k1, i1, n1, t1), (k2, i2, n2, t2) in itertools.combinations(toks, 2):
        if k1 == k2 or n1 == n2 or len(t1) < 4 or len(t2) < 4:
            continue  # cùng trang / trùng hệt (đã báo ở trên) / quá ngắn để so sánh
        j = len(t1 & t2) / len(t1 | t2)
        if j >= 0.8:
            err('%s#%d ~ %s#%d: câu hỏi gần trùng (Jaccard %.2f)' % (k1, i1, k2, i2, j))
    ans_seen = {}
    for key, i, na in all_a:
        if len(na.split()) >= 6:
            if na in ans_seen and ans_seen[na][0] != key:
                err('%s#%d: câu trả lời trùng hệt %s#%d' % (key, i, ans_seen[na][0], ans_seen[na][1]))
            ans_seen.setdefault(na, (key, i))
    return errors, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    errors, stats = validate(a.root)
    if a.json:
        print(json.dumps({'errors': errors, 'stats': stats}, ensure_ascii=False, indent=1))
    else:
        for e in errors:
            print('ERROR', e)
        print('faq files: %(files)d, items: %(items)d, schema=true: %(schema_true)d, errors: ' % stats + str(len(errors)))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
