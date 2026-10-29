# Đường: Giao diện

Menu, HUD, bố cục bàn, hoạt ảnh, màu, chữ. Mọi chữ qua `i18n.t()`, có cả vi và en.

**Chỉnh nhỏ** (đổi màu, khoảng cách, cỡ chữ ở thành phần có sẵn): làm thẳng như việc vặt, rồi chụp ảnh kiểm.

**Màn hình mới / đổi bố cục / đổi cách hiện thông tin → PHÁC TRƯỚC:**
1. Đọc code vẽ thật của màn đó (`game/render/`, `game/scenes/`) và `lang/*.json`. Phác dựng lại 1:1 phần đã có; chỉ phác phần MỚI.
2. Dựng 2–3 hướng có TÊN ổn định bằng chính code vẽ của game (công tắc trong `tools\shot.py` hoặc cảnh tạm), chụp ảnh từng hướng và từng trạng thái (mặc định, rỗng, lỗi/thua/thắng). Cho người dùng xem ảnh rồi hỏi chọn hướng (CLAUDE.md §1b). Chỉ code hướng được chọn; cảnh tạm xoá sau.
3. Con số/thông tin phụ không đổi việc người chơi làm thì bỏ — bàn bida cần thoáng.
4. Đo thật, không cảm tính: chụp ảnh ở kích thước cửa sổ chuẩn và cỡ nhỏ nhất `config.py` cho phép; chữ không tràn/cắt ở CẢ vi và en (chuỗi en/vi dài ngắn khác nhau); nút bấm đủ lớn để rê chuột trúng; `smoke.py` không tụt dưới 60 FPS (ms/khung ≤ 16).
4b. Vẽ ở ĐỘ PHÂN GIẢI THẬT của cửa sổ (render/view.py `View`); CẤM vẽ lên canvas nhỏ rồi phóng/thu, CẤM phóng sprite lên (bi trang trí cỡ lớn dựng bằng `View.scaled(k)`). Hình trong suốt/viền cong: vẽ lớn rồi thu qua `shrink_pm` + `blit_pm` (BLEND_PREMULTIPLIED) hoặc lớp `Aa`; `pg.draw.circle/rect(border_radius)` trực tiếp lên màn hình = răng cưa. Phông chữ cỡ = cỡ logic × `View.s`. Đã ghi sau lỗi người dùng báo 2026-10-28 (lỗ răng cưa, bi menu mờ). Kiểm: chụp `shot.py --size 1050x590` và phóng một vùng bằng `pg.transform.scale` (không làm mịn) để soi mép.
4c. Phong cách NEON (chốt 2026-10-29, `docs/GAME_DESIGN.md` "Phản hồi lần 5"): không viền đen; nét sáng + quầng qua `render/glow.py` và `LOOK`; lơ = đường nét, hồng tím = đang chọn/đang xảy ra; bi tối có vòng và số sáng. Chuyển động CHỈ ở ba chỗ đã chốt (sóng menu/Hướng dẫn, vòng sóng va chạm/rơi lỗ, vệt sáng viền) và bàn đứng yên khi ngắm: thêm chuyển động ở chỗ khác = hướng sản phẩm, phải hỏi. Mọi lớp sáng cộng lên nền tối phải rẻ (dựng sẵn rồi cuộn/cộng vùng nhỏ); đo `smoke.py` ở cửa sổ 2×.
5. KHÔNG nói "giao diện ổn" khi chưa chụp ảnh và nhìn ảnh. Cảm nhận thẩm mỹ cuối cùng là của người dùng.
6. Kết thúc: `gate.py` đầy đủ; commit `feat/fix(scope): ...`; báo cáo dòng đầu `ĐỦ BƯỚC` / `THIẾU …`, kèm đường dẫn ảnh đã chụp.
