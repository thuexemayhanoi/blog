#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PUBLISH GATE - kiểm tra trạng thái + bằng chứng TRƯỚC khi promote.

Cổng xuất bản cứng (không chỉ hướng dẫn bằng văn bản). Lệnh:

  python3 scripts/factory/publish-gate.py --draft _drafts/2026-09-27-slug.md --id BLG-00484

Điều kiện promote (tất cả phải đúng, không hạ ngưỡng):
  1. Matrix có hàng --id ở trạng thái PASS (writer tự set sau khi QA xong;
     WRITING/QA bị từ chối).
  2. Bằng chứng chấm điểm tồn tại: data/qa/<id>.json với quality >= 90,
     seo >= 90, business_fact = PASS, legal = PASS|NOT_REQUIRED,
     critical_failure = false. Điểm nội bộ, không phải điểm Google.
  3. Draft tồn tại, có frontmatter đầy đủ, không chứa placeholder nháp.
  4. Writer-lock đang tự do; transaction được ghi active trong lúc gate chạy
     (nhanh, tự đóng lại nếu mọi thứ PASS).
  5. Chỉ khi TẤT CẢ điều kiện đúng: chuyển draft sang _posts/ với tên tệp
     đúng ngày, cập nhật trạng thái matrix -> PUBLISHED, cập nhật checkpoint
     (last_completed_article_id, next_claimable_id, updated_at = giờ chạy thật).

FAIL bất kỳ: giữ draft trong _drafts/, ghi rõ lý do, exit 1. Không đổi gì.
Rollback: revert commit promote; chạy lại generate-reports.py.
"""
import argparse, csv, datetime, json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
MATRIX = 'data/content-matrix.csv'
QA_DIR = 'data/qa'
LOCK = 'data/state/writer-lock.json'
TXN = 'data/state/transaction.json'
CP = 'data/state/checkpoint.json'

QUALITY_MIN = 90
SEO_MIN = 90


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')


def fail(msgs):
    print('=== PUBLISH GATE: TỪ CHỐI ===')
    for m in msgs:
        print('FAIL:', m)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--draft', required=True)
    ap.add_argument('--id', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    errs = []

    # 1. matrix hàng PASS
    if not os.path.exists(MATRIX):
        fail(['matrix thiếu — không thể promote'])
    with open(MATRIX, encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    row = next((r for r in rows if r['id'] == args.id), None)
    if row is None:
        fail(['không tìm thấy %s trong matrix' % args.id])
    if row['status'] != 'PASS':
        fail(['trạng thái %s là %s — gate chỉ promote hàng PASS (WRITING/QA/PLANNED bị từ chối)' % (args.id, row['status'])])

    # 2. bằng chứng QA
    qa_path = os.path.join(QA_DIR, args.id + '.json')
    if not os.path.exists(qa_path):
        fail(['thiếu bằng chứng chấm điểm: %s' % qa_path])
    qa = json.load(open(qa_path, encoding='utf-8'))
    if qa.get('quality', 0) < QUALITY_MIN:
        errs.append('quality %s < %d' % (qa.get('quality'), QUALITY_MIN))
    if qa.get('seo', 0) < SEO_MIN:
        errs.append('seo %s < %d' % (qa.get('seo'), SEO_MIN))
    if qa.get('business_fact') != 'PASS':
        errs.append('business_fact phải PASS, có %s' % qa.get('business_fact'))
    if qa.get('legal') not in ('PASS', 'NOT_REQUIRED'):
        errs.append('legal phải PASS/NOT_REQUIRED, có %s' % qa.get('legal'))
    if qa.get('critical_failure', True):
        errs.append('critical_failure phải là false')
    if errs:
        fail(errs)

    # 3. draft
    if not os.path.exists(args.draft) or not args.draft.startswith('_drafts/'):
        fail(['draft không tồn tại hoặc không nằm trong _drafts/: %s' % args.draft])
    text = open(args.draft, encoding='utf-8').read()
    fm = re.match(r'^---\n(.*?)\n---', text, re.S)
    if not fm:
        fail(['draft thiếu frontmatter'])
    front = fm.group(1)
    for field in ('title:', 'date:', 'categories:', 'description:'):
        if field not in front:
            fail(['draft thiếu frontmatter: %s' % field])
    if 'MẪU NHẬP BÀI' in text or 'lorem' in text.lower():
        fail(['draft còn placeholder nháp'])

    # 4. lock + transaction
    lock = json.load(open(LOCK, encoding='utf-8'))
    if lock.get('locked'):
        fail(['writer-lock đang bị giữ bởi %s' % lock.get('holder')])
    txn = json.load(open(TXN, encoding='utf-8'))
    if txn.get('active'):
        fail(['transaction đang active — recover trước khi promote'])

    # ngày xuất bản = ngày trong tên draft (YYYY-MM-DD-slug.md); matrix chỉ lưu
    # placeholder {date} cho tới khi promote (chốt ngày thật tại đây).
    dm = re.match(r'(\d{4}-\d{2}-\d{2})-', os.path.basename(args.draft))
    if not dm:
        fail(['tên draft phải dạng YYYY-MM-DD-slug.md: %s' % args.draft])
    date_part = dm.group(1)
    # slug hàng matrix: _posts/{date}-slug.md (chưa promote) hoặc đã có ngày thật
    op = row['output_path']
    if op.startswith('_posts/{date}-'):
        slug_want = op[len('_posts/{date}-'):-3]
    else:
        om = re.match(r'_posts/\d{4}-\d{2}-\d{2}-(.+\.md)$', op)
        if not om:
            fail(['output_path matrix sai định dạng: %s' % op])
        slug_want = om.group(1)[:-3]
    slug_have = os.path.basename(args.draft)[11:-3]
    if slug_have != slug_want:
        fail(['slug draft (%s) != slug matrix (%s)' % (slug_have, slug_want)])
    dest = '_posts/%s-%s.md' % (date_part, slug_want)

    # ghi transaction active trong lúc promote
    if not args.dry_run:
        txn = {'active': True, 'updated_at': now_iso(),
               'pending': {'step': 'promote %s' % args.id, 'draft': args.draft},
               'history': []}
        json.dump(txn, open(TXN, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    try:
        if args.dry_run:
            print('=== PUBLISH GATE: DRY-RUN PASS (không đổi gì) ===')
            print('sẽ promote %s -> %s' % (args.draft, dest))
            return
        # 5. promote
        shutil.move(args.draft, dest)
        for r in rows:
            if r['id'] == args.id:
                r['status'] = 'PUBLISHED'
                r['output_path'] = dest
                r['expected_url'] = r['expected_url'].replace('{date}', '%s/%s/%s' % (date_part[:4], date_part[5:7], date_part[8:]))
                r['canonical_url'] = r['expected_url']
        fields = list(rows[0].keys())
        with open(MATRIX, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

        # checkpoint
        cp = json.load(open(CP, encoding='utf-8'))
        planned_left = [r['id'] for r in rows if r['status'] == 'PLANNED']
        cp['last_completed_article_id'] = args.id
        cp['next_claimable_id'] = planned_left[0] if planned_left else None
        cp['updated_at'] = now_iso()
        cp['last_run_id'] = 'publish-gate-' + args.id
        cp['counts']['planned'] = sum(1 for r in rows if r['status'] == 'PLANNED')
        cp['counts']['published'] = sum(1 for r in rows if r['status'] == 'PUBLISHED')
        json.dump(cp, open(CP, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

        txn = {'active': False, 'updated_at': now_iso(), 'pending': None, 'history': []}
        json.dump(txn, open(TXN, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print('=== PUBLISH GATE: PROMOTED ===')
        print('%s -> %s' % (args.draft, dest))
        print('checkpoint: last_completed=%s next_claimable=%s' % (args.id, cp['next_claimable_id']))
    except Exception:
        # nếu dở dang: trả draft về _drafts/
        if os.path.exists(dest) and not os.path.exists(args.draft):
            shutil.move(dest, args.draft)
        txn = {'active': False, 'updated_at': now_iso(), 'pending': None, 'history': []}
        json.dump(txn, open(TXN, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        raise


if __name__ == '__main__':
    main()
