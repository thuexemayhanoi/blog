#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MỞ RỘNG VŨ TRỤ CHỦ ĐỀ (topic universe) — thuexemayhanoi/blog.

Bối cảnh: taxonomy hiện 7 parent / 51 child, EDITORIAL_TARGET 6.570 nhưng seed
mới đăng ký 350 hàng planned. Nhiệm vụ: mở rộng chủ đề THẬT theo các trục biên
tập (đối tượng, địa điểm, sự cố xe, so sánh, pháp lý, cung đường, kỹ năng,
hỏi đáp) — KHÔNG sinh biến thể từ, KHÔNG doorway theo tên quận.

Quy tắc chống spam (bắt buộc, kiểm máy):
- Mỗi hàng là MỘT ý định tìm kiếm riêng; không hoán đổi tính từ/từ đồng nghĩa.
- Không "bài cũ đổi tên quận/model": chỉ nhận chủ đề có nội dung thật khác.
- Cổng nhận hàng (scoring): usefulness>=70, distinct>=80, depth>=70,
  cannibalization_risk<=30, feasibility in (PASS, REVIEW). REVIEW = chấp nhận
  vào matrix nhưng source_required=true (bắt buộc nguồn chính thống khi viết).
- Chống trùng toàn bộ matrix hiện có (chuẩn hoá): intent, primary_keyword,
  slug, output_path, canonical.

Idempotent: chạy lại không sinh thêm hàng; chỉ bổ sung phần thiếu.
KHÔNG đụng: checkpoint, writer-lock, transaction, REVIEW, legacy, PUBLISHED.

Chạy: python3 scripts/factory/expand-topic-universe.py  (từ gốc repository)
Sau đó chạy theo thứ tự: restore-foundation.py -> generate-matrix.py ->
generate-reports.py và commit toàn bộ kết quả.
"""
import csv, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

TAX_CONFIG = 'data/state/taxonomy-config.json'
SEED_PATH = 'data/state/matrix-seed.json'
MATRIX_PATH = 'data/content-matrix.csv'
REPORT_PATH = 'reports/factory/topic-universe.md'

# ---------------- chuẩn hoá chống trùng (giống generate-matrix.py)


def norm(s):
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9 ]', '', s.lower()).strip()


# ---------------- CỔNG SCORING
GATE = {'usefulness': 70, 'distinct': 80, 'depth': 70, 'cannibalization': 30}
FEASIBILITY_OK = ('PASS', 'REVIEW')   # BLOCKED = từ chối

# ---------------- CHILD MỚI (tuple đúng schema taxonomy-config):
# (cid, pid, title, slug, desc, kw_head, kw_cluster, group, planned_target,
#  intent, level, legal_risk, source_required)
NEW_CHILDREN = [
    ('C-THUE-DOI-TUONG', 'P-THUE-XE', 'Thuê xe theo đối tượng',
     'thue-theo-doi-tuong',
     'Kinh nghiệm thuê xe máy cho từng nhóm người: sinh viên, người đi làm, '
     'gia đình, khách quốc tế, người mới biết lái.',
     'Thuê xe máy theo đối tượng', 'thuê xe máy cho', 'THUE', 80,
     'commercial', 'high', 'none', False),
    ('C-THUE-DIA-DIEM', 'P-THUE-XE', 'Thuê xe theo địa điểm',
     'thue-theo-dia-diem',
     'Thuê xe máy quanh ga, bến xe, sân bay và các khu vực trọng điểm của '
     'Hà Nội: lấy xe, giữ xe, di chuyển.',
     'Thuê xe máy theo địa điểm', 'thuê xe máy gần', 'THUE', 70,
     'commercial', 'high', 'none', False),
    ('C-XE-LUA-CHON', 'P-XE-MAY', 'Chọn loại xe khi thuê',
     'chon-loai-xe',
     'Tư vấn chọn xe số/xe ga, xe điện/xe xăng, dung tích, độ cao yên theo '
     'nhu cầu thực tế của người thuê.',
     'Chọn xe máy khi thuê', 'nên thuê xe gì', 'XE', 80,
     'informational', 'medium', 'none', False),
    ('C-XE-KHAC-PHUC', 'P-XE-MAY', 'Xử lý sự cố xe máy thuê',
     'xu-ly-su-co-xe',
     'Các sự cố kỹ thuật thường gặp khi đang thuê xe máy và cách xử lý ban '
     'đầu đúng cách, kèm khi nào cần báo cửa hàng.',
     'Xử lý sự cố xe máy thuê', 'xe thuê bị hỏng', 'XE', 90,
     'informational', 'medium', 'low', False),
    ('C-XE-SO-SANH', 'P-XE-MAY', 'So sánh khi thuê xe máy',
     'so-sanh-xe',
     'So sánh model với model, hình thức thuê theo thời gian, chi phí thuê '
     'với các phương tiện khác — để người thuê quyết định.',
     'So sánh thuê xe máy', 'so sánh thuê xe', 'XE', 90,
     'informational', 'high', 'none', False),
]

# ---------------- ỨNG VIÊN (candidate pool) — mỗi hàng một ý định riêng.
# R(cid, title, intent, kw, kw2, links, sub, aud, loc, wt, u, d, dep, biz, can, feas)
DEFAULT_LINKS = []


def R(cid, title, intent, kw, kw2=(), links=(), sub='', aud='', loc='hà nội',
      wt=1200, u=85, d=92, dep=80, biz=80, can=12, feas='PASS'):
    return {'child_id': cid, 'title': title, 'intent': intent, 'kw': kw,
            'kw2': list(kw2), 'links': list(links), 'subtopic': sub,
            'audience': aud, 'location_scope': loc, 'word_target': wt,
            'scores': {'usefulness': u, 'distinct_intent': d, 'depth': dep,
                       'business_relevance': biz,
                       'cannibalization_risk': can, 'feasibility': feas}}


# Hàng bị loại vĩnh viễn vì trùng slug/ý định với bài LEGACY đã có
# (không được tạo bài thứ hai cạnh tranh với bài cũ):
LEGACY_DUPLICATE_TITLES = {
    'Thuê xe máy cho sinh viên ở Hà Nội: cần lưu ý gì',        # trùng BLG-00044
    'Thuê xe máy dài hạn cho người nước ngoài ở Hà Nội',       # trùng BLG-00408
}

CANDIDATES = [
    # ============ C-THUE-DOI-TUONG: thuê theo đối tượng
    R('C-THUE-DOI-TUONG', 'Thuê xe máy cho sinh viên ở Hà Nội: cần lưu ý gì',
      'Tìm kinh nghiệm thuê xe máy cho sinh viên',
      'thuê xe máy cho sinh viên',
      ['sinh viên thuê xe máy hà nội', 'giá sinh viên thuê xe'],
      ['/blog/thue-xe/thue-thang/', '/blog/bang-gia/'],
      'đối tượng sinh viên', 'sinh viên', 'hà nội', 1200, 85, 92, 80, 85, 10),
    R('C-THUE-DOI-TUONG', 'Thuê xe máy dài hạn cho người đi làm trong nội thành',
      'Tìm giải pháp thuê xe dài hạn cho người đi làm',
      'thuê xe máy dài hạn cho người đi làm',
      ['thuê xe theo tháng đi làm', 'thuê xe công commuting'],
      ['/blog/thue-xe/thue-thang/'],
      'đối tượng đi làm', 'người đi làm', 'nội thành', 1300, 90, 92, 85, 85, 8),
    R('C-THUE-DOI-TUONG', 'Thuê xe máy cho cặp đôi đi chơi cuối tuần',
      'Tìm kinh nghiệm thuê xe máy cho hai người đi chơi',
      'thuê xe máy cho hai người đi chơi',
      ['cặp đôi thuê xe máy cuốn tuần'.replace('cuốn', 'cuối'), 'cho thuê xe chở người yêu'.replace('cho thuê', 'thuê')],
      ['/blog/cung-duong/cung-duong-cuoi-tuan/', '/blog/xe-may/chon-loai-xe/'],
      'đối tượng cặp đôi', 'cặp đôi', 'hà nội', 1200, 75, 90, 75, 75, 12),
    R('C-THUE-DOI-TUONG', 'Thuê xe máy cho gia đình có trẻ nhỏ đi cùng',
      'Tìm cách thuê xe máy an toàn khi đi cùng trẻ nhỏ',
      'thuê xe máy cho gia đình có trẻ nhỏ',
      ['đi xe máy chở trẻ nhỏ an toàn', 'thuê xe cho gia đình'],
      ['/blog/ky-nang/ky-nang-lai-co-ban/', '/blog/an-toan-phap-ly/quy-dinh-giao-thong/'],
      'đối tượng gia đình', 'gia đình', 'hà nội', 1300, 80, 90, 80, 75, 15),
    R('C-THUE-DOI-TUONG', 'Thuê xe máy cho người mới lấy bằng A1 lần đầu',
      'Tìm kinh nghiệm thuê xe lần đầu cho người mới có bằng',
      'thuê xe máy cho người mới có bằng a1',
      ['lần đầu thuê xe máy', 'người mới lái thuê xe'],
      ['/blog/xe-may/chon-loai-xe/', '/blog/hoi-dap/hoi-dap-nguoi-moi/'],
      'đối tượng người mới', 'người mới', 'hà nội', 1200, 88, 90, 80, 85, 8),
    R('C-THUE-DOI-TUONG', 'Người cao tuổi đi xe máy thuê: nên chọn xe như thế nào',
      'Tư vấn chọn xe máy thuê cho người cao tuổi',
      'người cao tuổi đi xe máy chọn xe nào',
      ['xe máy nhẹ dễ điều khiển', 'thuê xe cho người lớn tuổi'],
      ['/blog/xe-may/chon-loai-xe/'],
      'đối tượng cao tuổi', 'người cao tuổi', 'hà nội', 1200, 72, 88, 70, 65, 15),
    R('C-THUE-DOI-TUONG', 'Thuê xe máy cho người từ tỉnh ra Hà Nội công tác',
      'Tìm cách thuê xe máy khi ra Hà Nội công tác',
      'thuê xe máy khi ra hà nội công tác',
      ['thuê xe ngắn hạn công tác', 'đi công tác hà nội cần xe'],
      ['/blog/thue-xe/thue-ngay/', '/blog/thue-xe/thue-theo-dia-diem/'],
      'đối tượng công tác', 'khách công tác', 'hà nội', 1200, 78, 90, 75, 80, 10),
    R('C-THUE-DOI-TUONG', 'Thuê xe máy dài hạn cho người nước ngoài ở Hà Nội',
      'Tìm cách thuê xe máy dài hạn cho người nước ngoài cư trú',
      'người nước ngoài thuê xe máy dài hạn hà nội',
      ['expat thuê xe máy hà nội', 'thuê xe cho người nước ngoài ở lâu'],
      ['/blog/thue-xe/khach-quoc-te/', '/blog/thue-xe/thue-thang/'],
      'đối tượng expat', 'người nước ngoài', 'hà nội', 1400, 82, 92, 80, 85, 10, 'REVIEW'),
    R('C-THUE-DOI-TUONG', 'Thuê xe máy cho nhóm bạn đi phýt cuối tuần',
      'Tìm cách thuê xe máy cho nhóm nhiều người đi phượt'.replace('phýt', 'phượt'),
      'thuê xe máy cho nhóm đi phượt',
      ['nhóm bạn thuê xe máy', 'thuê nhiều xe máy cùng lúc'],
      ['/blog/cung-duong/cung-duong-cuoi-tuan/', '/blog/thue-xe/thu-tuc/'],
      'đối tượng nhóm', 'nhóm bạn', 'hà nội', 1300, 80, 90, 80, 80, 12),
    R('C-THUE-DOI-TUONG', 'Cần xe gấp trong ngày: thuê xe máy ngay có khó không',
      'Hiểu khả năng và cách thuê xe máy gấp trong ngày',
      'thuê xe máy gấp trong ngày',
      ['cần thuê xe ngay hôm nay', 'thuê xe không cần đặt trước'],
      ['/blog/thue-xe/thue-ngay/', '/blog/thue-xe/thu-tuc/'],
      'đối tượng khách vội', 'khách vội', 'hà nội', 1000, 75, 88, 70, 78, 12),

    # ============ C-THUE-DIA-DIEM: thuê theo địa điểm (cửa ngõ, không doorway quận)
    R('C-THUE-DIA-DIEM', 'Thuê xe máy gần ga Hà Nội: lấy xe sớm nhất lúc nào',
      'Tìm nơi và cách thuê xe máy gần ga Hà Nội',
      'thuê xe máy gần ga hà nội',
      ['thuê xe gần ga hà nội giờ mở', 'lấy xe sớm gần ga'],
      ['/blog/thue-xe/thu-tuc/', '/blog/bang-gia/'],
      'địa điểm ga', 'khách du lịch', 'ga hà nội', 1100, 80, 90, 75, 82, 10),
    R('C-THUE-DIA-DIEM', 'Đi sân bay Nội Bài: nên thuê xe máy từ đâu và lúc nào',
      'Tư vấn quyết định thuê xe máy khi đi sân bay Nội Bài',
      'thuê xe máy đi sân bay nội bài',
      ['đi nội bài bằng xe máy', 'gửi xe ở nội bài'],
      ['/blog/thue-xe/thue-theo-dia-diem/', '/blog/thue-xe/thue-ngay/'],
      'địa điểm sân bay', 'khách du lịch', 'nội bài', 1300, 85, 92, 80, 80, 12),
    R('C-THUE-DIA-DIEM', 'Thuê xe máy gần bến xe Mỹ Đình: những điều cần biết',
      'Tìm cách thuê xe máy gần bến xe Mỹ Đình',
      'thuê xe máy gần bến xe mỹ định',
      ['bến xe mỹ định có thuê xe không', 'lấy xe gần bến mỹ định'],
      ['/blog/thue-xe/thu-tuc/'],
      'địa điểm bến xe', 'khách công tác', 'bến xe mỹ định', 1100, 75, 90, 75, 78, 12),
    R('C-THUE-DIA-DIEM', 'Thuê xe máy gần bến xe Giáp Bát cho chuyến về tỉnh',
      'Tìm cách thuê xe gần bến xe Giáp Bát',
      'thuê xe máy gần bến xe giáp bát',
      ['bến giáp bát thuê xe máy'],
      ['/blog/thue-xe/thu-tuc/'],
      'địa điểm bến xe', 'khách công tác', 'bến giáp bát', 1000, 70, 88, 70, 70, 15),
    R('C-THUE-DIA-DIEM', 'Thuê xe máy ở khu phố cổ: giữ xe và đường cấm cần biết',
      'Hiểu cách đi và giữ xe máy khi thuê ở phố cổ',
      'thuê xe máy phố cổ hà nội',
      ['đi xe máy trong phố cổ', 'giữ xe ở phố cổ'],
      ['/blog/du-lich/pho-co/', '/blog/ky-nang/cho-do-va-hanh-ly/'],
      'địa điểm phố cổ', 'khách du lịch', 'phố cổ', 1300, 88, 92, 85, 80, 12),
    R('C-THUE-DIA-DIEM', 'Thuê xe máy quanh hồ Gươm dịp cuối tuần',
      'Tìm kinh nghiệm thuê xe máy quanh hồ Gươm',
      'thuê xe máy quanh hồ gươm',
      ['đi xe quanh hồ gươm cuối tuần'.replace('cuối tuần', 'cuối tuần'), 'thuê xe gần hồ gươm'],
      ['/blog/du-lich/pho-co/', '/blog/cung-duong/cung-duong-noi-thanh/'],
      'địa điểm hồ gươm', 'khách du lịch', 'hồ gươm', 1100, 78, 90, 75, 78, 12),
    R('C-THUE-DIA-DIEM', 'Chạy vòng hồ Tây bằng xe máy thuê: cung đường và điểm dừng',
      'Tìm cung đường chạy vòng hồ Tây bằng xe máy',
      'chạy vòng hồ tây bằng xe máy',
      ['cung đường hồ tây', 'đi xe quanh hồ tây'],
      ['/blog/du-lich/ho-tay/', '/blog/cung-duong/cung-duong-noi-thanh/'],
      'địa điểm hồ tây', 'khách du lịch', 'hồ tây', 1200, 82, 90, 80, 75, 10),
    R('C-THUE-DIA-DIEM', 'Thuê xe máy ở khu Long Biên, ven sông Hồng',
      'Tìm kinh nghiệm thuê xe ở khu Long Biên ven sông',
      'thuê xe máy long biên',
      ['đi xe ven sông hồng', 'cầu long biên đi xe máy'],
      ['/blog/du-lich/long-bien/', '/blog/thue-xe/thue-theo-dia-diem/'],
      'địa điểm long biên', 'người đi làm', 'long biên', 1100, 75, 90, 75, 72, 12),
    R('C-THUE-DIA-DIEM', 'Thuê xe máy khu vực Gia Lâm, phía Đông Hà Nội',
      'Tìm cách thuê xe máy ở phía Đông Hà Nội',
      'thuê xe máy gia lâm',
      ['thuê xe phía đông hà nội'],
      ['/blog/thue-xe/thue-theo-dia-diem/'],
      'địa điểm gia lâm', 'người đi làm', 'gia lâm', 1000, 72, 88, 72, 70, 15),

    # ============ C-XE-LUA-CHON: chọn loại xe
    R('C-XE-LUA-CHON', 'Xe số hay xe ga cho người mới biết lái khi thuê',
      'So sán xe số và xe ga cho người mới'.replace('So sán', 'So sánh'),
      'xe số hay xe ga cho người mới',
      ['người mới nên thuê xe số hay ga', 'xe số dễ lái hơn xe ga'],
      ['/blog/xe-may/xe-so/', '/blog/xe-may/xe-ga/', '/blog/hoi-dap/hoi-dap-nguoi-moi/'],
      'chọn loại xe', 'người mới', 'hà nội', 1300, 90, 92, 85, 82, 10),
    R('C-XE-LUA-CHON', 'Thuê xe điện hay xe xăng khi đi trong nội đô Hà Nội',
      'So sánh xe điện và xe xăng khi thuê đi nội đô',
      'thuê xe điện hay xe xăng',
      ['xe điện thuê nội đô', 'xe xăng hay xe điện trong thành phố'],
      ['/blog/xe-may/xe-dien/', '/blog/xe-may/so-sanh-xe/'],
      'chọn loại xe', 'người đi làm', 'nội thành', 1400, 88, 92, 85, 82, 8),
    R('C-XE-LUA-CHON', 'Chưa có bằng lái: thuê xe 50cc hay chờ lấy bằng A1',
      'Tư vấn thuê xe khi chưa có bằng lái xe máy',
      'chưa có bằng lái thuê xe gì',
      ['thuê xe không cần bằng', 'xe 50cc có cần bằng không'],
      ['/blog/xe-may/xe-50cc/', '/blog/an-toan-phap-ly/giay-phep-lai-xe/'],
      'chọn loại xe pháp lý', 'người mới', 'hà nội', 1200, 82, 90, 78, 80, 15, 'REVIEW'),
    R('C-XE-LUA-CHON', 'Chọn xe theo chiều cao: yên xe bao nhiêu là vừa',
      'Tư vấn chọn xe máy thuê theo chiều cao người lái',
      'chọn xe máy theo chiều cao',
      ['yên xe cao thấp', 'xe máy cho người thấp'],
      ['/blog/xe-may/chon-loai-xe/'],
      'chọn loại xe', 'người mới', 'hà nội', 1100, 80, 90, 75, 72, 10),
    R('C-XE-LUA-CHON', 'Thuê xe máy chở người thứ hai cần lưu ý gì',
      'Tìm kinh nghiệm thuê xe khi đi hai người',
      'thuê xe máy chở hai người',
      ['đi xe hai người an toàn', 'chở người ngồi sau'],
      ['/blog/ky-nang/ky-nang-lai-co-ban/'],
      'chọn loại xe', 'cặp đôi', 'hà nội', 1200, 78, 90, 75, 75, 12),
    R('C-XE-LUA-CHON', 'Đi chở hành lý cồng kềnh nên thuê loại xe nào',
      'Tư vấn chọn xe khi cần chở hành lý',
      'thuê xe máy chở hành lý',
      ['chở balo vali trên xe máy', 'xe nào chở đồ tốt'],
      ['/blog/ky-nang/cho-do-va-hanh-ly/'],
      'chọn loại xe', 'khách du lịch', 'hà nội', 1100, 75, 88, 72, 72, 12),
    R('C-XE-LUA-CHON', 'Xe ga tiết kiệm xăng khi đi nội đô là dòng nào',
      'Tìm xe ga tiết kiệm xăng cho thuê đi nội đô',
      'xe ga tiết kiệm xăng nội đô',
      ['xe ga nào ít tốn xăng', 'xe ga rẻ tiền xăng'],
      ['/blog/xe-may/xe-ga/'],
      'chọn loại xe', 'người đi làm', 'nội thành', 1200, 78, 88, 75, 72, 12),
    R('C-XE-LUA-CHON', 'Đi đường trường: thuê xe số hay xe ga',
      'Tư vấn chọn xe cho cung đường trường',
      'đi đường trường thuê xe gì',
      ['xe cho cung đường xa', 'xe số đường trường'],
      ['/blog/cung-duong/cung-duong-pho-bac/', '/blog/xe-may/chon-loai-xe/'],
      'chọn loại xe', 'phượt thủ', 'miền bắc', 1200, 82, 90, 78, 75, 10),
    R('C-XE-LUA-CHON', 'Có nên thuê xe cao cấp khi chỉ đi phố cổ',
      'So sánh nhu cầu thuê xe cao cấp với xe phổ thông trong phố',
      'có nên thuê xe cao cấp sh',
      ['thuê xe sh có đáng', 'xe cao cấp đi phố'],
      ['/blog/xe-may/so-sanh-xe/', '/blog/du-lich/pho-co/'],
      'chọn loại xe', 'khách du lịch', 'phố cổ', 1100, 70, 88, 70, 78, 15),
    R('C-XE-LUA-CHON', 'Mùa mưa lớn nên thuê dòng xe máy nào',
      'Tư vấn chọn xe máy cho mùa mưa Hà Nội',
      'mùa mưa nên thuê xe gì',
      ['xe máy đi mưa', 'chọn xe cho mùa mưa hà nội'],
      ['/blog/ky-nang/thoi-tiet-va-duong-sa/', '/blog/xe-may/chon-loai-xe/'],
      'chọn loại xe', 'người đi làm', 'hà nội', 1100, 75, 88, 72, 72, 12),

    # ============ C-XE-KHAC-PHUC: xử lý sự cố xe thuê
    R('C-XE-KHAC-PHUC', 'Xe máy thuê không nổ máy: xử lý từng bước',
      'Tìm cách xử lý khi xe máy thuê không nổ',
      'xe máy thuê không nổ máy',
      ['xe máy không đề được', 'xe thuê không nổ phải làm sao'],
      ['/blog/thue-xe/su-co/', '/blog/thue-xe/nhan-tra-xe/'],
      'sự cố máy', 'người mới', 'hà nội', 1300, 88, 92, 82, 78, 8),
    R('C-XE-KHAC-PHUC', 'Đang đi xe thuê bị xịt lốp: làm gì ngay',
      'Tìm cách xử lý xịt lốp giữa đường với xe thuê',
      'xe máy bị xịt lốp giữa đường',
      [' vá lốp giữa đường'.strip(), 'xịt bánh xe máy'],
      ['/blog/thue-xe/su-co/'],
      'sự cố lốp', 'người mới', 'hà nội', 1200, 85, 90, 78, 75, 10),
    R('C-XE-KHAC-PHUC', 'Mất chìa khóa xe máy thuê: các bước tiếp theo',
      'Tìm cách xử lý khi mất chìa xe thuê',
      'mất chìa khóa xe máy thuê',
      ['mất chìa xe thuê trách nhiệm', 'làm gì khi mất chìa xe'],
      ['/blog/thue-xe/su-co/', '/blog/thue-xe/dat-coc/'],
      'sự cố chìa khóa', 'khách vãng lai', 'hà nội', 1200, 82, 92, 78, 78, 8),
    R('C-XE-KHAC-PHUC', 'Ắc quy xe thuê yếu, đề không nổ: nhận biết và xử lý',
      'Tìm cách nhận biết ắc quy yếu trên xe thuê',
      'ắc quy xe máy yếu đề không nổ',
      ['dấu hiệu ắc quy yếu', 'xe thuê đề yếu'],
      ['/blog/xe-may/bao-duong-xe/'],
      'sự cố ắc quy', 'người đi làm', 'hà nội', 1200, 78, 90, 75, 70, 10),
    R('C-XE-KHAC-PHUC', 'Xe thuê chết máy khi trời mưa: nguyên nhân thường gặp',
      'Tìm nguyên nhân xe chết máy khi mưa và cách xử lý',
      'xe máy chết máy khi trời mưa',
      ['xe chết máy khi mưa', 'xe vào nước chết máy'],
      ['/blog/ky-nang/thoi-tiet-va-duong-sa/', '/blog/thue-xe/su-co/'],
      'sự cố mưa', 'người đi làm', 'hà nội', 1200, 80, 90, 78, 72, 10),
    R('C-XE-KHAC-PHUC', 'Đèn pha xe thuê không sáng khi đi đêm: kiểm tra gì',
      'Tìm cách kiểm tra đèn khi đi xe thuê ban đêm',
      'đèn pha xe máy không sáng',
      ['đi đêm đèn xe yếu', 'kiểm tra đèn trước khi nhận xe'],
      ['/blog/ky-nang/ky-nang-lai-co-ban/', '/blog/thue-xe/nhan-tra-xe/'],
      'sự cố đèn', 'người mới', 'hà nội', 1100, 72, 88, 70, 68, 12),
    R('C-XE-KHAC-PHUC', 'Xe thuê rung giật khi tăng tốc: có nên tiếp tục đi',
      'Tìm cách đánh giá xe runnng giật khi thuê'.replace('runnng', 'rung'),
      'xe máy rung giật khi tăng tốc',
      ['xe máy rung bất thường', 'xe thuê rung có sao không'],
      ['/blog/xe-may/bao-duong-xe/'],
      'sự cố rung', 'người đi làm', 'hà nội', 1100, 70, 88, 70, 65, 15),
    R('C-XE-KHAC-PHUC', 'Phanh xe thuê yếu và có tiếng kêu: xử lý thế nào',
      'Tìm cách xử lý phanh yếu trên xe thuê',
      'phanh xe máy yếu có tiếng kêu',
      ['phát hiện phanh yếu', 'kiểm tra phanh khi nhận xe'],
      ['/blog/thue-xe/nhan-tra-xe/', '/blog/ky-nang/ky-nang-lai-co-ban/'],
      'sự cố phanh', 'người mới', 'hà nội', 1200, 82, 90, 75, 75, 10),
    R('C-XE-KHAC-PHUC', 'Hết xăng giữa đường với xe thuê: các lựa chọn',
      'Tìm cách xử lý khi hết xăng giữa đường',
      'hết xăng giữa đường làm gì',
      ['xe hết xăng giữa đường', 'mua xăng giữa đường'],
      ['/blog/thue-xe/su-co/'],
      'sự cố xăng', 'người mới', 'hà nội', 1000, 72, 88, 68, 65, 15),
    R('C-XE-KHAC-PHUC', 'Nhận nhầm xe so với xe đã đặt: đổi xe thế nào',
      'Tìm cách xử lý khi nhận nhầm xe thuê',
      'nhận nhầm xe thuê làm sao',
      ['đổi xe sau khi nhận', 'khác xe đã đặt'],
      ['/blog/thue-xe/nhan-tra-xe/', '/blog/thue-xe/thu-tuc/'],
      'sự cố nhận xe', 'khách vãng lai', 'hà nội', 1100, 75, 90, 72, 78, 10),
    R('C-XE-KHAC-PHUC', 'Xe thuê không vừa người: yêu cầu đổi xe đúng cách',
      'Tìm cách đề nghị đổi xe khi xe không vừa'.replace('đề nghị', 'yêu cầu'),
      'đổi xe khi xe thuê không vừa người',
      ['xe quá cao đổi xe', 'yêu cầu đổi xe cửa hàng'],
      ['/blog/xe-may/chon-loai-xe/', '/blog/thue-xe/nhan-tra-xe/'],
      'sự cố đổi xe', 'người mới', 'hà nội', 1000, 72, 88, 68, 72, 12),
    R('C-XE-KHAC-PHUC', 'Khóa cổ xe thuê bị kẹt: không nên tự sửa gì',
      'Tìm cách xử lý khóa cổ xe bị kẹt',
      'khóa cổ xe máy bị kẹt',
      ['khóa xe kẹt không xoay được', 'cổ xe kẹt chìa'],
      ['/blog/thue-xe/su-co/'],
      'sự cố khóa', 'khách vãng lai', 'hà nội', 1000, 70, 88, 65, 68, 15),
    R('C-XE-KHAC-PHUC', 'Xe thuê nóng máy khi leo dốc dài: có đáng lo không',
      'Tìm hiểu hiện tượng nóng máy khi leo dốc với xe thuê',
      'xe máy nóng máy khi leo dốc',
      ['leo dốc xe nóng máy', 'xe máy nóng máy có sao'],
      ['/blog/xe-may/bao-duong-xe/'],
      'sự cố nóng máy', 'phượt thủ', 'miền bắc', 1100, 70, 88, 68, 65, 15),
    R('C-XE-KHAC-PHUC', 'Báo cửa hàng ngay khi nào trong lúc thuê xe',
      'Hiểu quy tắc báo cửa hàng khi gặp sự cố xe thuê',
      'khi nào cần báo cửa hàng thuê xe',
      ['báo chủ xe khi xe hỏng', 'thông báo sự cố khi thuê xe'],
      ['/blog/thue-xe/su-co/', '/blog/thue-xe/nhan-tra-xe/'],
      'giao tiếp sự cố', 'người mới', 'hà nội', 1100, 78, 90, 72, 80, 10),

    # ============ C-XE-SO-SANH: so sánh
    R('C-XE-SO-SANH', 'Honda Wave và Yamaha Sirius: thuê dòng nào',
      'So sánh Wave và Sirius khi thuê',
      'so sánh wave và sirius',
      ['thuê wave hay sirius', 'wave khác sirius thế nào'],
      ['/blog/xe-may/honda-wave/', '/blog/xe-may/yamaha-sirius/'],
      'so sánh model', 'người mới', 'hà nội', 1300, 82, 92, 78, 78, 8),
    R('C-XE-SO-SANH', 'Honda Vision và Honda Air Blade: thuê dòng nào phù hợp',
      'So sánh Vision và Air Blade theo nhu cầu thuê',
      'so sánh vision và air blade',
      ['thuê vision hay air blade', 'vision và air blade khác gì'],
      ['/blog/xe-may/honda-vision/', '/blog/xe-may/honda-air-blade/'],
      'so sánh model', 'người đi làm', 'hà nội', 1300, 82, 92, 78, 78, 8),
    R('C-XE-SO-SANH', 'Thuê theo ngày và thuê theo tuần: chi phí khác nhau thế nào',
      'So sánh chi phí thuê ngày với thuê tuần',
      'thuê xe ngày hay tuần rẻ hơn',
      ['giá thuê theo tuần', 'lợi ích thuê dài ngày'],
      ['/blog/thue-xe/thue-ngay/', '/blog/thue-xe/thue-tuan/', '/blog/bang-gia/'],
      'so sánh thời hạn', 'khách du lịch', 'hà nội', 1200, 85, 92, 78, 82, 8),
    R('C-XE-SO-SANH', 'Thuê xe máy và đi taxi/ứng dụng: chi phí đi lại nội thành',
      'So sánh chi phí thuê xe máy với taxi trong tuần đi làm',
      'thuê xe máy hay taxi rẻ hơn',
      ['chi phí xe máy và taxi', 'đi lại nội thành rẻ nhất'],
      ['/blog/thue-xe/thue-thang/', '/blog/bang-gia/'],
      'so sánh phương tiện', 'người đi làm', 'nội thành', 1400, 88, 92, 82, 82, 10),
    R('C-XE-SO-SANH', 'Thuê theo tháng 3 tháng và 1 tháng: nên chọn kiểu nào',
      'So sánh thuê tháng dài và ngắn về chi phí',
      'thuê xe 3 tháng hay 1 tháng',
      ['thuê dài hạn có rẻ hơn', 'hợp đồng thuê tháng'],
      ['/blog/thue-xe/thue-thang/'],
      'so sánh thời hạn', 'người nước ngoài', 'hà nội', 1200, 78, 90, 75, 78, 12),
    R('C-XE-SO-SANH', 'Mùa cao điểm và mùa thấp điểm: giá thuê khác nhau ra sao',
      'Hiểu biến động giá thuê theo mùa du lịch',
      'giá thuê xe theo mùa',
      ['mùa cao điểm giá thuê', 'dịp lễ giá thuê xe'],
      ['/blog/bang-gia/'],
      'so sánh mùa', 'khách du lịch', 'hà nội', 1100, 78, 90, 72, 78, 10),
    R('C-XE-SO-SANH', 'Giá thuê xe số và xe ga ở Hà Nội chênh nhau bao nhiêu',
      'So sánh giá thuê xe số với xe ga',
      'giá thuê xe số và xe ga',
      ['thuê xe ga đắt hơn xe số', 'chênh lệch giá xe số ga'],
      ['/blog/bang-gia/', '/blog/xe-may/xe-so/', '/blog/xe-may/xe-ga/'],
      'so sánh giá', 'người mới', 'hà nội', 1100, 80, 90, 75, 80, 10),
    R('C-XE-SO-SANH', 'Thuê xe tự lái hay đi xe ôm công nghệ trong nội đô',
      'So sánh thuê tự lái với xe ôm cho nhu cầu đi lại',
      'thuê tự lái hay xe ôm',
      ['tự lái hay đi nhờ', 'chi phí xe ôm mỗi ngày'],
      ['/blog/thue-xe/thue-ngay/'],
      'so sánh phương tiện', 'người đi làm', 'nội thành', 1200, 80, 90, 75, 75, 12),
    R('C-XE-SO-SANH', 'So sánh đặt cọc giữa các hình thức thuê xe máy',
      'So sánh hình thức đặt cọc phổ biến (trung lập, không nêu số tiền)',
      'đặt cọc thuê xe máy các hình thức',
      ['cọc tiền mặt hay giấy tờ', 'đặt cọc thế nào'],
      ['/blog/thue-xe/dat-coc/'],
      'so sánh thủ tục', 'khách vãng lai', 'hà nội', 1100, 75, 90, 72, 78, 12),
    R('C-XE-SO-SANH', 'Chi phí chạy xe điện và xe xăng khi thuê theo tháng',
      'So sánh chi phí vận hành xe điện với xe xăng khi thuê dài hạn',
      'chi phí xe điện và xe xăng',
      ['xe điện tốn bao nhiêu mỗi tháng', 'sạc xe điện chi phí'],
      ['/blog/xe-may/xe-dien/', '/blog/thue-xe/thue-thang/'],
      'so sánh vận hành', 'người đi làm', 'hà nội', 1300, 80, 90, 78, 72, 10),

    # ============ BỔ SUNG CHO CÁC CHILD HIỆN CÓ
    # --- C-THUE-GIA
    R('C-THUE-GIA', 'Dự toán chi phí thuê xe máy cho chuyến 3 ngày 2 đêm',
      'Ước tính chi phí thuê xe máy cho chuyến 3 ngày',
      'chi phí thuê xe máy 3 ngày',
      ['thuê xe 3 ngày bao nhiêu', 'dự toán tiền thuê xe du lịch'],
      ['/blog/bang-gia/', '/blog/thue-xe/thue-ngay/'],
      'dự toán chi phí', 'khách du lịch', 'hà nội', 1200, 82, 90, 78, 80, 10),
    R('C-THUE-GIA', 'Giá thuê xe máy dịp lễ Tết thường thay đổi thế nào',
      'Hiểu biến động giá thuê xe dịp lễ Tết',
      'giá thuê xe máy dịp tết',
      ['thuê xe tết có đắt không', 'lễ tết giá thuê xe'],
      ['/blog/bang-gia/'],
      'giá theo mùa', 'khách du lịch', 'hà nội', 1100, 78, 90, 72, 78, 10),
    R('C-THUE-GIA', 'Cách đọc báo giá thuê xe máy: con số nào là con số thật',
      'Hướng dẫn đọc và so sánh báo giá thuê xe máy',
      'cách đọc báo giá thuê xe máy',
      ['báo giá thuê xe máy', 'giá niêm yết và giá thật'],
      ['/blog/bang-gia/', '/blog/thue-xe/gia-thue/'],
      'giá và niêm yết', 'khách vãng lai', 'hà nội', 1200, 80, 90, 75, 78, 10),
    # --- C-THUE-THU-TUC
    R('C-THUE-THU-TUC', 'Chuẩn bị giấy tờ gì trước khi đến cửa hàng thuê xe',
      'Danh sách giấy tờ cần chuẩn bị khi đi thuê xe máy',
      'giấy tờ cần khi thuê xe máy',
      ['thuê xe cần giấy gì', 'chuẩn bị trước khi thuê xe'],
      ['/blog/thue-xe/thu-tuc/', '/blog/an-toan-phap-ly/giay-to/'],
      'giấy tờ', 'khách vãng lai', 'hà nội', 1100, 85, 90, 78, 82, 8),
    R('C-THUE-THU-TUC', 'Quy trình đặt xe trước qua điện thoại: chốt trước điều gì',
      'Hướng dẫn đặt xe thuê trước qua điện thoại',
      'đặt xe máy thuê trước',
      ['gọi đặt xe trước bao lâu', 'đặt xe điện thoại hỏi gì'],
      ['/blog/thue-xe/thu-tuc/', '/blog/hoi-dap/hoi-dap-thu-tuc/'],
      'đặt trước', 'khách công tác', 'hà nội', 1100, 78, 90, 72, 80, 10),
    R('C-THUE-THU-TUC', 'Nên thử xe như thế nào khi nhận xe máy thuê',
      'Hướng dẫn chạy thử xe trước khi nhận xe thuê',
      'chạy thử xe máy khi nhận xe',
      ['kiểm tra xe trước nhận', 'thử xe trước khi thuê'],
      ['/blog/thue-xe/nhan-tra-xe/'],
      'chạy thử', 'người mới', 'hà nội', 1100, 78, 90, 72, 75, 10),
    # --- C-THUE-NHAN-TRA
    R('C-THUE-NHAN-TRA', 'Checklist nhận xe máy thuê: kiểm tra gì trước khi rời cửa hàng',
      'Danh sách kiểm tra khi nhận xe máy thuê',
      'checklist nhận xe máy thuê',
      ['nhận xe kiểm tra gì', 'bàn giao xe thuê'],
      ['/blog/thue-xe/nhan-tra-xe/'],
      'nhận xe', 'người mới', 'hà nội', 1300, 88, 92, 82, 80, 8),
    R('C-THUE-NHAN-TRA', 'Trả xe thuê sớm hơn dự kiến: hỏi trước điều gì',
      'Hiểu quy định trả xe sớm khi thuê xe máy (trung lập)',
      'trả xe thuê sớm có hoàn tiền không',
      ['trả sớm tiền thuê tính sao', 'hoàn tiền khi trả sớm'],
      ['/blog/thue-xe/nhan-tra-xe/', '/blog/bang-gia/'],
      'trả xe sớm', 'khách công tác', 'hà nội', 1000, 72, 88, 70, 72, 15),
    R('C-THUE-NHAN-TRA', 'Trả xe ngoài giờ mở cửa: cần báo trước thế nào',
      'Hiểu cách sắp xếp trả xe ngoài giờ (trung lập, theo giờ 09:00–21:00)',
      'trả xe ngoài giờ làm sao',
      ['trả xe muộn giờ', 'báo giờ trả xe'],
      ['/blog/thue-xe/nhan-tra-xe/'],
      'trả xe giờ', 'khách vãng lai', 'hà nội', 1000, 70, 88, 68, 72, 15),
    R('C-THUE-NHAN-TRA', 'Chụp lại tình trạng xe khi nhận và khi trả',
      'Hướng dẫn lưu bằng chứng tình trạng xe thuê',
      'chụp ảnh xe khi nhận và trả',
      ['lưu bằng chứng xe thuê', 'chụp xe tránh tranh chấp'],
      ['/blog/thue-xe/nhan-tra-xe/', '/blog/thue-xe/su-co/'],
      'bằng chứng', 'khách vãng lai', 'hà nội', 1100, 78, 90, 72, 78, 10),
    # --- C-THUE-DAT-COC
    R('C-THUE-DAT-COC', 'Đặt cọc khi thuê xe máy: cần hỏi rõ điều gì',
      'Hiểu các điều cần hỏi về đặt cọc khi thuê xe (trung lập)',
      'đặt cọc thuê xe máy hỏi gì',
      ['điều khoản đặt cọc', 'cọc thuê xe máy'],
      ['/blog/thue-xe/dat-coc/'],
      'đặt cọc', 'khách vãng lai', 'hà nội', 1100, 80, 90, 75, 80, 10),
    R('C-THUE-DAT-COC', 'Nhận lại tiền cọc khi trả xe: điều kiện thường gặp',
      'Hiểu điều kiện hoàn cọc khi trả xe thuê (trung lập)',
      'nhận lại tiền cọc khi trả xe',
      ['điều kiện hoàn cọc', 'bị trừ cọc khi nào'],
      ['/blog/thue-xe/dat-coc/', '/blog/thue-xe/nhan-tra-xe/'],
      'hoàn cọc', 'khách vãng lai', 'hà nội', 1100, 78, 90, 75, 80, 12),
    # --- C-THUE-QUOC-TE (legal, source_required khi viết)
    R('C-THUE-QUOC-TE', 'Khách quốc tế thuê xe máy ở Hà Nội cần giấy tờ gì',
      'Tìm yêu cầu giấy tờ cho khách quốc tế thuê xe máy',
      'khách quốc tế thuê xe máy cần gì',
      ['người nước ngoài thuê xe máy hà nội', 'giấy tờ thuê xe quốc tế'],
      ['/blog/thue-xe/khach-quoc-te/', '/blog/an-toan-phap-ly/giay-phep-lai-xe/'],
      'giấy tờ quốc tế', 'khách quốc tế', 'hà nội', 1400, 88, 92, 85, 82, 10, 'REVIEW'),
    R('C-THUE-QUOC-TE', 'International Driving Permit ở Việt Nam: khách quốc tế cần biết gì',
      'Tìm hiểu giá trị IDP khi lái xe máy tại Việt Nam',
      'international driving permit việt nam',
      ['idp lái xe việt nam', 'giấy phép lái quốc tế'],
      ['/blog/thue-xe/khach-quoc-te/', '/blog/an-toan-phap-ly/giay-phep-lai-xe/'],
      'idp', 'khách quốc tế', 'việt nam', 1400, 85, 92, 82, 78, 12, 'REVIEW'),
    R('C-THUE-QUOC-TE', 'Khách quốc tế nên thuê xe số hay xe ga ở Hà Nội',
      'Tư vấn loại xe cho khách quốc tế khi thuê',
      'khách quốc tế thuê xe số hay ga',
      ['người nước ngoài lái xe số', 'xe ga cho khách tây'],
      ['/blog/thue-xe/khach-quoc-te/', '/blog/xe-may/chon-loai-xe/'],
      'loại xe quốc tế', 'khách quốc tế', 'hà nội', 1200, 75, 88, 75, 72, 12),
    R('C-THUE-QUOC-TE', 'Giao tiếp với cửa hàng khi không nói tiếng Việt',
      'Hướng dẫn khách quốc tế trao đổi khi thuê xe',
      'thuê xe máy khi không nói tiếng việt',
      ['giao tiếp thuê xe quốc tế', 'thuật ngữ thuê xe tiếng anh'],
      ['/blog/thue-xe/khach-quoc-te/', '/blog/thue-xe/thu-tuc/'],
      'giao tiếp', 'khách quốc tế', 'hà nội', 1100, 72, 88, 70, 72, 15),
    # --- C-THUE-SU-CO
    R('C-THUE-SU-CO', 'Xe thuê hỏng giữa chuyến đi: trách nhiệm thuộc về ai',
      'Hiểu trách nhiệm khi xe thuê hỏng giữa chuyến',
      'xe thuê hỏng giữa đường trách nhiệm',
      ['xe hỏng ai chịu', 'sửa xe thuê ai trả tiền'],
      ['/blog/thue-xe/su-co/'],
      'trách nhiệm hỏng', 'khách vãng lai', 'hà nội', 1300, 85, 92, 80, 80, 10, 'REVIEW'),
    R('C-THUE-SU-CO', 'Tai nạn nhẹ với xe thuê: các bước xử lý ngay',
      'Hướng dẫn xử lý tai nạn nhẹ với xe máy thuê',
      'tai nạn nhẹ với xe thuê',
      ['va quẹt xe thuê làm sao', 'xử lý tai nạn nhẹ'],
      ['/blog/thue-xe/su-co/', '/blog/an-toan-phap-ly/quy-dinh-giao-thong/'],
      'tai nạn', 'người mới', 'hà nội', 1300, 82, 92, 78, 78, 10, 'REVIEW'),
    R('C-THUE-SU-CO', 'Xe thuê bị mất trộm: trình tự cần làm',
      'Tìm trình tự xử lý khi xe thuê bị mất trộm',
      'xe thuê bị mất trộm làm gì',
      ['mất xe thuê trách nhiệm', 'báo công an khi mất xe'],
      ['/blog/thue-xe/su-co/', '/blog/thue-xe/dat-coc/'],
      'mất trộm', 'khách vãng lai', 'hà nội', 1200, 80, 92, 75, 80, 10, 'REVIEW'),
    # --- P-PHAP-LY children (source_required=true)
    R('C-GPLX', 'Bằng lái A1 điều khiển xe máy: phạm vi nào',
      'Tìm hiểu phạm vi bằng A1 với xe máy',
      'bằng a1 lái được xe nào',
      ['bằng a1 dưới 175cc', 'a1 chạy xe bao nhiêu cc'],
      ['/blog/an-toan-phap-ly/giay-phep-lai-xe/'],
      'phạm vi bằng', 'người mới', 'việt nam', 1100, 80, 90, 75, 70, 10, 'REVIEW'),
    R('C-GPLX', 'Đổi bằng lái nước ngoài sang bằng Việt Nam: hướng dẫn cơ bản',
      'Tìm quy trình đổi bằng lái nước ngoài',
      'đổi bằng lái nước ngoài sang việt nam',
      ['đổi bằng lái cho người nước ngoài', 'thủ tục đổi bằng lái'],
      ['/blog/an-toan-phap-ly/giay-phep-lai-xe/', '/blog/thue-xe/khach-quoc-te/'],
      'đổi bằng', 'người nước ngoài', 'việt nam', 1400, 82, 92, 80, 72, 10, 'REVIEW'),
    R('C-PHAT-NGUOI', 'Không mang bằng lái khi đang đi xe: có bị xử lý không',
      'Tìm hậu quả khi không mang bằng khi lái xe',
      'không mang bằng lái bị làm sao',
      ['quên bằng lái khi đi xe', 'không có bằng bị bắt'],
      ['/blog/an-toan-phap-ly/giay-phep-lai-xe/', '/blog/an-toan-phap-ly/phat-nguoi/'],
      'xử lý vi phạm', 'người đi làm', 'việt nam', 1100, 80, 90, 72, 72, 12, 'REVIEW'),
    R('C-NOI-DO-CONG', 'Mũ bảo hiểm đạt chuẩn khi đi xe máy: chuẩn nào',
      'Tìm hiểu chuẩn mũ bảo hiểm hợp lệ ở Việt Nam',
      'mũ bảo hiểm đạt chuẩn',
      ['mũ bảo hiểm chuẩn việt nam', 'mũ bảo hiểm khi thuê xe'],
      ['/blog/an-toan-phap-ly/noi-do-cong/', '/blog/ky-nang/ky-nang-lai-co-ban/'],
      'mũ bảo hiểm', 'người mới', 'việt nam', 1200, 82, 92, 75, 70, 10, 'REVIEW'),
    R('C-BAO-HIEM', 'Bảo hiểm trách nhiệm dân sự với xe máy: khách thuê cần biết gì',
      'Tìm hiểu bảo hiểm bắt buộc với xe máy khi thuê',
      'bảo hiểm xe máy khi thuê',
      ['bảo hiểm trách nhiệm dân sự xe máy', 'xe thuê có bảo hiểm không'],
      ['/blog/an-toan-phap-ly/bao-hiem/', '/blog/thue-xe/su-co/'],
      'bảo hiểm', 'khách vãng lai', 'việt nam', 1300, 82, 92, 78, 75, 10, 'REVIEW'),
    R('C-QUY-DINH', 'Nồng độ cồn khi lái xe máy: quy định hiện hành cần nguồn chính thống',
      'Tìm quy định nồng độ cồn khi lái xe máy (cần nguồn chính thống)',
      'nồng độ cồn khi lái xe máy',
      ['quy định rượu bia lái xe', 'nồng độ cồn xe máy quy định'],
      ['/blog/an-toan-phap-ly/quy-dinh-giao-thong/'],
      'nồng độ cồn', 'người đi làm', 'việt nam', 1200, 85, 92, 80, 70, 10, 'REVIEW'),
    # --- P-DU-LICH
    R('C-DIEM-DEN', 'Lịch trình nửa ngày đi Hà Nội bằng xe máy: chọn lộ trình theo giờ',
      'Tìm lịch trình nửa ngày tham quan Hà Nội bằng xe máy',
      'lịch trình nửa ngày hà nội xe máy',
      ['đi đâu trong nửa ngày hà nội', 'lộ trình nửa ngày'],
      ['/blog/du-lich/diem-den/', '/blog/cung-duong/cung-duong-noi-thanh/'],
      'lịch trình', 'khách du lịch', 'nội thành', 1400, 85, 92, 82, 78, 10),
    R('C-DIEM-DEN', 'Ẩm thực Hà Nội theo cung đường xe máy: đi đâu ăn gì',
      'Tìm cung đường ẩm thực Hà Nội khi đi xe máy',
      'ẩm thực hà nội theo cung đường',
      ['đi ăn gì ở hà nội bằng xe máy', 'food tour hà nội xe máy'],
      ['/blog/du-lich/diem-den/', '/blog/du-lich/pho-co/'],
      'ẩm thực', 'khách du lịch', 'nội thành', 1400, 85, 92, 82, 75, 12),
    R('C-BAO-TANG', 'Ghé bảo tàng Hà Nội bằng xe máy: giữ xe ở đâu',
      'Tìm thông tin đi bảo tàng Hà Nội bằng xe máy',
      'bảo tàng hà nội đi xe máy',
      ['giữ xe bảo tàng hà nội', 'đi bảo tàng bằng xe'],
      ['/blog/du-lich/bao-tang/', '/blog/ky-nang/cho-do-va-hanh-ly/'],
      'bảo tàng', 'khách du lịch', 'nội thành', 1100, 72, 88, 70, 70, 12),
    R('C-PHO-CO', 'Lái xe trong phố cổ giờ cấm: cần biết gì trước khi đi',
      'Tìm hiểu giờ cấm xe trong phố cổ Hà Nội (cần nguồn chính thống)',
      'đường phố cổ cấm xe máy',
      ['giờ cấm xe phố cổ', 'đi xe trong khu phố cổ'],
      ['/blog/du-lich/pho-co/', '/blog/an-toan-phap-ly/quy-dinh-giao-thong/'],
      'giờ cấm', 'khách du lịch', 'phố cổ', 1200, 82, 92, 78, 75, 12, 'REVIEW'),
    R('C-HO-TAY', 'Cung đường chạy quanh hồ Tây: điểm dừng và chỗ gửi xe',
      'Tìm cung đường chạy quanh hồ Tây',
      'cung đường quanh hồ tây',
      ['chạy xe vòng hồ tây', 'điểm dừng hồ tây'],
      ['/blog/du-lich/ho-tay/', '/blog/cung-duong/cung-duong-noi-thanh/'],
      'cung đường', 'khách du lịch', 'hồ tây', 1200, 78, 90, 75, 72, 10),
    R('C-LONG-BIEN', 'Cầu Long Biên và đường ven sông: trải nghiệm đi xe máy',
      'Tìm trải nghiệm đi xe máy qua cầu Long Biên và ven sông',
      'cầu long biên đi xe máy',
      ['đi xe qua cầu long biên', 'đường ven sông hồng'],
      ['/blog/du-lich/long-bien/', '/blog/cung-duong/cung-duong-noi-thanh/'],
      'cung đường', 'khách du lịch', 'long biên', 1200, 78, 90, 75, 72, 10),
    R('C-NGOAI-THANH', 'Đi xe máy ra ngoại thành Hà Nội cuối tuần: chọn hướng nào',
      'Tìm hướng đi ngoại thành Hà Nội cuối tuần bằng xe máy',
      'đi ngoại thành hà nội bằng xe máy',
      ['chơi gì ngoại thành hà nội', 'cuối tuần ngoại thành'],
      ['/blog/du-lich/ngoai-thanh/', '/blog/cung-duong/cung-duong-cuoi-tuan/'],
      'ngoại thành', 'cặp đôi', 'ngoại thành', 1300, 78, 90, 75, 72, 10),
    # --- P-CUNG-DUONG
    R('C-CD-CUOI-TUAN', 'Hà Nội đi Tam Cốc Tràng An bằng xe máy: cung đường và thời gian',
      'Tìm cung đường Hà Nội đi Tam Cốc Tràng An bằng xe máy',
      'hà nội đi tràng an bằng xe máy',
      ['cung đường đi tam cốc', 'hà nội ninh bình xe máy'],
      ['/blog/cung-duong/cung-duong-cuoi-tuan/'],
      'cung đường ninh bình', 'phượt thủ', 'ninh bình', 1400, 85, 92, 82, 78, 8),
    R('C-CD-CUOI-TUAN', 'Hà Nội đi Tam Đảo bằng xe máy: lên dốc cần chuẩn bị gì',
      'Tìm cung đường Hà Nội đi Tam Đảo bằng xe máy',
      'hà nội đi tam đảo bằng xe máy',
      ['cung đường tam đảo', 'leo dốc tam đảo'],
      ['/blog/cung-duong/cung-duong-cuoi-tuan/', '/blog/xe-may/chon-loai-xe/'],
      'cung đường tam đảo', 'phượt thủ', 'vĩnh phúc', 1400, 85, 92, 82, 78, 8),
    R('C-CD-CUOI-TUAN', 'Chùa Hương bằng xe máy từ Hà Nội: chuẩn bị trước khi đi',
      'Tìm kinh nghiệm đi chùa Hương bằng xe máy',
      'đi chùa hương bằng xe máy',
      ['hà nội đi chùa hương', 'mùa chùa hương'],
      ['/blog/cung-duong/cung-duong-cuoi-tuan/', '/blog/ky-nang/thoi-tiet-va-duong-sa/'],
      'cung đường hương sơn', 'phượt thủ', 'mỹ đức', 1300, 80, 90, 78, 75, 10),
    R('C-CD-CUOI-TUAN', 'Hà Nội đi Ba Vì cuối tuần bằng xe máy',
      'Tìm cung đường Hà Nội đi Ba Vì bằng xe máy',
      'hà nội đi ba vì bằng xe máy',
      ['leo núi ba vì bằng xe', 'cung đường ba vì'],
      ['/blog/cung-duong/cung-duong-cuoi-tuan/'],
      'cung đường ba vì', 'phượt thủ', 'ba vì', 1300, 78, 90, 78, 72, 10),
    R('C-CD-CUOI-TUAN', 'Đi làng đá Ninh Bình? Không — Đường Lâm từ Hà Nội bằng xe máy'.split(' — ')[1],
      'Tìm cung đường Hà Nội đi làng cổ Đường Lâm',
      'hà nội đi đường lâm bằng xe máy',
      ['làng cổ đường lâm', 'đường lâm đi như nào'],
      ['/blog/cung-duong/cung-duong-noi-thanh/'],
      'cung đường đường lâm', 'cặp đôi', 'sơn tây', 1200, 75, 90, 75, 70, 10),
    R('C-CD-MAI-CHAU', 'Hà Nội đi Mai Châu bằng xe máy: chuẩn bị cung đường',
      'Tìm cung đường Hà Nội đi Mai Châu bằng xe máy',
      'hà nội đi mai châu bằng xe máy',
      ['cung đường mai châu', 'đi mai châu bao lâu'],
      ['/blog/cung-duong/mai-chau/'],
      'cung đường mai châu', 'phượt thủ', 'mai châu', 1400, 85, 92, 82, 78, 8),
    R('C-CD-MOC-CHAU', 'Hà Nội đi Mộc Châu bằng xe máy mùa hoa: lên đường lúc nào',
      'Tìm cung đường Hà Nội đi Mộc Châu',
      'hà nội đi mộc châu bằng xe máy',
      ['cung đường mộc châu', 'mộc châu mùa hoa'],
      ['/blog/cung-duong/moc-chau/'],
      'cung đường mộc châu', 'phượt thủ', 'mộc châu', 1400, 85, 92, 82, 78, 8),
    R('C-CD-HA-GIANG', 'Đi Hà Giang: thuê xe từ Hà Nội hay gửi xe lên rồi thuê tại chỗ',
      'So sánh đi Hà Giang bằng xe thuê từ Hà Nội với thuê tại chỗ',
      'đi hà giang thuê xe ở đâu',
      ['gửi xe lên hà giang', 'thuê xe hà giang hay hà nội'],
      ['/blog/cung-duong/ha-giang/', '/blog/cung-duong/cung-duong-pho-bac/'],
      'quyết định hà giang', 'phượt thủ', 'hà giang', 1400, 85, 92, 82, 78, 10),
    R('C-CD-PHO-BAC', 'Kinh nghiệm chạy các đèo phía Bắc khi thuê xe máy ở Hà Nội',
      'Tìm kinh nghiệm chạy đèo phía Bắc bằng xe máy thuê',
      'chạy đèo phía bắc bằng xe máy',
      ['các đèo phía bắc', 'đèo phía bắc kinh nghiệm'],
      ['/blog/cung-duong/cung-duong-pho-bac/', '/blog/xe-may/chon-loai-xe/'],
      'đèo phía bắc', 'phượt thủ', 'miền bắc', 1500, 85, 92, 85, 75, 8),
    # --- P-KY-NANG
    R('C-KY-NANG-TINH-HUONG', 'Kẹt xe giờ cao điểm nội thành: kỹ năng đi xe máy an toàn',
      'Tìm kỹ năng đi xe máy khi kẹt xe giờ cao điểm',
      'đi xe máy giờ cao điểm',
      ['kỹ năng đi xe khi kẹt xe', 'lái xe trong tắc đường'],
      ['/blog/ky-nang/tinh-huong-giao-thong/', '/blog/ky-nang/ky-nang-lai-co-ban/'],
      'tắc đường', 'người đi làm', 'nội thành', 1200, 85, 92, 80, 78, 8),
    R('C-KY-NANG-TINH-HUONG', 'Đi xe máy qua đoạn ngập nước trong nội đô',
      'Tìm cách đi xe qua đường ngập nước',
      'đi xe máy qua đường ngập',
      ['chạy xe qua chỗ ngập', 'xe máy đi mưa ngập'],
      ['/blog/ky-nang/thoi-tiet-va-duong-sa/'],
      'ngập nước', 'người đi làm', 'nội thành', 1200, 82, 90, 78, 75, 8),
    R('C-KY-NANG-THOI-TIET', 'Mùa mưa Hà Nội: chuẩn bị gì khi đi xe máy thuê',
      'Tìm cách chuẩn bị đi xe máy mùa mưa',
      'đi xe máy mùa mưa chuẩn bị',
      ['đi xe mưa hà nội', 'áo mưa đi xe máy'],
      ['/blog/ky-nang/thoi-tiet-va-duong-sa/', '/blog/xe-may/chon-loai-xe/'],
      'mùa mưa', 'người đi làm', 'hà nội', 1200, 82, 90, 78, 75, 8),
    R('C-KY-NANG-THOI-TIET', 'Nắng nóng mùa hè Hà Nội: đi xe máy cần chú ý gì',
      'Tìm cách đi xe máy trong nắng nóng',
      'đi xe máy mùa hè nắng nóng',
      ['chống nắng khi đi xe', 'nóng bức đi xe máy'],
      ['/blog/ky-nang/thoi-tiet-va-duong-sa/', '/blog/ky-nang/suc-khoe-khi-lai-xe/'],
      'nắng nóng', 'người đi làm', 'hà nội', 1100, 78, 90, 75, 72, 10),
    R('C-KY-NANG-THOI-TIET', 'Trời lạnh đi xe máy sáng sớm ở Hà Nội: chuẩn bị thế nào',
      'Tìm cách chuẩn bị đi xe máy khi trời lạnh',
      'đi xe máy trời lạnh',
      ['chống lạnh khi đi xe', 'mùa đông đi xe máy hà nội'],
      ['/blog/ky-nang/thoi-tiet-va-duong-sa/'],
      'trời lạnh', 'người đi làm', 'hà nội', 1100, 72, 88, 72, 70, 12),
    R('C-KY-NANG-CHO-DO', 'Gửi xe ở khu vực không có bãi giữ xe: phương án nào',
      'Tìm phương án gửi xe khi không có bãi giữ xe',
      'gửi xe khi không có bãi',
      ['không có chỗ gửi xe', 'gửi xe ở khu phố'],
      ['/blog/ky-nang/cho-do-va-hanh-ly/'],
      'gửi xe', 'khách du lịch', 'nội thành', 1100, 75, 90, 72, 70, 12),
    R('C-KY-NANG-GUI-XE', 'Chống trộm xe máy khi thuê: khóa và cách đỗ xe',
      'Tìm cách chống trộm khi dùng xe máy thuê',
      'chống trộm xe máy thuê',
      ['khóa xe chống trộm', 'đỗ xe an toàn'],
      ['/blog/ky-nang/gui-xe-va-giu-xe/', '/blog/thue-xe/su-co/'],
      'chống trộm', 'khách vãng lai', 'hà nội', 1200, 82, 92, 78, 75, 10),
    R('C-KY-NANG-CO-BAN', 'Đề xe và vào số 1: thao tác cơ bản cho người mới',
      'Hướng dẫn thao tác đề xe và vào số cho người mới',
      'cách đề xe số 1',
      ['đề xe máy cho người mới', 'thao tác xe số'],
      ['/blog/ky-nang/ky-nang-lai-co-ban/'],
      'thao tác cơ bản', 'người mới', 'hà nội', 1100, 78, 90, 75, 70, 10),
    R('C-KY-NANG-CO-BAN', 'Lên dốc và xuống dốc bằng xe số khi mới lái',
      'Hướng dẫn lên xuống dốc bằng xe số',
      'lên dốc xe số cách nào',
      ['xia dốc bằng xe số'.replace('xia', 'xuống'), 'kỹ thuật lên dốc'],
      ['/blog/ky-nang/ky-nang-lai-co-ban/'],
      'lên xuống dốc', 'người mới', 'hà nội', 1200, 78, 90, 75, 70, 10),
    R('C-KY-NANG-CO-BAN', 'Quay đầu xe trong ngõ phố cổ: mẹo cho xe máy',
      'Tìm mẹo quay đầu xe máy trong ngõ nhỏ',
      'quay đầu xe trong ngõ nhỏ',
      ['quay xe trong ngõ', 'lùi xe ngõ hẹp'],
      ['/blog/ky-nang/ky-nang-lai-co-ban/', '/blog/du-lich/pho-co/'],
      'quay đầu', 'người mới', 'phố cổ', 1000, 70, 88, 70, 65, 15),
    # --- P-HOI-DAP
    R('C-HD-GIA', 'Thuê xe máy theo ngày: tiền xăng tính thế nào',
      'Tìm hiểu cách tính xăng khi thuê xe theo ngày',
      'thuê xe máy có bao gồm xăng không',
      ['xe thuê đầy bình hay rỗng', 'trả xe bao nhiêu xăng'],
      ['/blog/hoi-dap/hoi-dap-gia/', '/blog/bang-gia/'],
      'faq xăng', 'khách vãng lai', 'hà nội', 1000, 75, 88, 70, 78, 10),
    R('C-HD-THU-TUC', 'Thuê xe máy cần bao nhiêu tuổi',
      'Tìm độ tuổi tối thiểu khi thuê xe máy (trung lập + pháp lý)',
      'thuê xe máy bao nhiêu tuổi',
      ['tuổi tối thiểu thuê xe', 'thuê xe dưới 18 tuổi'],
      ['/blog/hoi-dap/hoi-dap-thu-tuc/', '/blog/an-toan-phap-ly/giay-phep-lai-xe/'],
      'faq tuổi', 'người mới', 'hà nội', 1000, 78, 88, 70, 75, 10, 'REVIEW'),
    R('C-HD-THU-TUC', 'Người khác có thể đến nhận xe thuê thay mình không',
      'Tìm hiểu quy định nhận xe thuê hộ người khác',
      'nhận xe thuê hộ người khác',
      ['đến nhận xe giúp bạn', 'nhận xe thuê thay mặt'],
      ['/blog/hoi-dap/hoi-dap-thu-tuc/'],
      'faq nhận hộ', 'khách vãng lai', 'hà nội', 900, 68, 85, 65, 70, 15),
    R('C-HD-CHON-XE', 'Chỉ đi trong nội thành nên thuê xe máy loại nào',
      'Tư vấn chọn xe máy chỉ đi nội thành',
      'thuê xe máy đi nội thành',
      ['xe nào hợp đi phố', 'xe nhỏ nội đô'],
      ['/blog/hoi-dap/hoi-dap-chon-xe/', '/blog/xe-may/chon-loai-xe/'],
      'faq chọn xe', 'khách du lịch', 'nội thành', 1000, 72, 88, 70, 72, 12),
    R('C-HD-CHON-XE', 'Đi hai người vác balo: thuê xe máy nào vừa',
      'Tư vấn thuê xe khi đi hai người có balo',
      'thuê xe máy đi hai người có balo',
      ['xe máy chở hai người thoải mái', 'chở balo đi phượt'],
      ['/blog/hoi-dap/hoi-dap-chon-xe/', '/blog/ky-nang/cho-do-va-hanh-ly/'],
      'faq chọn xe', 'phượt thủ', 'hà nội', 1000, 70, 88, 68, 70, 15),
    R('C-HD-NGUOI-MOI', 'Lần đầu thuê xe máy: những lỗi người mới hay mắc',
      'Tìm các lỗi thường gặp lần đầu thuê xe',
      'lỗi thường gặp khi thuê xe máy',
      ['lần đầu thuê xe nhớ gì', 'người mới hay quên gì khi thuê'],
      ['/blog/hoi-dap/hoi-dap-nguoi-moi/', '/blog/thue-xe/thu-tuc/'],
      'faq lỗi mới', 'người mới', 'hà nội', 1100, 80, 90, 75, 78, 10),
    R('C-HD-NGUOI-MOI', 'Chưa quen xe ga: làm quen trong 30 phút trước khi lên đường',
      'Hướng dẫn làm quen xe ga nhanh cho người mới',
      'làm quen xe ga nhanh',
      ['chưa đi xe ga bao giờ', 'tập đi xe ga'],
      ['/blog/hoi-dap/hoi-dap-nguoi-moi/', '/blog/xe-may/xe-ga/'],
      'faq xe ga mới', 'người mới', 'hà nội', 1100, 78, 88, 75, 72, 12),
    R('C-HD-SU-CO', 'Xe thuê hỏng giữa đường: gọi ai trước',
      'Tìm trình tự liên hệ khi xe thuê hỏng giữa đường',
      'xe thuê hỏng gọi ai',
      ['số điện thoại cửa hàng khi xe hỏng', 'xe hỏng gọi cứu hộ'],
      ['/blog/hoi-dap/hoi-dap-su-co/', '/blog/thue-xe/su-co/'],
      'faq sự cố', 'người mới', 'hà nội', 900, 72, 88, 68, 80, 10),
    R('C-HD-PHAP-LY', 'Quên bằng lái khi đang đi xe thuê: làm gì ngay',
      'Tìm cách xử lý khi quên bằng lái (cần nguồn chính thống)',
      'quên bằng lái làm sao',
      ['đi xe không mang bằng', 'quên bằng xử lý thế nào'],
      ['/blog/hoi-dap/hoi-dap-phap-ly/', '/blog/an-toan-phap-ly/giay-phep-lai-xe/'],
      'faq quên bằng', 'người đi làm', 'việt nam', 1000, 78, 88, 70, 72, 12, 'REVIEW'),
    # --- model children (góc nhìn riêng trong mỗi child)
    R('C-HONDA-VISION', 'Thuê Honda Vision đi làm nội đô: trải nghiệm thực tế',
      'Tìm trải nghiệm thuê Vision đi làm trong nội đô',
      'trải nghiệm thuê honda vision',
      ['vision đi làm nội đô', 'thuê vision có tốt không'],
      ['/blog/xe-may/honda-vision/', '/blog/thue-xe/thue-thang/'],
      'trải nghiệm model', 'người đi làm', 'nội thành', 1200, 78, 90, 75, 75, 12),
    R('C-HONDA-AIR-BLADE', 'Thuê Honda Air Blade chạy đường trường có đáng không',
      'Đánh giá Air Blade khi thuê chạy cung đường trường',
      'thuê air blade đường trường',
      ['air blade chạy trường', 'air blade có đáng thuê'],
      ['/blog/xe-may/honda-air-blade/', '/blog/cung-duong/cung-duong-pho-bac/'],
      'trải nghiệm model', 'phượt thủ', 'miền bắc', 1200, 78, 90, 75, 72, 12),
    R('C-HONDA-WAVE', 'Thuê Honda Wave cho người mới: vì sao hay được chọn',
      'Tìm lý do Wave phù hợp người mới thuê xe',
      'thuê honda wave cho người mới',
      ['wave cho người mới', 'wave dễ lái'],
      ['/blog/xe-may/honda-wave/', '/blog/hoi-dap/hoi-dap-nguoi-moi/'],
      'trải nghiệm model', 'người mới', 'hà nội', 1100, 75, 88, 72, 72, 12),
    R('C-YAMAHA-SIRIUS', 'Thuê Yamaha Sirius dài hạn: xe số bền cho người đi làm',
      'Tìm đánh giá Sirius khi thuê dài hạn',
      'thuê yamaha sirius dài hạn',
      ['sirius bền không', 'sirius đi làm'],
      ['/blog/xe-may/yamaha-sirius/', '/blog/thue-xe/thue-thang/'],
      'trải nghiệm model', 'người đi làm', 'hà nội', 1100, 72, 88, 72, 70, 12),
    R('C-XE-DIEN', 'Thuê xe điện trong nội đô Hà Nội: những điều cần biết',
      'Tìm những điều cần biết khi thuê xe điện nội đô',
      'thuê xe điện hà nội cần biết',
      ['xe điện nội đô trữigate'.replace('trữigate', 'sạc ở đâu'), 'xe điện chạy được bao xa'],
      ['/blog/xe-may/xe-dien/', '/blog/xe-may/chon-loai-xe/'],
      'xe điện', 'người đi làm', 'nội thành', 1300, 80, 90, 78, 72, 10),
    R('C-XE-50CC', 'Thuê xe 50cc khi chưa có bằng: lưu ý pháp lý',
      'Tìm lưu ý pháp lý khi thuê xe 50cc (cần nguồn chính thống)',
      'thuê xe 50cc chưa có bằng',
      ['xe 50cc cần bằng không', 'pháp lý xe 50cc'],
      ['/blog/xe-may/xe-50cc/', '/blog/an-toan-phap-ly/giay-phep-lai-xe/'],
      'xe 50cc pháp lý', 'người mới', 'việt nam', 1200, 80, 90, 75, 72, 12, 'REVIEW'),
    R('C-XE-SO', 'Ai nên thuê xe số và vì sao',
      'Tư vấn nhóm người phù hợp thuê xe số',
      'ai nên thuê xe số',
      ['ưu điểm xe số', 'xe số cho ai'],
      ['/blog/xe-may/xe-so/', '/blog/xe-may/chon-loai-xe/'],
      'xe số', 'người mới', 'hà nội', 1100, 72, 88, 70, 70, 12),
    R('C-XE-GA', 'Xe ga hay được chọn thuê ở Hà Nội là những dòng nào',
      'Tìm các dòng xe ga phổ biến khi thuê ở Hà Nội',
      'xe ga phổ biến cho thuê hà nội',
      ['dòng xe ga hay thuê', 'xe ga nào phổ biến'],
      ['/blog/xe-may/xe-ga/', '/blog/bang-gia/'],
      'xe ga', 'khách vãng lai', 'hà nội', 1100, 70, 86, 68, 70, 15),
]

# ---------------- ỨNG VIÊN BỊ TỪ CHỐI (lưu vết để báo cáo, KHÔNG vào matrix)
REJECTED_DEMO = [
    {'title': 'Thuê xe máy giá rẻ quận Hoàn Kiếm / Ba Đình / Đống Đa ... (×12 quận)',
     'reason': 'Doorway theo tên quận: cùng bài chỉ đổi tên địa danh — cấm.',
     'scores': {'usefulness': 40, 'distinct_intent': 25, 'depth': 30,
                'business_relevance': 70, 'cannibalization_risk': 85,
                'feasibility': 'BLOCKED'}},
    {'title': 'Thuê Honda Vision giá rẻ / Vision chất lượng / Vision tốt nhất',
     'reason': 'Hoán đổi tính từ quanh một ý định đã có trong child C-HONDA-VISION.',
     'scores': {'usefulness': 45, 'distinct_intent': 20, 'depth': 35,
                'business_relevance': 70, 'cannibalization_risk': 90,
                'feasibility': 'BLOCKED'}},
    {'title': 'Cách thuê xe máy / cách mướn xe máy / cách đi thuê xe máy',
     'reason': 'Xoay từ đồng nghĩa quanh một ý định duy nhất.',
     'scores': {'usefulness': 50, 'distinct_intent': 15, 'depth': 40,
                'business_relevance': 65, 'cannibalization_risk': 92,
                'feasibility': 'BLOCKED'}},
    {'title': 'Top 10 cửa hàng thuê xe máy tốt nhất Hà Nội',
     'reason': 'Template "best X in Y" mỏng + rủi ro bịa xếp hạng — cấm theo quy tắc số 2.',
     'scores': {'usefulness': 60, 'distinct_intent': 55, 'depth': 25,
                'business_relevance': 60, 'cannibalization_risk': 60,
                'feasibility': 'BLOCKED'}},
    {'title': 'Thuê xe máy 24/7 ở Hà Nội',
     'reason': 'Bịa cam kết hoạt động: cửa hàng mở 09:00–21:00 — cấm theo quy tắc số 2.',
     'scores': {'usefulness': 40, 'distinct_intent': 60, 'depth': 20,
                'business_relevance': 50, 'cannibalization_risk': 40,
                'feasibility': 'BLOCKED'}},
    {'title': 'Đặt cọc thuê xe máy chỉ 500.000 đồng',
     'reason': 'Bịa mức phí cố định — tiềm ủi/phí chưa được chủ xe phê duyệt.',
     'scores': {'usefulness': 55, 'distinct_intent': 65, 'depth': 20,
                'business_relevance': 65, 'cannibalization_risk': 50,
                'feasibility': 'BLOCKED'}},
    {'title': 'Mức phạt cụ thể vi phạm nồng độ cồn hiện hành (số tiền chi tiết)',
     'reason': 'Số tiền phạt dễ lỗi thời — cần nguồn chính thống mới được viết; giữ hàng REVIEW chung quy định + yêu cầu nguồn.',
     'scores': {'usefulness': 75, 'distinct_intent': 70, 'depth': 65,
                'business_relevance': 60, 'cannibalization_risk': 30,
                'feasibility': 'BLOCKED'}},
    {'title': 'Hàng loạt FAQ 1 câu hỏi - 1 đoạn trả lời dạng máy',
     'reason': 'Nghìn hàng FAQ gần giống nhau — cấm theo mục 4.',
     'scores': {'usefulness': 35, 'distinct_intent': 30, 'depth': 15,
                'business_relevance': 50, 'cannibalization_risk': 80,
                'feasibility': 'BLOCKED'}},
]


def main():
    cfg = json.load(open(TAX_CONFIG, encoding='utf-8'))
    seed = json.load(open(SEED_PATH, encoding='utf-8'))
    tax = json.load(open('data/content-taxonomy.json', encoding='utf-8'))
    child_ids = {c[0] for c in cfg['children']}
    with open(MATRIX_PATH, encoding='utf-8', newline='') as f:
        mrows = list(csv.DictReader(f))

    # chống trùng với toàn bộ matrix hiện có
    seen_intent, seen_kw, seen_out, seen_slug = set(), set(), set(), set()
    for r in mrows:
        seen_intent.add(norm(r['intent']))
        seen_kw.add(norm(r['primary_keyword']))
        seen_out.add(r['output_path'])
        seen_slug.add(os.path.basename(r['output_path'])[11:-3])
        # chống ăn thịt bài legacy: ý định mới không được trùng tiêu đề chuẩn hoá
        # của bài legacy (title == intent của hàng legacy)
        seen_intent.add(norm(r['title']))
    # chống trùng trong chính seed hiện có
    for cid, spec in seed['children'].items():
        for rw in spec.get('rows', []):
            seen_intent.add(norm(rw['intent']))
            seen_kw.add(norm(rw['kw']))
        for ent in spec.get('entities', []):
            for ang in spec.get('angles', []):
                seen_kw.add(norm(ang['kw'].replace('{e}', ent['name'])))

    # ---- 1. thêm child mới vào taxonomy-config (append, không đổi thứ tự cũ)
    added_children = []
    for ch in NEW_CHILDREN:
        if ch[0] in child_ids:
            continue
        cfg['children'].append(list(ch))
        cfg['quota'][ch[0]] = ch[8]          # quota = planned_target
        child_ids.add(ch[0])
        added_children.append(ch[0])

    # ---- 2. cổng scoring + chống trùng -> ghi vào seed
    accepted, rejected = [], []
    for cand in CANDIDATES:
        sc = cand['scores']
        ok_gate = (sc['usefulness'] >= GATE['usefulness']
                   and sc['distinct_intent'] >= GATE['distinct']
                   and sc['depth'] >= GATE['depth']
                   and sc['cannibalization_risk'] <= GATE['cannibalization']
                   and sc['feasibility'] in FEASIBILITY_OK)
        nid, nkw = norm(cand['intent']), norm(cand['kw'])
        nslug = re.sub(r'\\s+', '-', norm(cand['title']))[:80].strip('-')
        dup = None
        if cand['title'] in LEGACY_DUPLICATE_TITLES:
            dup = 'trùng bài legacy đã có (cannibalization — cấm)'
        elif nid in seen_intent:
            dup = 'intent trùng matrix/seed hiện có'
        elif nkw in seen_kw:
            dup = 'primary_keyword trùng matrix/seed hiện có'
        elif nslug in seen_slug:
            dup = 'slug trùng bài hiện có (trùng URL khi xuất bản)'
        if not ok_gate:
            rejected.append((cand, 'không đạt cổng scoring'))
        elif dup:
            rejected.append((cand, dup))
        else:
            accepted.append(cand)
            seen_intent.add(nid)
            seen_kw.add(nkw)

    # ghi vào seed (idempotent theo title chuẩn hoá)
    def upsert(cid, row):
        spec = seed['children'].setdefault(cid, {'group': '', 'rows': []})
        if 'rows' not in spec:
            spec['rows'] = []   # child dạng entities/angles: bổ sung mục rows riêng
        t = norm(row['title'])
        for rw in spec['rows']:
            if norm(rw['title']) == t:
                return False
        spec['rows'].append({
            'title': row['title'], 'intent': row['intent'], 'kw': row['kw'],
            'kw2': row['kw2'], 'links': row['links'],
            'subtopic': row['subtopic'], 'audience': row['audience'],
            'location_scope': row['location_scope'],
            'word_target': row['word_target'],
            'scores': row['scores'],
        })
        return True

    tax_child = {c['child_id']: c for c in tax['children']}
    n_new = 0
    for cand in accepted:
        if upsert(cand['child_id'], cand):
            n_new += 1
        # đảm bảo child group khớp taxonomy
        cid = cand['child_id']
        if cid in tax_child and not seed['children'][cid].get('group'):
            seed['children'][cid]['group'] = tax_child[cid]['group']

    # group cho child mới theo NEW_CHILDREN
    for ch in NEW_CHILDREN:
        if ch[0] in seed['children'] and not seed['children'][ch[0]].get('group'):
            seed['children'][ch[0]]['group'] = ch[7]

    # dọn hàng từng ghi nhưng bị xếp loại sau (khớp legacy-trùng): giữ seed sạch
    for cid, spec in seed['children'].items():
        spec['rows'] = [r for r in spec.get('rows', [])
                        if r['title'] not in LEGACY_DUPLICATE_TITLES]

    with open(TAX_CONFIG, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write('\n')
    with open(SEED_PATH, 'w', encoding='utf-8') as f:
        json.dump(seed, f, ensure_ascii=False, indent=2)
        f.write('\n')

    # ---- 3. báo cáo (dựa trên TRẠNG THÁI SEED, không phụ thuộc lần chạy —
    # chạy lại vẫn cho report giống hệt)
    accepted_in_seed = []
    for cid, spec in seed['children'].items():
        for rw in spec.get('rows', []):
            if 'scores' in rw:   # hàng do expand-topic-universe ghi
                c = dict(rw)
                c['child_id'] = cid
                accepted_in_seed.append(c)
    write_report(cfg, tax, seed, mrows, accepted_in_seed, rejected, added_children, n_new)
    print('children mới: %d %s' % (len(added_children), added_children))
    print('ứng viên: %d | nhận: %d | từ chối: %d | ghi mới vào seed: %d'
          % (len(CANDIDATES), len(accepted), len(rejected), n_new))
    print('KẾT QUẢ: PASS (idempotent — chạy lại không sinh thêm)')


def write_report(cfg, tax, seed, mrows, accepted, rejected, added_children, n_new):
    import collections
    tax_children = {c['child_id']: c for c in tax['children']}
    tax_parents = {p['parent_id']: p for p in tax['parents']}
    by_child = collections.Counter(c['child_id'] for c in accepted)
    by_parent = collections.Counter(
        tax_children[c['child_id']]['parent_id'] for c in accepted if c['child_id'] in tax_children)
    by_aud = collections.Counter(c['audience'] or '(chung)' for c in accepted)
    by_loc = collections.Counter(c['location_scope'] or '(chung)' for c in accepted)
    by_feas = collections.Counter(c['scores']['feasibility'] for c in accepted)
    legal = collections.Counter(
        (tax_children.get(c['child_id'], {}).get('legal_risk', 'none')) for c in accepted)
    comm = collections.Counter(
        (tax_children.get(c['child_id'], {}).get('commercial_level', '')) for c in accepted)

    # trục location/audience của cả seed cũ + mới để báo cáo phân bố
    cur_rows = len(mrows)
    hard = 10000
    seeded = sum(1 for r in mrows if r['source'].startswith('planned:'))
    legacy = sum(1 for r in mrows if r['source'].startswith('legacy:'))
    editorial_after = sum(c[8] for c in cfg['children'])
    reserved = hard - legacy - seeded - n_new

    L = []
    A = L.append
    A('# Báo cáo vũ trụ chủ đề (topic universe) — mở rộng 10K')
    A('')
    A('Sinh bởi `scripts/factory/expand-topic-universe.py` (idempotent). ')
    A('Mọi ứng viên phải qua cổng scoring và chống trùng máy trước khi vào seed.')
    A('')
    A('## Hiện trạng')
    A('')
    A('| Khái niệm | Giá trị |')
    A('|---|---|')
    A('| HARD_CAPACITY | %d |' % hard)
    A('| CURRENT_ROWS (matrix trước mở rộng) | %d |' % cur_rows)
    A('| CURRENT_SEEDED_ROWS (planned trước mở rộng) | %d |' % seeded)
    A('| Legacy | %d |' % legacy)
    A('| EDITORIAL_TARGET sau mở rộng (tổng planned_target) | %d |' % editorial_after)
    A('| RESERVED_CAPACITY sau mở rộng | %d |' % reserved)
    A('| Ứng viên đề xuất | %d |' % len(CANDIDATES))
    A('| Hàng mở rộng hiện có trong seed | %d |' % len(accepted))
    
    A('| Ứng viên bị từ chối lần chạy gần nhất | %d |' % len(rejected))
    A('| Nhóm bị từ chối làm bằng chứng (luôn từ chối) | %d |' % len(REJECTED_DEMO))
    A('')
    A('Trung thực về con số: %d legacy + EDITORIAL_TARGET %d = %d < HARD_CAPACITY %d. '
      'Taxonomy vẫn không thể đạt 10.000 hàng một cách hợp lệ; phần thiếu tiếp tục là '
      'không gian dành cho chủ đề THẬT sau này. KHÔNG ĐỆM.' % (
          legacy, editorial_after, legacy + editorial_after, hard))
    A('')
    A('## Child mới (thêm vào taxonomy, append — không đổi child cũ)')
    A('')
    A('| child_id | parent | title | slug | planned_target | legal_risk |')
    A('|---|---|---|---|---|---|')
    for ch in NEW_CHILDREN:
        A('| %s | %s | %s | %s | %d | %s |' % (ch[0], ch[1], ch[2], ch[3], ch[8], ch[11]))
    A('')
    A('## Phân bổ hàng chấp nhận')
    A('')
    A('### Theo parent')
    A('')
    A('| Parent | Hàng nhận |')
    A('|---|---|')
    for pid in sorted(by_parent):
        A('| %s (%s) | %d |' % (pid, tax_parents.get(pid, {}).get('title', ''), by_parent[pid]))
    A('')
    A('### Theo child')
    A('')
    A('| Child | Hàng nhận |')
    A('|---|---|')
    for cid in sorted(by_child):
        A('| %s | %d |' % (cid, by_child[cid]))
    A('')
    A('### Theo audience')
    A('')
    A('| Audience | Hàng nhận |')
    A('|---|---|')
    for k in sorted(by_aud):
        A('| %s | %d |' % (k, by_aud[k]))
    A('')
    A('### Theo location_scope')
    A('')
    A('| Location | Hàng nhận |')
    A('|---|---|')
    for k in sorted(by_loc):
        A('| %s | %d |' % (k, by_loc[k]))
    A('')
    A('### Theo commercial_level (kế thừa child)')
    A('')
    A('| Level | Hàng nhận |')
    A('|---|---|')
    for k in sorted(comm):
        A('| %s | %d |' % (k, comm[k]))
    A('')
    A('### Theo legal_risk (kế thừa child)')
    A('')
    A('| legal_risk | Hàng nhận |')
    A('|---|---|')
    for k in sorted(legal):
        A('| %s | %d |' % (k, legal[k]))
    A('')
    A('### Theo feasibility (cổng pháp lý/nguồn)')
    A('')
    A('| feasibility | Hàng nhận |')
    A('|---|---|')
    for k in sorted(by_feas):
        A('| %s | %d |' % (k, by_feas[k]))
    A('')
    A('## Nhóm bị từ chối do trùng lặp cao nhất')
    A('')
    for cand, why in rejected[:20]:
        A('- "%s" — %s' % (cand['title'], why))
    A('')
    A('## Nhóm bị từ chối vĩnh viễn (luôn từ chối, không bao giờ vào matrix)')
    A('')
    A('| Ứng viên mẫu | Lý do | usefulness | distinct | depth | cannibalization |')
    A('|---|---|---|---|---|---|')
    for d in REJECTED_DEMO:
        s = d['scores']
        A('| %s | %s | %d | %d | %d | %d |' % (
            d['title'].replace('|', '/'), d['reason'],
            s['usefulness'], s['distinct_intent'], s['depth'], s['cannibalization_risk']))
    A('')
    A('## Cổng scoring (nội bộ, không phải điểm Google)')
    A('')
    A('| Tiêu chí | Ngưỡng nhận |')
    A('|---|---|')
    A('| Search usefulness | >= %d |' % GATE['usefulness'])
    A('| Distinct intent | >= %d |' % GATE['distinct'])
    A('| Content depth potential | >= %d |' % GATE['depth'])
    A('| Cannibalization risk (nghịch đảo) | <= %d |' % GATE['cannibalization'])
    A('| Source/legal feasibility | PASS hoặc REVIEW (REVIEW = source_required khi viết) |')
    A('')
    A('## Hàng đã vào seed — danh sách đầy đủ')
    A('')
    A('| # | child | title | kw | audience | location | wt | feas |')
    A('|---|---|---|---|---|---|---|---|')
    for i, c in enumerate(accepted, 1):
        A('| %d | %s | %s | %s | %s | %s | %d | %s |' % (
            i, c['child_id'], c['title'], c['kw'], c['audience'] or '-',
            c['location_scope'], c['word_target'], c['scores']['feasibility']))
    A('')
    open(REPORT_PATH, 'w', encoding='utf-8').write('\n'.join(L))
    print('report:', REPORT_PATH)


if __name__ == '__main__':
    main()
