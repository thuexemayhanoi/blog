# Nhật ký bảo trì SEO /blog — 24/10/2026

> Đây là **phụ lục sau checkpoint SEO Master 23/10/2026**, không thay thế `checkpoint.json`, `data/content-matrix.csv` hoặc trạng thái FACTORY live. Việc writer W4 của Claude và publisher tiếp tục độc lập.

## Đã merge — SEO-114: tuyên bố phí trả xe muộn chưa xác thực

**Phạm vi theo checkpoint 23/10: 9 trang tĩnh + 14 bài legacy; đã sửa đủ 23/23 tệp được xác định trong kiểm kê này.** Xóa các lời khẳng định mức phí trả muộn 20.000đ/giờ và ngưỡng hơn 6 tiếng tính thêm một ngày khi chưa có trong `data/business-facts.json`. Nội dung thay thế hướng dẫn trả đúng hẹn và xác nhận chi phí phát sinh **nếu có** theo hợp đồng/thỏa thuận; không tự đặt mức phí mới.

| PR | Nội dung | Kết quả |
|---|---|---|
| [#67](https://github.com/thuexemayhanoi/blog/pull/67) | 6 trang tĩnh | MERGED, 24/10 |
| [#68](https://github.com/thuexemayhanoi/blog/pull/68) | 3 trang bảng giá còn lại | MERGED, 24/10 |
| [#70](https://github.com/thuexemayhanoi/blog/pull/70) | 12 bài legacy | MERGED; Quality Gate SUCCESS |
| [#71](https://github.com/thuexemayhanoi/blog/pull/71) | 2 bài legacy cuối | MERGED; Quality Gate SUCCESS |

Các bản sửa **không đổi** frontmatter, slug, permalink, canonical, bài PUBLISHED có evidence, state, matrix, writer registry hoặc workflow. Chưa coi đã live trừ khi GitHub Pages hoàn thành triển khai commit tương ứng. Nếu sau này chủ cửa hàng có chính sách phí muộn chính thức, cần bổ sung vào nguồn sự thật đã duyệt và kiểm lại toàn bộ trang/bài; không khôi phục số tiền cũ từ tài liệu này.

## Đang ở PR — đính chính tên quy chuẩn mũ bảo hiểm

[#72](https://github.com/thuexemayhanoi/blog/pull/72): bổ sung mã `HELMET_QCVN_2021` trong `_data/legal-notices.json` cho bài `BLG-00634`, sửa cách ghi sai quy chuẩn bị thay thế (`QCVN 02:2019/BKHCN` → đúng là `QCVN 2:2008/BKHCN`). Nguồn [Thông tư 04/2021/TT-BKHCN trong Công báo Chính phủ](https://congbao.chinhphu.vn/van-ban/thong-tu-so-04-2021-tt-bkhcn-34048/36343.htm). **Trạng thái tại lúc viết: PR đã tạo, kiểm thử FULL chưa xác nhận SUCCESS, không báo MERGED.** Không đổi nội dung gốc bài hay QA evidence.

## Chưa giải quyết, không tự phá khóa

- **SEO-115:** báo cáo 23/10 ghi 91 bài PUBLISHED có nội dung chưa sửa được: 79 lệch evidence hash và 12 bài title-bound; 68 bài giá cũ đã có `price-notice`. Cần dùng `reattest-legacy-qa.py` có `--approval-ref` và `revise-published.py` trên các trường hợp đạt QA, không sửa trực tiếp `_posts/` hay `data/qa/`.
- **SEO-116:** 21 bài pháp lý lệch evidence, 19 đã có lớp đính chính, hai bài `BLG-00634` và `BLG-00869` còn thiếu lớp tại checkpoint. #72 chỉ xử lý ca 00634 nếu merge. `BLG-00869` còn điểm pháp lý ranh giới đúng 50 cm3 và điều kiện hợp đồng/độ tuổi, phải xác minh và phê duyệt nội dung chính xác trước khi sửa.
- **SEO-101:** 1.410 slug thiếu chữ `đ` giữ nguyên; không đổi URL nếu chưa có hạ tầng 301 thực.
- **SEO-102:** 49 nhóm/107 bài cannibalization đã phân loại intent, chưa gộp/redirect; cần Search Console thật của blog.
- **SEO-103:** tối ưu hiệu suất related-articles hoãn do liên quan build/publisher, không đụng lúc Claude viết bài.
- **SEO-109:** chưa có GSC cho `blog.thuexemaynguyentu.com`. Không phát biểu CTR/vị trí/index dựa vào suy luận.

## Nguyên tắc phối hợp với Claude writer

Không sửa `_drafts/**`, `data/state/**`, `data/content-matrix.csv`, `data/qa/**`, `factory-publish.yml` hoặc `factory-refill.yml` trong luồng bảo trì SEO này. Mọi sửa dữ liệu SEO/tài liệu phải đi qua nhánh và PR; chỉ merge thay đổi template sau khi kiểm thử. Nhật ký này là báo cáo **theo PR có bằng chứng**, không phải tuyên bố đã kiểm tra toàn bộ website hoặc toàn bộ 97 hàng BLOCKED.
