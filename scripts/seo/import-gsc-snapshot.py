#!/usr/bin/env python3
"""Nhập snapshot Google Search Console (JSON thô do connector trả về) thành CSV gọn trong reports/factory/seo-master/gsc/.

Vì sao có tệp này: môi trường agent không gọi được API Google trực tiếp; dữ liệu Search Console của
https://blog.thuexemaynguyentu.com/ đến qua connector MCP (Seo_key -> Search Console Performance report) và được lưu NGUYÊN VĂN
ra tệp JSON. Script này chỉ ĐỔI ĐỊNH DẠNG (không làm tròn lại, không suy diễn, không điền số thiếu) để các công cụ SEO Master
đọc được và để lần sau so sánh theo thời gian. Không gọi mạng. Đầu ra xác định (cùng đầu vào -> cùng byte).

JSON đầu vào (mỗi tệp một truy vấn Performance): {"site", "period": {"start","end","days"}, "dimensions": [...], "totals": {...},
"rows": [{<dimension>..., "clicks", "impressions", "ctr", "position"[, "prev_clicks", "prev_impressions", "prev_position"]}]}.

Dùng:
  python3 scripts/seo/import-gsc-snapshot.py --raw-dir <thư mục JSON thô> --fetched-on 2026-11-17 --connector "Seo_key MCP"
Tệp JSON thô được nhận diện theo `dimensions` + `period`, không theo tên tệp. URL được bỏ host và giải mã %XX thành đường dẫn
(giống cột `url` của url-inventory.csv); phần `#đoạn` (Google ghi nhận liên kết nhảy tới heading) được giữ ở cột `fragment`.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(ROOT, 'reports', 'factory', 'seo-master', 'gsc')


def split_url(page, site):
    """'https://host/a/b/#x' -> ('/a/b/', 'x'); giữ nguyên nếu không thuộc site."""
    p = urllib.parse.unquote(page)
    base = site.rstrip('/')
    if p.startswith(base):
        p = p[len(base):] or '/'
    frag = ''
    if '#' in p:
        p, frag = p.split('#', 1)
    return p, frag


def load_registry_groups():
    """{đường dẫn: nhóm} từ slug-redirect-registry.csv: old-<status> cho URL cũ, new-migrated cho URL mới."""
    reg = os.path.join(ROOT, 'reports', 'factory', 'seo-master', 'slug-redirect-registry.csv')
    out = {}
    if os.path.isfile(reg):
        with open(reg, encoding='utf-8', newline='') as f:
            for r in csv.DictReader(f):
                out[r['old_url']] = 'old-' + r['status'].lower()
                out[r['new_url']] = 'new-migrated'
    return out


def write_csv(name, header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(header)
    w.writerows(rows)
    data = buf.getvalue().encode('utf-8')
    with open(os.path.join(OUT_DIR, name), 'wb') as f:
        f.write(data)
    return {'file': name, 'rows': len(rows), 'sha256': hashlib.sha256(data).hexdigest()}


def num(v):
    """Giữ nguyên số connector trả về (không làm tròn lại)."""
    return '' if v is None else repr(v) if isinstance(v, float) else str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw-dir', required=True)
    ap.add_argument('--fetched-on', required=True, help='YYYY-MM-DD ngày lấy dữ liệu')
    ap.add_argument('--connector', default='Seo_key MCP (Google Search Console Performance report)')
    a = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    raws = []
    for fn in sorted(os.listdir(a.raw_dir)):
        if not fn.endswith('.json'):
            continue
        with open(os.path.join(a.raw_dir, fn), encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict) and 'rows' in d and 'dimensions' in d and 'period' in d:
            raws.append((fn, d))
    if not raws:
        sys.exit('không thấy JSON Performance nào trong %s' % a.raw_dir)
    site = raws[0][1]['site']
    files, queries_meta = [], []
    longest = max(d['period']['days'] for _, d in raws)
    for fn, d in raws:
        if d['site'] != site:
            sys.exit('%s thuộc property khác (%s != %s)' % (fn, d['site'], site))
        dims, per = d['dimensions'], d['period']
        tag = '%s_%s' % (per['start'], per['end'])
        has_prev = bool(d.get('compare'))
        meta = {'raw_file': fn, 'dimensions': dims, 'period': per, 'totals': d.get('totals'), 'type': d.get('type'),
                'data_state': d.get('data_state'), 'more': d.get('more'), 'notes': d.get('notes') or [],
                'compare': d.get('compare')}
        rows = d['rows']
        if dims == ['page']:
            out = []
            for r in rows:
                path, frag = split_url(r['page'], site)
                row = [path, frag, num(r['clicks']), num(r['impressions']), num(r['ctr']), num(r['position'])]
                if has_prev:
                    row += [num(r.get('prev_clicks')), num(r.get('prev_impressions')), num(r.get('prev_position'))]
                out.append(row)
            out.sort(key=lambda x: (-int(x[3]), x[0], x[1]))
            header = ['url', 'fragment', 'clicks', 'impressions', 'ctr', 'position']
            if has_prev:
                header += ['prev_clicks', 'prev_impressions', 'prev_position']
            name = 'gsc-pages-%s%s.csv' % (tag, '-vs-prev' if has_prev else '')
        elif dims == ['query']:
            out = [[r['query'], num(r['clicks']), num(r['impressions']), num(r['ctr']), num(r['position'])] for r in rows]
            out.sort(key=lambda x: (-int(x[2]), x[0]))
            header = ['query', 'clicks', 'impressions', 'ctr', 'position']
            name = 'gsc-queries-%s.csv' % tag
        elif dims == ['page', 'query']:
            out = []
            for r in rows:
                path, frag = split_url(r['page'], site)
                out.append([path, frag, r['query'], num(r['clicks']), num(r['impressions']), num(r['ctr']), num(r['position'])])
            out.sort(key=lambda x: (x[0], x[1], -int(x[4]), x[2]))
            header = ['url', 'fragment', 'query', 'clicks', 'impressions', 'ctr', 'position']
            name = 'gsc-page-query-%s.csv' % tag
        elif dims == ['date']:
            out = [[r['date'], num(r['clicks']), num(r['impressions']), num(r['ctr']), num(r['position'])] for r in rows]
            out.sort()
            header = ['date', 'clicks', 'impressions', 'ctr', 'position']
            name = 'gsc-daily-%s.csv' % tag
        elif dims == ['date', 'page']:
            # Không lưu từng hàng (hàng chục nghìn): gộp theo ngày x nhóm URL của registry di trú slug đ->d, để theo dõi
            # URL cũ đã gỡ (RETIRED, 404) / URL mới / phần còn lại. Tổng theo trang (byPage) có thể lệch nhẹ tổng property.
            groups = load_registry_groups()
            agg = {}
            for r in rows:
                path, _ = split_url(r['page'], site)
                g = groups.get(path, 'other')
                k = (r['date'], g)
                c = agg.setdefault(k, [0, 0, 0.0])
                c[0] += r['clicks']
                c[1] += r['impressions']
                c[2] += r['position'] * r['impressions']
            out = [[dt, g, str(c[0]), str(c[1]), ('%.2f' % (c[2] / c[1])) if c[1] else '']
                   for (dt, g), c in sorted(agg.items())]
            header = ['date', 'url_group', 'clicks', 'impressions', 'position_weighted']
            name = 'gsc-daily-url-groups-%s.csv' % tag
        elif dims == ['device']:
            out = [[r['device'], num(r['clicks']), num(r['impressions']), num(r['ctr']), num(r['position'])] for r in rows]
            out.sort()
            header = ['device', 'clicks', 'impressions', 'ctr', 'position']
            name = 'gsc-device-%s.csv' % tag
        else:
            continue
        info = write_csv(name, header, out)
        info.update(meta)
        info['is_primary_window'] = (per['days'] == longest)
        files.append(info)
    snap = {
        'schema': 'gsc-snapshot/1',
        'property': site,
        'connector': a.connector,
        'fetched_on': a.fetched_on,
        'note': 'Số liệu là bản chụp có ngày; Search Console trễ khoảng 2 ngày và chỉ có dữ liệu từ khi property được tạo. '
                'URL không có hàng trong gsc-pages = Search Console không ghi nhận lượt hiển thị nào trong kỳ. '
                'Hàng theo truy vấn cộng lại nhỏ hơn tổng vì Google ẩn truy vấn hiếm (ghi chú của Search Console).',
        'files': sorted(files, key=lambda x: x['file']),
    }
    with open(os.path.join(OUT_DIR, 'gsc-snapshot.json'), 'w', encoding='utf-8') as f:
        json.dump(snap, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write('\n')
    for i in snap['files']:
        print('%-55s %6d hàng' % (i['file'], i['rows']))


if __name__ == '__main__':
    main()
