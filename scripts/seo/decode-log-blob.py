#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Giải mã khối `NAME_BEGIN sha256=... bytes=...` / `NAME_END` (gzip+base64) do live-url-audit.py in vào log runner.

Runner GitHub không đẩy tệp về được môi trường agent (host lưu log/artifact bị chặn), nên kết quả audit được in
vào log và đọc lại bằng công cụ GitHub. Công cụ này tách khối đó, kiểm sha256 rồi ghi JSON.

  python3 scripts/seo/decode-log-blob.py LOG.txt LIVE_INVENTORY out.json
  python3 scripts/seo/decode-log-blob.py LOG.txt STUB_EVIDENCE out.json

Dòng log có thể mang tiền tố thời gian của Actions (`2026-10-24T13:03:04.123Z `) hoặc mã màu: được bỏ qua.
Mã thoát: 0 = ok, 2 = không thấy khối / sai sha256 / không đọc được.
"""
import base64
import gzip
import hashlib
import json
import re
import sys

TS = re.compile(r'^\S*\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\s?')
ANSI = re.compile(r'\x1b\[[0-9;]*m')


def extract(text, name):
    blocks, cur, meta = [], None, None
    for line in text.splitlines():
        line = ANSI.sub('', TS.sub('', line)).strip()
        m = re.match(r'^%s_BEGIN sha256=([0-9a-f]{64}) bytes=(\d+)$' % re.escape(name), line)
        if m:
            cur, meta = [], (m.group(1), int(m.group(2)))
            continue
        if line == '%s_END' % name and cur is not None:
            blocks.append((meta, ''.join(cur)))
            cur = None
            continue
        if cur is not None:
            cur.append(line)
    if not blocks:
        raise ValueError('không thấy khối %s trong log' % name)
    (sha, size), b64 = blocks[-1]          # lấy khối cuối cùng
    raw = base64.b64decode(b64)
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError('sai kích thước/sha256 của khối %s' % name)
    return json.loads(gzip.decompress(raw).decode('utf-8'))


def main(argv):
    if len(argv) != 4:
        print(__doc__)
        return 2
    try:
        with open(argv[1], encoding='utf-8', errors='replace') as f:
            obj = extract(f.read(), argv[2])
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print('LỖI:', e, file=sys.stderr)
        return 2
    with open(argv[3], 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    print('ok:', argv[3])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
