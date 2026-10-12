#!/usr/bin/env python3
"""READ-ONLY legacy QA audit. Emits a proposal, NEVER writes QA or PASS.

python3 scripts/factory/audit-legacy-qa.py --baseline 04d46bef^ > audit.json
--rescore-stale independently calls the canonical scorer on published bytes
(no promotion, no evidence writes). A domain-only diff is NOT a QA approval.
"""
import argparse
import collections
import csv
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
FP_FIELDS = ('title', 'intent', 'primary_keyword', 'expected_url',
             'output_path', 'canonical_url')
OLD_BASE = 'https://thuexemayhanoi.github.io/blog'
NEW_BASE = 'https://blog.thuexemaynguyentu.com'
PREFIX = re.compile(r'(?<![A-Za-z0-9._-])/blog/')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(row):
    return sha(json.dumps({k: row[k] for k in FP_FIELDS}, ensure_ascii=False,
                          sort_keys=True).encode('utf-8'))


def migrated(data):
    """Exact v3 migration transform, one-way, no whitespace/prose stripping."""
    text = data.decode('utf-8').replace(OLD_BASE, NEW_BASE)
    while True:
        new = PREFIX.sub('/', text)
        if new == text:
            return text.encode('utf-8')
        text = new


def historical_blobs(ref):
    tree = subprocess.check_output(['git', 'ls-tree', '-r', '-z', ref], cwd=ROOT)
    entries = {}
    for record in tree.split(b'\0'):
        if not record:
            continue
        meta, path = record.split(b'\t', 1)
        path = path.decode('utf-8')
        if path.startswith(('_posts/', 'data/qa/')) or path == 'data/content-matrix.csv':
            entries[path] = meta.split()[2].decode('ascii')
    # Batch immutable blob reads; no checkout/reset or writes to production.
    proc = subprocess.run(['git', 'cat-file', '--batch'], cwd=ROOT,
                          input=('\n'.join(entries.values()) + '\n').encode(),
                          capture_output=True, check=True)
    stream = io.BytesIO(proc.stdout)
    out = {}
    for path in entries:
        header = stream.readline().split()
        if len(header) != 3 or header[1] != b'blob':
            raise ValueError('missing/non-blob historical source: ' + path)
        out[path] = stream.read(int(header[2]))
        if stream.read(1) != b'\n':
            raise ValueError('invalid git batch framing')
    return out


def classify(row, current, evidence, old_row=None, old_bytes=None, old_ev=None):
    """Provenance classification only. No label here authorizes re-attestation."""
    content_match = sha(current) == evidence.get('content_sha256')
    matrix_match = fingerprint(row) == evidence.get('matrix_row_sha256')
    result = {'id': row['id'], 'path': row['output_path'],
              'current_content_sha256': sha(current),
              'recorded_content_sha256': evidence.get('content_sha256'),
              'current_matrix_sha256': fingerprint(row),
              'recorded_matrix_sha256': evidence.get('matrix_row_sha256'),
              'content_match': content_match, 'matrix_match': matrix_match,
              'classification': 'CURRENT_HASHES_MATCH'}
    if content_match and matrix_match:
        return result
    result['classification'] = 'UNPROVEN_HISTORY'
    if old_row is None or old_bytes is None or old_ev is None:
        return result
    result['baseline_content_sha256'] = sha(old_bytes)
    result['baseline_matrix_sha256'] = fingerprint(old_row)
    # The recorded hashes must bind to actual immutable baseline bytes AND row.
    bound = (sha(old_bytes) == old_ev.get('content_sha256')
             and fingerprint(old_row) == old_ev.get('matrix_row_sha256')
             and evidence.get('content_sha256') == old_ev.get('content_sha256')
             and evidence.get('matrix_row_sha256') == old_ev.get('matrix_row_sha256'))
    result['baseline_bound'] = bound
    if not bound:
        result['classification'] = 'BASELINE_EVIDENCE_UNBOUND'
        return result
    matrix_only = all(migrated(old_row[k].encode()) == row[k].encode()
                      for k in FP_FIELDS)
    result['classification'] = ('DOMAIN_ONLY_PROVEN'
                                if migrated(old_bytes) == current and matrix_only
                                else 'CONTENT_OR_MATRIX_CHANGE')
    return result


# Untracked files can change what the audit reads. By path: the matrix, posts and
# evidence (data/, _posts/), business facts / taxonomy (data/) and the scorer code
# (scripts/). By content: factory-operator.canonical_routes() walks the whole repo and
# reads the `permalink:` of every .md/.html outside ROUTE_EXCLUDED, so an untracked page
# anywhere else can flip `links_routes_valid` / `critical_failure`. ROUTE_EXCLUDED mirrors
# that function (it never reads _drafts/, docs/, reports/ ...), so a writer's untracked
# draft or an `> audit.json` redirect does not trip the guard.
INPUT_DIRS = ('_posts', 'data', 'scripts')
ROUTE_EXCLUDED = ('scripts', 'assets', 'data', 'reports', 'docs', 'en', '_queue', '_drafts',
                  'gemfiles', 'node_modules', 'vendor', '.git', '.jekyll-cache',
                  '.sass-cache', '__pycache__')


def dirty_inputs(root=ROOT):
    """Paths whose working-tree state differs from the checked-out HEAD in a way the audit
    can see: any tracked modification/deletion, plus untracked files the audit reads (see
    INPUT_DIRS / ROUTE_EXCLUDED). The result is only attributable to `head` when empty."""
    def porcelain(*extra):
        raw = subprocess.check_output(['git', 'status', '--porcelain=v1', '-z'] + list(extra),
                                      cwd=root)
        return [e.decode('utf-8', 'surrogateescape') for e in raw.split(b'\0') if e]

    out = [e for e in porcelain('--untracked-files=no') if e.strip()]
    for entry in porcelain('--untracked-files=all'):
        if not entry.startswith('?? '):
            continue
        path = entry[3:]
        top = path.split('/')[0]
        if top in INPUT_DIRS or (path.endswith(('.md', '.html')) and top not in ROUTE_EXCLUDED):
            out.append(entry)
    return out


def rescore_published(op, row, rows, biz, tax):
    """Read actual _posts bytes through the SAME scorer; never invoke op_qa.

    qa_check_one reads the module-global APPROVED_AMOUNTS, which only
    build_amount_whitelist(biz) fills (factory-operator.main and writer-loop do
    it before scoring). Without it every money amount looks unapproved and
    business_fact is a false FAIL for any post that quotes an approved price."""
    op.build_amount_whitelist(biz)
    original = op.find_draft
    path = row['output_path']
    slug = pathlib.Path(path).name[11:-3]
    # qa_check_one opens the post by its repo-relative path, i.e. relative to the
    # PROCESS cwd. The CLI only works from elsewhere because importing the
    # operator happens to chdir; a library caller (tests, re-attestation tool)
    # must not depend on that. Pin the cwd to the scorer's own repo root for the
    # call and give the caller's cwd back.
    root = getattr(op, 'ROOT', None) or str(ROOT)
    try:
        previous = os.getcwd()
    except OSError:                      # caller's cwd was deleted
        previous = None
    try:
        os.chdir(root)
        op.find_draft = lambda r: (path, slug) if r['id'] == row['id'] else original(r)
        return op.qa_check_one(row, rows, biz, tax)
    finally:
        op.find_draft = original
        if previous is not None:
            os.chdir(previous)


def proposal_decision(classification, fresh, current, row, quality_min, seo_min):
    """Fresh scorer output must bind to exact current bytes/row. Still pending approval.

    No CLI accepts caller-supplied fresh evidence, and no write/promote path exists.
    Hashes are integrity checks, not authentication against a privileged code editor.
    """
    if classification != 'DOMAIN_ONLY_PROVEN':
        return 'MANUAL_REVIEW_REQUIRED'
    if not fresh or fresh.get('content_sha256') != sha(current) \
            or fresh.get('matrix_row_sha256') != fingerprint(row) \
            or fresh.get('article_id') != row['id']:
        return 'FRESH_QA_UNBOUND'
    if (fresh.get('result') != 'PASS' or fresh.get('quality', 0) < quality_min
            or fresh.get('seo', 0) < seo_min or fresh.get('business_fact') != 'PASS'
            or fresh.get('legal') not in ('PASS', 'NOT_REQUIRED')
            or fresh.get('critical_failure') is not False):
        return 'FRESH_QA_FAILED'
    return 'ELIGIBLE_PROPOSAL_AWAITING_OWNER_APPROVAL'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--rescore-stale', action='store_true')
    parser.add_argument('--allow-dirty', action='store_true',
                        help='run on a modified working tree (output then says head_bound: false)')
    args = parser.parse_args()
    baseline = subprocess.check_output(
        ['git', 'rev-parse', '--verify', args.baseline + '^{commit}'], cwd=ROOT,
        text=True).strip()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = dirty_inputs()
    if dirty and not args.allow_dirty:
        # The JSON names `head`; with a modified matrix/post/evidence/scorer/facts the
        # numbers would be attributed to a commit that never contained those inputs.
        print(json.dumps({'ok': False, 'code': 'DIRTY_TREE', 'head': head,
                          'error': 'working tree differs from HEAD; audit a clean checkout '
                                   '(or pass --allow-dirty, which marks head_bound: false)',
                          'dirty': dirty[:20], 'dirty_count': len(dirty)}, indent=2))
        return 1
    rows = list(csv.DictReader((ROOT / 'data/content-matrix.csv').open(encoding='utf-8')))
    history = historical_blobs(baseline)
    old_rows = {r['id']: r for r in csv.DictReader(io.StringIO(
        history['data/content-matrix.csv'].decode('utf-8')))}
    op = None
    if args.rescore_stale:
        spec = importlib.util.spec_from_file_location('legacy_readonly_scorer',
                                                      ROOT / 'scripts/factory/factory-operator.py')
        op = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(op)
        biz = json.loads((ROOT / 'data/business-facts.json').read_text())
        tax = json.loads((ROOT / 'data/content-taxonomy.json').read_text())
    results = []
    for row in rows:
        if row['status'] != 'PUBLISHED':
            continue
        qa_path = 'data/qa/' + row['id'] + '.json'
        current = (ROOT / row['output_path']).read_bytes()
        evidence = json.loads((ROOT / qa_path).read_text())
        old_row = old_rows.get(row['id'])
        old_bytes = history.get(old_row['output_path']) if old_row else None
        old_ev = json.loads(history[qa_path]) if qa_path in history else None
        result = classify(row, current, evidence, old_row, old_bytes, old_ev)
        if result['classification'] != 'CURRENT_HASHES_MATCH' and op:
            fresh = rescore_published(op, row, rows, biz, tax)
            result['fresh_qa'] = {k: fresh.get(k) for k in (
                'result', 'quality', 'seo', 'business_fact', 'legal', 'critical_failure')}
            result['failed_checks'] = sorted(k for k, v in fresh.get('checks', {}).items() if not v)
            result['proposal_decision'] = proposal_decision(
                result['classification'], fresh, current, row, op.QUALITY_MIN, op.SEO_MIN)
        results.append(result)
    output = {'audit_only': True, 're_attestation_authorized': False,
              'head': head, 'head_bound': not dirty, 'baseline_commit': baseline,
              'matrix_sha256': sha((ROOT / 'data/content-matrix.csv').read_bytes()),
              'migration_rule': '04d46bef v3: OLD_BASE replacement + bounded /blog/ prefix removal',
              'published_count': len(results),
              'content_mismatches': sum(not r['content_match'] for r in results),
              'matrix_mismatches': sum(not r['matrix_match'] for r in results),
              'classifications': dict(collections.Counter(r['classification'] for r in results)),
              'proposal_decisions': dict(collections.Counter(r.get('proposal_decision', 'NOT_RESCORED')
                                                           for r in results)),
              'articles': results}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
