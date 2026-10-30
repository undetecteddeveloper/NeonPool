# Đường: Giao diện

Menu, HUD, bố cục bàn, hoạt ảnh, màu, chữ. Mọi chữ qua `i18n.t()`, có cả vi và en.

**Chỉnh nhỏ** (đổi màu, khoảng cách, cỡ chữ ở thành phần có sẵn): làm thẳng như việc vặt, rồi chụp ảnh kiểm.

**Màn hình mới / đổi bố cục / đổi cách hiện thông tin → PHÁC TRƯỚC:**
1. Đọc code vẽ thật của màn đó (`game/render/`, `game/scenes/`) và `lang/*.json`. Phác dựng lại 1:1 phần đã có; chỉ phác phần MỚI.
2. Dựng 2–3 hướng có TÊN ổn định bằng chính code vẽ của game (công tắc trong `tools\shot.py` hoặc cảnh tạm), chụp ảnh từng hướng và từng trạng thái (mặc định, rỗng, lỗi/thua/thắng). Cho người dùng xem ảnh rồi hỏi chọn hướng (CLAUDE.md §1b). Chỉ code hướng được chọn; cảnh tạm xoá sau.
3. Con số/thông tin phụ không đổi việc người chơi làm thì bỏ — bàn bida cần thoáng.
4. Đo thật, không cảm tính: chụp ảnh ở kích thước cửa sổ chuẩn và cỡ nhỏ nhất `config.py` cho phép; chữ không tràn/cắt ở CẢ vi và en (chuỗi en/vi dài ngắn khác nhau); nút bấm đủ lớn để rê chuột trúng; `smoke.py` không tụt dưới 60 FPS (ms/khung ≤ 16).
4b. Vẽ ở ĐỘ PHÂN GIẢI THẬT của cửa sổ (render/view.py `View`); CẤM vẽ lên canvas nhỏ rồi phóng/thu, CẤM phóng sprite lên (bi trang trí cỡ lớn dựng bằng `View.scaled(k)`). Hình trong suốt/viền cong: vẽ lớn rồi thu qua `shrink_pm` + `blit_pm` (BLEND_PREMULTIPLIED) hoặc lớp `Aa`; `pg.draw.circle/rect(border_radius)` trực tiếp lên màn hình = răng cưa. Phông chữ cỡ = cỡ logic × `View.s`. Đã ghi sau lỗi người dùng báo 2026-10-28 (lỗ răng cưa, bi menu mờ). Kiểm: chụp `shot.py --size 1050x590` và phóng một vùng bằng `pg.transform.scale` (không làm mịn) để soi mép.
4c. Phong cách ARCADE 80 / SYNTHWAVE (chốt 2026-10-29, `docs/GAME_DESIGN.md` "Phản hồi lần 5–6"): không viền đen; nét sáng + quầng qua `render/glow.py` và `LOOK`; lơ = đường nét, hồng = đang chọn/đang xảy ra. Phông chỉ từ `render/fonts.py` (Tilt Neon tiêu đề, Chakra Petch chữ thường); đặt chữ bằng `hud.text` (theo chiều cao chữ hoa, `center=True` căn giữa nét chữ): KHÔNG tự cộng trừ px để "căn mắt". Chữ luôn trên mảng nền đặc. Bàn tối giản: thêm chi tiết lên bàn = hướng sản phẩm, phải hỏi. Mọi lớp sáng phải rẻ (vẽ sẵn rồi dán/cuộn/cộng vùng nhỏ); đo ở 1920×1080 VÀ 2560×1440, mỗi cảnh ≤ 16,7 ms/khung.
4d. MỘT chức năng, MỘT thành phần (chốt 2026-10-30, sau khi người dùng phải tự nhắc nhiều lần): hai phần tử cùng chức năng ở hai màn khác nhau (nút đóng bảng, mũi tên bước trước/sau, nút chữ, hàng chọn giá trị, chấm trang, nhãn phím, bảng nổi…) phải cùng thiết kế. Người dùng không soi ra được, nên Claude tự soi:
   - TRƯỚC khi vẽ hay sửa phần tử nào: đọc bảng "Thành phần UI dùng chung" trong `docs/ARCHITECTURE.md` và Grep `game/render/`, `game/scenes/` tìm phần tử CÙNG CHỨC NĂNG ở màn khác (đừng chỉ tìm theo tên hàm — tìm theo việc nó làm). Đã có → gọi lại đúng thành phần đó. Chưa có mà thấy nó sẽ xuất hiện ở ≥2 màn → viết thẳng thành thành phần chung ở `game/render/` (thường `hud.py`), không viết hàm riêng trong file cảnh; thêm dòng vào bảng cùng commit.
   - Chạm tới bản riêng cũ (xem cột "Chưa gom" của bảng) thì gom về thành phần chung trong cùng đợt, nếu việc gom không đổi thứ người chơi thấy. Nếu gom làm hình hiện ra đổi → hướng sản phẩm, hỏi (CLAUDE.md §1b).
   - BẮT BUỘC giống: hình dạng, màu theo trạng thái (thường / rê / bấm / đã chọn), hoạt ảnh (độ phình, nhún, sáng dần, thời lượng), tiếng, phím tắt, chữ (cùng nghĩa thì cùng khoá `i18n`). ĐƯỢC khác: kích cỡ và vị trí theo bố cục từng màn, số lượng, có hay không có phần tử đó.
   - Muốn khác ở điểm bắt buộc → hỏi người dùng (§1b), không tự quyết. Người dùng chốt khác thì ghi vào cột "Khác có chủ ý" của bảng (kèm lý do); điểm chưa ghi ở đó coi như PHẢI giống.
   - Kiểm bằng ảnh: chụp phần tử ở cả hai màn, cùng trạng thái, nhìn cạnh nhau. Báo cáo cuối ghi `Đã đối chiếu <phần tử> với <phần tử tương đương ở màn X>` (hoặc "không có phần tử tương đương").
5. KHÔNG nói "giao diện ổn" khi chưa chụp ảnh và nhìn ảnh. Cảm nhận thẩm mỹ cuối cùng là của người dùng.
6. Kết thúc: `gate.py` đầy đủ; commit `feat/fix(scope): ...`; báo cáo dòng đầu `ĐỦ BƯỚC` / `THIẾU …`, kèm đường dẫn ảnh đã chụp (ảnh nằm ở `tools/_out/<yyyymmdd>-<slug>/`, xoá theo `ops-env.md`).
