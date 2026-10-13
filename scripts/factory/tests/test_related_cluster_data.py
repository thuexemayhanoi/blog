#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bất biến dữ liệu cho _includes/related-articles.html (đường nhanh theo cụm).

Include chọn "bài liên quan" bằng: bài factory của cụm = `site.posts | where: "child_id"` (frontmatter),
bài legacy của cụm = `_data/legacy-clusters.yml` (sinh từ cùng nguồn với `_data/factory-map.yml`). Cách này chỉ đúng khi:

  R1  legacy-clusters.yml khớp 100% với factory-map.yml (cùng slug, cùng cụm, cùng thứ tự);
  R2  mọi slug legacy trỏ tới đúng MỘT tệp `_posts/*-<slug>.md` và bài đó KHÔNG có `child_id:` trong frontmatter
      (nếu có sẽ bị đếm hai lần: một ở nhánh legacy, một ở nhánh where);
  R3  mọi bài KHÔNG có `child_id:` trong frontmatter đều là bài legacy có mặt trong factory-map (không bài mồ côi);
  R4  tổng số slug trong legacy-clusters == số mục trong factory-map.

Chạy: python3 scripts/factory/tests/test_related_cluster_data.py (từ gốc repository)
"""
import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def factory_map():
    out, cur = {}, None
    for line in read('_data/factory-map.yml').splitlines():
        if not line or line.startswith('#'):
            continue
        m = re.match(r'^([^\s:][^:]*):\s*$', line)
        if m:
            cur = m.group(1)
            out[cur] = {}
            continue
        m = re.match(r'^\s+([pc]):\s*(\S+)\s*$', line)
        if m and cur:
            out[cur][m.group(1)] = m.group(2)
    return out


def legacy_clusters():
    out, cur = {}, None
    for line in read('_data/legacy-clusters.yml').splitlines():
        if not line or line.startswith('#'):
            continue
        m = re.match(r'^([^\s:][^:]*):\s*$', line)
        if m:
            cur = m.group(1)
            out[cur] = []
            continue
        m = re.match(r'^\s+-\s+(\S+)\s*$', line)
        if m and cur:
            out[cur].append(m.group(1))
    return out


def front_matter(path):
    with open(path, encoding='utf-8') as f:
        t = f.read(6000)
    m = re.match(r'\A---\s*\n(.*?)\n---', t, re.S)
    return m.group(1) if m else ''


class TestRelatedClusterData(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fmap = factory_map()
        cls.clusters = legacy_clusters()
        cls.posts = {}
        for p in glob.glob(os.path.join(ROOT, '_posts', '*.md')):
            m = re.match(r'\d{4}-\d{2}-\d{2}-(.+)\.md$', os.path.basename(p))
            if m:
                cls.posts.setdefault(m.group(1), []).append(p)

    def test_r1_clusters_match_factory_map(self):
        expect = {}
        for slug, v in self.fmap.items():
            expect.setdefault(v['c'], []).append(slug)
        self.assertEqual(self.clusters, expect,
                         'legacy-clusters.yml lệch factory-map.yml: chạy python3 scripts/factory/restore-foundation.py')

    def test_r2_legacy_slugs_are_real_posts_without_child_id(self):
        for cid, slugs in self.clusters.items():
            for s in slugs:
                self.assertEqual(len(self.posts.get(s, [])), 1, 'slug legacy %s (%s) phải có đúng 1 tệp _posts' % (s, cid))
                fm = front_matter(self.posts[s][0])
                self.assertIsNone(re.search(r'(?m)^child_id:', fm), 'bài legacy %s có child_id trong frontmatter' % s)

    def test_r3_every_post_without_child_id_is_legacy(self):
        orphans = []
        for slug, paths in self.posts.items():
            fm = front_matter(paths[0])
            if re.search(r'(?m)^child_id:', fm):
                continue
            if slug not in self.fmap:
                orphans.append(slug)
        self.assertEqual(orphans, [], 'bài không có child_id và không nằm trong factory-map: %s' % orphans[:5])

    def test_r4_counts(self):
        self.assertEqual(sum(len(v) for v in self.clusters.values()), len(self.fmap))


if __name__ == '__main__':
    unittest.main(verbosity=1)
