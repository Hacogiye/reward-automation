# UI giai đoạn 1: bảng màu trung tính

- **Task:** giai đoạn 1 của kế hoạch đổi UI sang phong cách chuyên nghiệp/tối giản: bảng màu trung tính, khối hero phẳng, bỏ khung nhật ký kiểu terminal, độ tương phản đạt AA.
- **Loại:** SIMPLE
- **Kết luận:** APPROVE
- **Số vòng tranh luận:** 1. Reviewer kiểm tra lại các bản sửa, sau đó sửa thêm một dòng cho R3.

## Thay đổi
- `style.css`:
  - Màu nhấn xanh dương: #2563eb (sáng) / #3b82f6 (tối). Bỏ màu gold và gradient.
  - Màu chữ phụ là `--tblr-secondary` = #566273 / #a3aebd (đạt AA).
  - Màu biểu đồ lấy từ `--rb-series-1..5`.
  - Khối hero phẳng: số 30px, chữ số đều độ rộng (tabular).
  - Card có viền 1px, không đổ bóng.
  - Icon menu đang chọn trên sidebar dùng #60a5fa.
  - Xóa các biến không còn dùng: `--rb-pc`, `--rb-mobile`, `--rb-offers`, `--rb-hero-*`.
- `index.html` và `i18n.js`: tiêu đề khung nhật ký đổi thành "Nhật ký hoạt động" (EN: "Activity log"); bỏ ba chấm màu và dòng `rewards-bot://`.
- `app.js`: màu biểu đồ (gồm cả biểu đồ so sánh tài khoản) đọc từ biến CSS.
- `cyberpunk.css`:
  - Ba vạch neon ở đầu khung nhật ký được vẽ lại bằng `.log-head::before`.
  - Thêm `--tblr-secondary-rgb` để chữ phụ giữ đúng màu của skin.

## Các phát hiện

| id | reviewer | mức | kết quả | tóm tắt |
|---|---|---|---|---|
| R1 | reviewer | MAJOR | đã sửa | Phần lớn chữ phụ vẫn dùng `--tblr-secondary` của Tabler, dưới AA (3,61:1 ở chế độ tối). |
| R2 | reviewer | MINOR | đã sửa | TC-1.3 chỉ đo phần tử đầu tiên của các selector đã vá, giờ đo mọi phần tử đang hiện và yêu cầu có ít nhất 1 phần tử. |
| R3 | reviewer | MINOR | đã sửa | `!important` chồng lên nhau và ghi đè màu chữ phụ của Cyberpunk; lần đầu sửa còn thiếu `--tblr-secondary-rgb`. |
| R4 | reviewer | MINOR | đã sửa | Icon menu đang chọn trên sidebar tối chỉ đạt 2,39:1, sau khi sửa đạt 4,86:1. |
| R5 | reviewer | MINOR | đã sửa | Biểu đồ so sánh tài khoản còn màu gold viết cứng trong code. |
| R6 | reviewer | MINOR | đã sửa | Cyberpunk mất ba vạch neon ở khung nhật ký và còn sót CSS `.log-dots` không dùng. |

Không còn mục UNRESOLVED.

## Ghi chú nhỏ
- Dưới Cyberpunk, `.hero-state`, `.hero-mini .lbl`, `.goal-eta` và `.form-hint` giờ dùng `--cp-dim` của skin, thay cho màu trắng mờ trước đây. Màu này dễ đọc (khoảng 6:1). Reviewer chấp nhận.
- Chưa ai xem tận mắt khối hero mới và skin Cyberpunk trong cửa sổ app thật. Mọi kiểm tra đều đo màu bằng Edge chạy ẩn.

## Test
- `python -m pytest -q tests`: 121 passed.
- TC-1.1: mọi trang hiển thị ở cả chế độ sáng và tối, không có lỗi console. Đạt.
- TC-1.2: khối hero có `background-image: none`; khung nhật ký không còn `.log-dots` và dòng `rewards-bot://`. Đạt.
- TC-1.3: độ tương phản ≥ 4,5 với mọi phần tử chữ phụ đang hiện (trang tổng quan, nhật ký, cài đặt, hộp thoại tài khoản), và ≥ 3,0 với icon menu đang chọn, ở cả hai chế độ. Đạt.

## Kiểm tra A/B trên tài khoản thật
Không cần, vì thay đổi này chỉ ở giao diện.

## Hỏi site-researcher
Không có.
