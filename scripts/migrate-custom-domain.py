#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Idempotent migration from GitHub project-site baseurl /blog to the
custom-domain root https://blog.thuexemaynguyentu.com.

_drafts/ is intentionally untouched so this maintenance commit cannot wake
Factory Publish. Published/runtime source and future factory URL generation
are migrated.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OLD_BASE = "https://thuexemayhanoi.github.io/blog"
OLD_HOST = "https://thuexemayhanoi.github.io"
NEW_BASE = "https://blog.thuexemaynguyentu.com"
MIGRATION_VERSION = 3

TEXT_EXT = {
    ".md", ".markdown", ".html", ".htm", ".yml", ".yaml", ".json", ".csv",
    ".py", ".js", ".css", ".scss", ".sass", ".txt", ".xml"
}
EXCLUDE_TOP = {
    ".git", ".github", "reports", "_drafts", "vendor", "node_modules",
    ".jekyll-cache", ".sass-cache"
}
ROOT_REL_BLOG = re.compile(r"(?<![A-Za-z0-9._-])/blog/")


def read(path):
    return path.read_text(encoding="utf-8")


def write_if_changed(path, old, new, changed):
    if new != old:
        path.write_text(new, encoding="utf-8")
        changed.append(str(path.relative_to(ROOT)))


def patch_config(changed):
    p = ROOT / "_config.yml"
    old = read(p)
    new = re.sub(r'^baseurl:\s*["\']?/blog["\']?\s*$', 'baseurl: ""', old, flags=re.M)
    new = re.sub(r'^url:\s*["\']https://thuexemayhanoi\.github\.io["\']\s*$',
                 'url: "' + NEW_BASE + '"', new, flags=re.M)
    write_if_changed(p, old, new, changed)


def patch_robots(changed):
    p = ROOT / "robots.txt"
    old = read(p)
    new = re.sub(r'^Sitemap:\s*.*$', 'Sitemap: ' + NEW_BASE + '/sitemap.xml',
                 old, flags=re.M)
    write_if_changed(p, old, new, changed)


def patch_check_built_links(changed):
    p = ROOT / "scripts/factory/check-built-links.py"
    old = read(p)
    new = old
    start = new.index("def _site_baseurl():")
    end = new.index("\n\n# ------------------------------------------------------------------ trích link", start)
    replacement = '''def _site_baseurl():
    cfg = open(os.path.join(ROOT, '_config.yml'), encoding='utf-8').read()
    m = re.search(r'^baseurl:\\s*(?:"([^"]*)"|\\'([^\\']*)\\'|([^\\s#]*))', cfg, re.M)
    if not m:
        raise SystemExit('QA: không đọc được baseurl từ _config.yml')
    value = next((g for g in m.groups() if g is not None), '')
    if value and not value.startswith('/'):
        raise SystemExit('QA: baseurl không hợp lệ trong _config.yml: %s' % value)
    return value.rstrip('/')


BASEURL = _site_baseurl()
HOST = 'https://blog.thuexemaynguyentu.com'
SITE_URL = HOST + BASEURL


def _with_base(path):
    path = '/' + path.lstrip('/')
    return BASEURL + path if BASEURL else path


def _inside_site(path):
    if BASEURL:
        return path == BASEURL or path.startswith(BASEURL + '/')
    return path.startswith('/')
'''
    new = new[:start] + replacement + new[end:]
    new = new.replace("if path.startswith(BASEURL + BASEURL):",
                      "if BASEURL and path.startswith(BASEURL + BASEURL + '/'):")
    write_if_changed(p, old, new, changed)


def patch_generate_matrix(changed):
    p = ROOT / "scripts/factory/generate-matrix.py"
    old = read(p)
    new = old
    start = new.index("def canonical_internal_link(link):")
    end = new.index("\n\ndef read_sources():", start)
    replacement = '''def canonical_internal_link(link):
    """Chuẩn hoá liên kết nội bộ về root-relative URL của custom domain."""
    link = (link or '').strip()
    if (not link or link.startswith('#')
            or link.startswith(('http://', 'https://', 'mailto:', 'tel:'))):
        return link
    if not link.startswith('/'):
        link = '/' + link
    return link
'''
    new = new[:start] + replacement + new[end:]
    new = new.replace(
        "parent_cat.setdefault(c['parent_id'], c['hub_url'].split('/')[2])",
        "parent_cat.setdefault(c['parent_id'], c['hub_url'].strip('/').split('/')[0])"
    )
    write_if_changed(p, old, new, changed)


def patch_generate_topic_hubs(changed):
    p = ROOT / "scripts/factory/generate-topic-hubs.py"
    old = read(p)
    new = old.replace(
        "            if route.startswith('/blog'):\n"
        "                route = route[len('/blog'):]\n",
        ""
    )
    write_if_changed(p, old, new, changed)


def patch_validate(changed):
    p = ROOT / "scripts/factory/validate.py"
    old = read(p)
    new = old.replace(OLD_BASE, NEW_BASE).replace(OLD_HOST, NEW_BASE)
    write_if_changed(p, old, new, changed)


def is_test_file(rel):
    parts = rel.parts
    return len(parts) >= 3 and parts[0] == "scripts" and parts[1] == "factory" and parts[2] == "tests"


def migrate_runtime_text(changed):
    self_path = (ROOT / "scripts/migrate-custom-domain.py").resolve()
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.resolve() == self_path:
            continue
        rel = p.relative_to(ROOT)
        if rel.parts and rel.parts[0] in EXCLUDE_TOP:
            continue
        if is_test_file(rel):
            continue
        if p.suffix.lower() not in TEXT_EXT and p.name not in {"CNAME"}:
            continue
        try:
            old = read(p)
        except UnicodeDecodeError:
            continue
        new = old.replace(OLD_BASE, NEW_BASE)
        # Repeat so legacy doubles such as /blog/blog/ fully collapse to root.
        while True:
            newer = ROOT_REL_BLOG.sub("/", new)
            if newer == new:
                break
            new = newer
        write_if_changed(p, old, new, changed)


def patch_factory_operator(changed):
    p = ROOT / "scripts/factory/factory-operator.py"
    old = read(p)
    new = old

    start = new.index("def _site_baseurl():")
    end = new.index("\n\nBASEURL = None", start)
    replacement = '''def _site_baseurl():
    cfg = open(os.path.join(ROOT, '_config.yml'), encoding='utf-8').read()
    m = re.search(r'^baseurl:\\s*(?:"([^"]*)"|\\'([^\\']*)\\'|([^\\s#]*))', cfg, re.M)
    if not m:
        raise SystemExit('QA: không đọc được baseurl từ _config.yml')
    value = next((g for g in m.groups() if g is not None), '')
    if value and not value.startswith('/'):
        raise SystemExit('QA: baseurl không hợp lệ trong _config.yml: %s' % value)
    return value.rstrip('/')
'''
    new = new[:start] + replacement + new[end:]

    ep_start = new.index("    expected_permalink =")
    ep_end = new.index("\n    checks['permalink_canonical']", ep_start)
    new = (new[:ep_start] +
           "    expected_permalink = row['canonical_url'].replace('{date}', date_url)" +
           new[ep_end:])

    nh_start = new.index("    checks['no_hardcoded_blog']")
    nh_end = new.index("\n\n    # ---- cannibalization", nh_start)
    nh = ("    legacy_project_prefix = '/' + 'blog/'\n"
          "    checks['no_hardcoded_blog'] = legacy_project_prefix not in body")
    new = new[:nh_start] + nh + new[nh_end:]

    write_if_changed(p, old, new, changed)


def final_assertions():
    cfg = read(ROOT / "_config.yml")
    if 'baseurl: ""' not in cfg or ('url: "' + NEW_BASE + '"') not in cfg:
        raise SystemExit("migration assertion failed: _config.yml")
    robots = read(ROOT / "robots.txt")
    if NEW_BASE + "/sitemap.xml" not in robots:
        raise SystemExit("migration assertion failed: robots.txt")

    bad = []
    check_roots = ["_posts", "data", "_data", "_includes", "_layouts", "scripts"]
    for root_name in check_roots:
        root = ROOT / root_name
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or p.name == "migrate-custom-domain.py":
                continue
            rel = p.relative_to(ROOT)
            if is_test_file(rel):
                continue
            if p.suffix.lower() not in TEXT_EXT:
                continue
            try:
                text = read(p)
            except UnicodeDecodeError:
                continue
            if ROOT_REL_BLOG.search(text):
                bad.append(str(rel))
                if len(bad) >= 20:
                    break
        if len(bad) >= 20:
            break
    if bad:
        raise SystemExit("root-relative /blog/ remains in runtime source: " + ", ".join(bad))


def main():
    changed = []
    patch_config(changed)
    patch_robots(changed)
    patch_check_built_links(changed)
    patch_generate_matrix(changed)
    patch_generate_topic_hubs(changed)
    patch_validate(changed)
    migrate_runtime_text(changed)
    patch_factory_operator(changed)
    final_assertions()
    changed = sorted(set(changed))
    print("Custom-domain migration complete.")
    print("Changed files:", len(changed))
    for p in changed[:80]:
        print(" -", p)
    if len(changed) > 80:
        print(" ... +%d more" % (len(changed) - 80))
    print("_drafts intentionally untouched; Factory Publish remains asleep.")


if __name__ == "__main__":
    main()
