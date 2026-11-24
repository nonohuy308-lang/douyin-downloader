# Douyin Downloader cho Windows

App tiếng Việt để quét kênh Douyin, chọn video công khai và tải về máy.

## Dùng trên máy khác

1. Vào **Releases**, mở bản **v1.1.0** và tải **Douyin-Downloader.exe**.
2. Mở file trên Windows có Microsoft Edge. Không cần cài Python.
3. Dán link kênh `https://www.douyin.com/user/...` hoặc link chia sẻ `https://v.douyin.com/...`.
4. Bấm **Quét kênh / video**. Nếu được yêu cầu, tự đăng nhập/xác minh trong cửa sổ Edge riêng của app.
5. Chọn video, chọn thư mục lưu rồi bấm **Tải video đã chọn**.

Máy mới dùng phiên đăng nhập riêng. Gói tải xuống không chứa tài khoản, mật khẩu, cookie hay video cá nhân.

## Bộ lọc

- **Lượt thích** là số tim, được trình bày riêng với lượt xem.
- Chỉ lọc **Lượt xem** khi nguồn thực sự cung cấp số liệu đó.
- Dấu **—** là thiếu số liệu, không phải số 0. Khi cả danh sách thiếu dữ liệu, app báo lý do và giữ nguyên lựa chọn.
- **Từ mức này trở lên** bao gồm đúng mức nhập; **Dưới mức này** không bao gồm.
- Bộ lọc chọn các video phù hợp để tải, không ẩn các dòng còn lại.

## Phạm vi và kiểm chứng

- Tải lần lượt, dừng tác vụ, bỏ qua tệp đã có và vượt kiểm tra.
- Giữ chất lượng nguồn tốt nhất tìm được; không nâng độ phân giải.
- Tệp `.pending` chỉ đổi thành `.mp4` sau khi kiểm tra định dạng và giải mã giây đầu.
- Không hỗ trợ bài ảnh, livestream, kênh riêng tư hoặc vượt xác minh. Không cam kết xóa watermark.
- Không gửi link đến dịch vụ phân tích bên ngoài. App liên hệ Douyin và các máy chủ video do trang trả về.

Đã kiểm tra bản Windows với 30 video của một kênh công khai. Một video đã tải thành công: 11,90 giây, 1080 × 1920, H.264/AAC; giải mã toàn bộ hình và tiếng không lỗi. Bộ lọc từ 1.000 lượt thích chọn 3/30 video. Chưa kiểm thử tải toàn bộ kênh hoặc bảo đảm mọi kênh đều hoạt động.

Chỉ tải nội dung bạn có quyền sử dụng. Douyin có thể thay đổi trang hoặc giới hạn truy cập.

## Chạy từ mã nguồn

Cần Python 3.12 đầy đủ Tcl/Tk trên Windows và Microsoft Edge:

```powershell
py -3.12 -m pip install -r requirements.txt
py -3.12 app.py
```

Để đóng gói, chạy `build.ps1` trong PowerShell. File kết quả nằm ở `dist/Douyin-Downloader.exe`.

## Dữ liệu lưu trên máy

- Video mặc định: `Downloads\Douyin-Videos`.
- Phiên trình duyệt: `%LOCALAPPDATA%\DouyinDownloader\BrowserProfile`.

Không tải thư mục phiên trình duyệt lên GitHub hoặc gửi cho người khác vì có thể chứa cookie đăng nhập.

Xem `HUONG-DAN.txt` để biết hướng dẫn chi tiết và các thư viện được dùng.
