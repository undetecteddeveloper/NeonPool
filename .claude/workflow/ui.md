# Đường: Giao diện

Menu, HUD, bố cục bàn, hoạt ảnh, màu, chữ. Mọi chữ qua `i18n.t()`, có cả vi và en.

**Chỉnh nhỏ** (đổi màu, khoảng cách, cỡ chữ ở thành phần có sẵn): làm thẳng như việc vặt, rồi chụp ảnh kiểm.

**Màn hình mới / đổi bố cục / đổi cách hiện thông tin → PHÁC TRƯỚC:**
1. Đọc code vẽ thật của màn đó (`game/render/`, `game/scenes/`) và `lang/*.json`. Phác dựng lại 1:1 phần đã có; chỉ phác phần MỚI.
2. Dựng 2–3 hướng có TÊN ổn định bằng chính code vẽ của game (công tắc trong `tools\shot.py` hoặc cảnh tạm), chụp ảnh từng hướng và từng trạng thái (mặc định, rỗng, lỗi/thua/thắng). Cho người dùng xem ảnh rồi hỏi chọn hướng (CLAUDE.md §1b). Chỉ code hướng được chọn; cảnh tạm xoá sau.
3. Con số/thông tin phụ không đổi việc người chơi làm thì bỏ — bàn bida cần thoáng.
4. Đo thật, không cảm tính: chụp ảnh ở kích thước cửa sổ chuẩn và cỡ nhỏ nhất `config.py` cho phép; chữ không tràn/cắt ở CẢ vi và en (chuỗi en/vi dài ngắn khác nhau); nút bấm đủ lớn để rê chuột trúng; `smoke.py` không tụt dưới 60 FPS (ms/khung ≤ 16).
5. KHÔNG nói "giao diện ổn" khi chưa chụp ảnh và nhìn ảnh. Cảm nhận thẩm mỹ cuối cùng là của người dùng.
6. Kết thúc: `gate.py` đầy đủ; commit `feat/fix(scope): ...`; báo cáo dòng đầu `ĐỦ BƯỚC` / `THIẾU …`, kèm đường dẫn ảnh đã chụp.
