# PROGRESS — MathofPool

## Đang mở
- MVP đã làm xong T1–T4 trên nhánh `feat/mvp` (chưa gộp vào `main`). VIỆC CỦA NGƯỜI DÙNG: chạy `.venv\Scripts\python.exe main.py`, chơi thử, rồi chọn bộ cảm giác bàn (phím 1 Trơn / 2 Vừa / 3 Chậm) và góp ý đồ họa/âm thanh. Chưa ai nghe âm thanh thật: Claude chỉ kiểm bằng test (có tiếng, trong khoảng âm lượng), không nghe được.
- Chưa kiểm trên cửa sổ thật: kéo to/nhỏ cửa sổ, F11 (chỉ test hàm ánh xạ chuột và chụp headless).
- Sau MVP (thứ tự đã chốt ở `GAME_DESIGN.md`): xoáy cao/thấp → luật 8-ball tập một mình → nhập công thức toán.

## Vừa xong
- 2026-10-28 MVP: T1 vật lý thuần + tia ngắm (54 test; chồng lấn bi tệ nhất 4 µm sau khi lặp tách bi 16 lượt, trước đó 300 µm), T2 bàn + kéo thả + cửa sổ co giãn, T3 âm thanh tự tạo + hiệu ứng, T4 menu + vi/en + bảng bên. 109 test; smoke 2 ms/khung (cú phá cũng ~2 ms, ngân sách 16,7 ms).
- 2026-10-28: dựng bộ workflow + hook + cổng `tools/gate.py` (lý do: máy chặn push, commit lên main, cài thư viện ngoài venv).
