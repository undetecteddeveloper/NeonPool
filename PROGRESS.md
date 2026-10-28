# PROGRESS — MathofPool

## Đang mở
- Nhánh `fix/phan-hoi-mvp` (chưa gộp): đã sửa theo phản hồi chơi thử (vẽ ở độ phân giải thật, thanh kéo có giới hạn, bỏ thanh lực trái, đường cong lực, giảm lực tối đa). Người dùng cần chơi lại để xác nhận: hết răng cưa/mờ chưa, lực tối đa mới và đường cong lực có hợp không.
- Chế độ công thức: đã chốt hướng (đường thẳng y = ax + b, hai nút Chơi ở menu). CÒN HỎI người dùng: ô nhập nằm đâu/trông thế nào, có xem trước đường đi không, mức toán, lực nhập kiểu gì, báo lỗi ra sao. Chưa viết code chế độ công thức.
- MVP đã làm xong T1–T4 trên nhánh `feat/mvp` (chưa gộp vào `main`). VIỆC CỦA NGƯỜI DÙNG: chạy `.venv\Scripts\python.exe main.py`, chơi thử, rồi chọn bộ cảm giác bàn (phím 1 Trơn / 2 Vừa / 3 Chậm) và góp ý đồ họa/âm thanh. Chưa ai nghe âm thanh thật: Claude chỉ kiểm bằng test (có tiếng, trong khoảng âm lượng), không nghe được.
- Chưa kiểm trên cửa sổ thật: kéo to/nhỏ cửa sổ, F11 (chỉ test hàm ánh xạ chuột và chụp headless).
- Sau MVP (thứ tự đã chốt ở `GAME_DESIGN.md`): xoáy cao/thấp → luật 8-ball tập một mình → nhập công thức toán.

## Vừa xong
- 2026-10-28 sửa giao diện theo người dùng (nhánh `feat/cong-thuc`, 236 test): bàn vẽ lại theo ảnh tham chiếu (`render/table.py`: gỗ có vân, tấm đồng, nỉ chuyển sắc, băng đệm, kim cương vàng), bỏ ô ca-rô, bóng bi thẳng xuống, thanh kéo chữ nhật góc vuông. Dựng bàn tốn 57 ms ở 1280×720, 103 ms ở 2× (chỉ chạy lúc mở và sau khi đổi cỡ cửa sổ); smoke vẫn 2,4–4,2 ms/khung. Có test đảo ngược: trả bóng về lệch chéo thì test đỏ.
- 2026-10-28 MVP: T1 vật lý thuần + tia ngắm (54 test; chồng lấn bi tệ nhất 4 µm sau khi lặp tách bi 16 lượt, trước đó 300 µm), T2 bàn + kéo thả + cửa sổ co giãn, T3 âm thanh tự tạo + hiệu ứng, T4 menu + vi/en + bảng bên. 109 test; smoke 2 ms/khung (cú phá cũng ~2 ms, ngân sách 16,7 ms).
- 2026-10-28: dựng bộ workflow + hook + cổng `tools/gate.py` (lý do: máy chặn push, commit lên main, cài thư viện ngoài venv).
