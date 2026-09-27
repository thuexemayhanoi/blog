#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# sitemap-plan.py - du do do scale sitemap cho 10K (read-only).
# Hien tai dung jekyll-sitemap (1 file sitemap.xml).
# Ke hoach 10K-ready: ~1000 URL/shard + sitemap index.
# Chua kich hoat shard vi so URL con thap.
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
os.chdir(ROOT)

CAP_PATH = 'data/factory-capacity.json'
INV_PATH = 'data/content-inventory.csv'
ROBOTS = 'robots.txt'


def main():
    cap = json.load(open(CAP_PATH, encoding='utf-8'))
    sm = cap['sitemap']
    inv = list(csv.DictReader(open(INV_PATH, encoding='utf-8')))
    posts = [f for f in os.listdir('_posts') if f.endswith('.md')]
    legacy = len(inv)
    factory = max(0, len(posts) - legacy)
    live = legacy + factory
    per = sm['urls_per_shard']
    shards_now = max(1, -(-live // per))
    shards_10k = max(1, -(-cap['hard_capacity'] // per))
    robots = open(ROBOTS, encoding='utf-8').read()
    ok_robots = 'sitemap.xml' in robots.lower()
    print('=== SITEMAP 10K PLAN ===')
    print('urls live hien tai : %d (legacy %d + factory %d)'
          % (live, legacy, factory))
    print('urls per shard     : %d' % per)
    print('shards can bay gio : %d (shard_now=%s, dung 1 file)'
          % (shards_now, sm['shard_now']))
    print('shards tai 10K     : %d' % shards_10k)
    print('robots co sitemap  : %s'
          % ('OK' if ok_robots else 'MISSING'))
    if not ok_robots:
        sys.exit(1)
    print('RESULT: 10K-READY (ke hoach shard, chua kich hoat)')
    sys.exit(0)


if __name__ == '__main__':
    main()
