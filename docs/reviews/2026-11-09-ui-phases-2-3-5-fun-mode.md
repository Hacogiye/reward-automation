# UI giai đoạn 2, 3, 5: Fun mode, icon nét, Tổng quan và Tài khoản

- **Task:** gộp giai đoạn 2 (setting `fun_mode`), 3 (icon nét Tabler làm mặc định) và 5 (làm lại trang Tổng quan và Tài khoản, cùng các trạng thái trống, lỗi, xóa) của kế hoạch đổi UI sang phong cách chuyên nghiệp/tối giản. Làm tiếp trên giai đoạn 1, phần này cũng chưa commit.
- **Loại:** SIMPLE
- **Kết luận:** APPROVE
- **Số vòng tranh luận:** 1

## Thay đổi
- **Setting `fun_mode`** (bool, mặc định tắt): có trong `DEFAULT_SETTINGS`, `SETTING_SCHEMA`, công tắc `#set-fun-mode` ở mục "Giao diện" và trong `_window_background`.
- **Khi Fun mode tắt (mặc định):**
  - Ẩn Văn phòng và Cyberpunk. Theme `cyberpunk` đã lưu được hiển thị thành tối, nhưng giá trị đã lưu không bị ghi đè.
  - Chỉ dùng icon nét Tabler. Không còn ảnh nào trên trang Tổng quan.
  - "Tiến độ hôm nay" là danh sách task thay cho các con dấu.
  - Streak hiện thành dòng gọn có thanh 7 đoạn. Stamp bonus là một thanh tiến độ.
  - Lịch nhiệt và "Điểm đến từ đâu" được gấp vào mục "Thêm biểu đồ".
- **Khi Fun mode bật:** giao diện giữ nguyên như cũ.
- **Dùng chung cho mọi chế độ:**
  - `stateBlock()` cho trạng thái trống: chưa có tài khoản, lịch sử trống, nhật ký trống.
  - Lỗi khi thao tác hiện thành banner `.alert-danger` (`role="alert"`) và không tự tắt. Toast có `aria-live`.
  - Xóa tài khoản dùng hộp `<dialog>` thay cho `confirm()`.
  - Mỗi dòng tài khoản có nút Chạy và menu ⋮ (Kiểm tra / Đăng nhập / Sửa / Xóa).
  - "Làm tất cả" đổi tên thành "Chạy mọi task một lần" và có dòng giải thích.
- **Văn phòng:** có thêm `Office.setFun(on)`. Khi tắt Fun mode thì nhạc lofi dừng và không tự phát lại khi bấm chuột. Lựa chọn bật nhạc (`officeMusic`) vẫn được giữ.

## Các phát hiện

| id | reviewer | mức | kết quả | tóm tắt |
|---|---|---|---|---|
| R1 | reviewer | MAJOR | đã sửa | Nhạc lofi bỏ qua Fun mode: tự phát khi bấm chuột và không dừng khi tắt Fun mode, trong khi nút tắt nhạc nằm ở trang đã bị ẩn. |
| R2 | reviewer | MAJOR | đã sửa | Sidebar thu gọn đổi giao diện vòng qua cả nút Cyberpunk đang ẩn, nên bị kẹt ở chế độ tối và lưu ngầm theme `cyberpunk`. |
| R3 | reviewer | MINOR | đã sửa | Tắt Fun mode từ hộp cài đặt mở ở Văn phòng thì hộp vẫn mở trên trang Tổng quan. |
| R4 | reviewer | MINOR | đã sửa | Còn sót các chuỗi I18N không dùng sau khi thay trạng thái trống. |

Không còn mục UNRESOLVED.

## Các điểm khác kế hoạch (reviewer chấp nhận)
- "Tiến độ hôm nay" không có dòng Search PC/Mobile, vì hai thanh tiến độ ngay bên dưới đã hiện số này.
- "Thêm biểu đồ" chứa cả "Điểm đến từ đâu", để không bị một card nửa chiều rộng đứng một mình.
- Lỗi khi lưu cài đặt cũng hiện bằng banner.

## Ghi chú nhỏ
- Vẫn còn vibe cũ ở logo huy chương, tên "Rewards Bot" (giai đoạn 8) và nút chọn giao diện ở sidebar (giai đoạn 4).
- Chưa ai bấm thử bật/tắt Fun mode trong cửa sổ pywebview thật.

## Test
- `python -m pytest -q tests`: 137 passed.
- TC-2.1, 2.2, 3.1, 5.1 (`test_fun_off_default_look`): đạt.
- TC-2.3, 3.2 (`test_fun_mode_toggle_without_reload`, có kiểm tra hộp cài đặt đóng và các card trả về `#settings-home`): đạt.
- TC-2.4 (validate `fun_mode` và `_window_background` trong `test_webapp_api.py`): đạt.
- TC-5.2 (trạng thái trống), 5.3 (banner lỗi), 5.4 (hộp xác nhận xóa), 5.5 (menu dòng dùng bằng bàn phím): đạt.
- Test thêm sau review: `test_lofi_follows_fun_mode`, `test_collapsed_theme_cycle_skips_hidden_cyberpunk`. Đạt.
- Test độ tương phản của giai đoạn 1 chạy với cả Fun mode bật và tắt, có kiểm tra không rỗng. Đạt.

## Kiểm tra A/B trên tài khoản thật
Không cần, vì thay đổi này chỉ ở giao diện.

## Hỏi site-researcher
Không có.
