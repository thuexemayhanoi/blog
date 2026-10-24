#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trạng thái vận hành THẬT không được rò vào fixture của test engine.

data/factory/production-control.json là công tắc vận hành do chủ site bật/tắt
(ví dụ tạm dừng sản xuất để bảo trì slug/404). Fixture là bản sao của repo nên
thừa hưởng công tắc đó: khi chủ site tạm dừng thì mọi suite cần claim/publish
đều đỏ dù engine không lỗi. Gọi unpause_production() NGAY SAU khi sao chép repo;
test nào kiểm hành vi "paused" tự ghi lại file này sau đó. Repo thật không bị đụng.

File này là helper (không phải test).
"""
import json
import os


def unpause_production(root):
    path = os.path.join(root, 'data', 'factory', 'production-control.json')
    try:
        with open(path, encoding='utf-8') as f:
            cur = json.load(f)
    except (OSError, ValueError):
        cur = {}
    cur['enabled'] = True
    cur.setdefault('chunk_size', 2)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cur, f, indent=2)
        f.write('\n')
