# Nhật ký thay đổi

Mỗi phiên bản **bắt buộc** có một mục `## X.Y.Z - YYYY-MM-DD` ở đây trước khi đẩy tag `vX.Y.Z`. Nội dung của mục đó là
ghi chú của GitHub Release, và là danh sách thay đổi mà app hiện cho người dùng khi báo có bản mới. Thiếu mục (hoặc mục
rỗng) thì test và workflow phát hành đều báo lỗi, không có bản phát hành nào được tạo.

Viết cho người dùng: bản mới làm được gì, sửa lỗi gì, người dùng cần làm gì. Không cần liệt kê tên file hay chi tiết code.

## Chưa phát hành
- Giữ ảnh đại diện cũ nếu ảnh thay thế không hợp lệ hoặc không ghi được xuống đĩa.
- Hộp thêm/sửa tài khoản có nhãn email, mật khẩu rõ ràng; nút đổi ảnh dùng được bằng bàn phím. Lỗi được thông báo
  cho trình đọc màn hình, nút Lưu chống bấm lặp và cho phép thử lại khi lưu thất bại.
- Nhật ký chẩn đoán proxy hệ thống không còn hiện user, mật khẩu, đường dẫn hoặc tham số URL.

## 1.8.2 - 2026-11-13
- Sửa lỗi tài khoản mới luôn chạy profile Edge **Default** dù trong cửa sổ **Đăng nhập** bạn đã chuyển sang profile khác
  (vd Profile 2). Giờ đóng cửa sổ đăng nhập xong, bot ghim đúng profile bạn dùng sau cùng và ghi rõ trong nhật ký.
- **Kiểm tra** không còn báo OK nhầm khi profile bot đang dùng chưa đăng nhập trình duyệt mà profile khác thì đã đăng
  nhập; giờ sẽ cảnh báo kèm cách sửa.
- Tài khoản đang bị dùng sai profile: bấm **Đăng nhập**, chuyển sang đúng profile trong cửa sổ Edge rồi đóng hết cửa
  sổ. Từ lần chạy sau bot dùng profile đó.

## 1.8.1 - 2026-11-12
- Dòng **Read to Earn** ở Tổng quan giờ hiện cả khi công tắc Read to Earn đang tắt (ví dụ khi bạn tự đọc báo trên
  điện thoại). Công tắc chỉ quyết định bot có tự đọc báo hay không; tiến độ thì luôn được đọc khi chạy, **Làm mới**
  hoặc **Kiểm tra**.

## 1.8.0 - 2026-11-12
- Theo dõi **Read to Earn** (đọc báo trên app điện thoại) ngay trên Tổng quan: dòng mới trong nhóm **Hoạt động** hiện
  số điểm đã nhận hôm nay (tối đa 30), rê chuột để xem số bài (tối đa 10).
- Số liệu lấy từ máy chủ Microsoft qua API của app điện thoại, cập nhật khi bot chạy và khi bấm **Làm mới** hoặc
  **Kiểm tra** (chỉ đọc, không cộng điểm gì). Đọc báo thật trên điện thoại thì bấm **Làm mới** để thấy số mới.
- Tài khoản không có Read to Earn (tùy quốc gia) sẽ không có dòng này.

## 1.7.3 - 2026-11-12
- Bản thử tự cập nhật, không đổi gì trong app: từ 1.7.2 bấm **Cập nhật ngay** rồi **Khởi động lại để cập nhật**, mở lại
  sẽ thấy 1.7.3 ở **Cài đặt → Giới thiệu**, dữ liệu giữ nguyên.

## 1.7.2 - 2026-11-12
- Sửa lỗi tự cập nhật: bấm **Khởi động lại để cập nhật** giờ cài bản mới thật (trước đó app mở lại vẫn ở bản cũ).
- Đang dùng 1.7.0 hoặc 1.7.1: tải bản này bằng tay một lần (giải nén đè lên thư mục cũ, `data\` được giữ nguyên).
  Từ 1.7.2 trở đi app tự cập nhật.

## 1.7.1 - 2026-11-12
- Bấm **Dừng** sẽ đóng trình duyệt bị treo sau một lúc chờ; tài khoản đang xếp hàng dừng ngay, không phải đợi lượt.
- Tự từ chối banner cookie của Bing trước khi làm Visual Search.
- Trang Văn phòng dùng font pixel VT323 cho chữ trên tường, bảng tên và bong bóng thoại.

## 1.7.0 - 2026-11-12
- App báo khi có phiên bản mới trên GitHub, hiện danh sách thay đổi của mọi bản mới hơn bản đang dùng.
- Bản `.exe`: bấm **Cập nhật ngay** để tải (có kiểm tra SHA-256) và cài bản mới; dữ liệu, cài đặt và phiên đăng nhập
  được giữ nguyên.
- Bật / tắt tự kiểm tra và nút **Kiểm tra ngay** ở **Cài đặt → Giới thiệu**.

## 1.6.0 - 2026-11-12
- Search gõ từ khóa vào ô tìm kiếm của Bing như người thật (tắt được trong Cài đặt).
- Thời gian nghỉ giữa các lượt search phần lớn ngắn, thỉnh thoảng nghỉ lâu.
- Các tài khoản chạy theo thứ tự ngẫu nhiên; lịch tự chạy (`--run-all`, `--checkin`) chờ ngẫu nhiên vài phút rồi mới
  bắt đầu (thêm `--now` để chạy ngay).

## 1.5.0 - 2026-11-12
- Check-in app điện thoại mỗi ngày (giữ chuỗi Bing App Streak), thêm lệnh `--checkin` để đặt lịch check-in riêng.
- Thêm Read to Earn: đọc tối đa 10 bài báo mỗi ngày (30 điểm).
