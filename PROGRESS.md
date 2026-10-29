# PROGRESS — NeonPool

## Đang mở
- ĐANG LÀM (nhánh `feat/giao-dien-neon`, tách từ `main`): đổi đồ họa sang neon nền tối + hiệu ứng wave, nâng giao diện theo phong cách neon. Đã xong: cài plugin `frontend-design@claude-plugins-official` (phạm vi dự án, `.claude/settings.json`). CHƯA LÀM: nạp skill vào phiên (phiên đầu không nạp được, chờ người dùng khởi động lại/nạp lại plugin), hỏi người dùng về hướng neon (màu, nơi có wave, mức sáng), phác 2–3 hướng bằng ảnh rồi mới code (ui.md).
- `main` đã có tất cả (gộp 2026-10-29, 205 test, cổng xanh): MVP kéo thả + bàn vẽ lại theo ảnh tham chiếu + luật 8-ball + màn Hướng dẫn chơi. Không còn chế độ công thức.
- NGƯỜI DÙNG đã duyệt bàn mới, lỗ/băng, thông báo và màn Hướng dẫn. Còn mở từ trước: lực tối đa và đường cong lực (từ lần trước). Claude chưa nghe âm thanh và chưa thử chuột thật.
- Đã chốt 2026-10-29: game tên NeonPool (cũ: MathofPool), dòng phụ "Mỗi cú đánh một vệt sáng" / "Every shot leaves a glow". Tên thư mục dự án vẫn là `MathofPool` (đổi thư mục giữa phiên làm hỏng đường dẫn phiên và bộ nhớ Claude; người dùng tự đổi khi muốn).
- Việc kế tiếp: xoáy cao/thấp (`Shot.spin` đã có trong hợp đồng, vật lý chưa dùng). Chưa lưu cài đặt (ngôn ngữ, tắt tiếng chỉ trong phiên).
- Nhánh `feat/cong-thuc` (chế độ công thức, 302 test): `git branch --list` ngày 2026-10-29 không còn thấy trong máy; nếu còn cần bản đó thì phải khôi phục từ reflog, không gộp vào `main`.
- Ảnh `ban-bida-anh-tham-chieu.webp` và `ban-bida.png` ở thư mục gốc là của bên thứ ba, chỉ để tham khảo, cố ý KHÔNG đưa vào git.

## Vừa xong
- 2026-10-29 gộp `feat/ban-moi-8ball` vào `main` (fast-forward) và xoá nhánh bằng `git branch -d`; cổng chạy lại trên `main` xanh.
- 2026-10-29 màn Hướng dẫn chơi (brief `docs/plans/20261029-huong-dan.md`): nút menu + phím H, 6 trang lật, hình là ảnh thật do game vẽ rồi đánh dấu (`scenes/help_pictures.py`, `render/guide_art.py`), vi + en. Test 186 → 205. Khung đầu của mỗi trang làm hình 12–41 ms (trang 1: 158 ms vì dựng bàn; trang phím tắt 715 → 97 ms ở cửa sổ 2× sau khi chỉ vẽ bảng bên thay vì cả bàn); khung thường 1,8 ms. Đã phác 3 bố cục bằng ảnh, người dùng chọn Trang lật. Ảnh: `tools\_out\guide_0..5.png`, `guide_en_1.png`, `guide_en_small_2.png`, `menu_new.png`.
- 2026-10-29 chỉnh tinh: tấm đồng/gỗ không còn lòi ra ở khoảng nêm giữa đầu băng bo cong và vành lỗ (lót nền băng sẫm dưới băng, nên tấm đồng chỉ còn nằm trên phần gỗ, băng xanh liền hai bên lỗ giữa như ảnh tham chiếu). Test mới đỏ khi bỏ lớp lót. Ảnh: `tools/_out/backing_mid.png`, `backing_corner.png`, `after2.png`.
- 2026-10-29 sửa theo phản hồi bản 8-ball: thông báo dời xuống dải trống dưới bàn (không còn che bi sát băng trên); lỗ có vành sáng + thành + hố đen lún ra ngoài; thành băng bo cong hai đầu sát lỗ, bóng băng theo đường bo. Test 178 → 185. Dựng bàn 46 ms (cỡ 0,82), 62 ms (1×), 115 ms (2×); smoke 2,1–4,1 ms/khung. Đã chụp ảnh và nhìn: `tools\_outfter.png`, `banner_vi.png`, `banner_en_small.png`, `edge_corner.png`.
- 2026-10-29 bỏ chế độ công thức (người dùng chốt: khó chơi, ít thú vị): gỡ ô nhập, mức toán, Gợi ý, lưới toạ độ (phím G), đường nét đứt; menu còn Chơi / Ngôn ngữ / Thoát. Test 302 → 178 (bỏ các test của phần công thức và mức toán; test luật 8-ball và bàn giữ nguyên). Smoke 2,1–4,7 ms/khung (ngân sách 16,7).
- 2026-10-29 dọn nhánh: `main` = đỉnh `fix/phan-hoi-mvp` (gồm MVP và sửa theo phản hồi); đã xoá `chore/workflow`, `feat/mvp`, `fix/phan-hoi-mvp` bằng `git branch -d` sau khi gộp.
- 2026-10-28 luật 8-ball tập một mình (`rules/eight_ball.py` thuần) + bi trắng trong tay + bảng kết quả; sự kiện va chạm phát từ 0,001 m/s để luật thấy cả cú chạm rất nhẹ (âm thanh vẫn bỏ < 0,05 m/s).
- 2026-10-28 bàn vẽ lại (`render/table.py`): dựng bàn tốn 57 ms ở 1280×720, 103 ms ở 2× (chỉ lúc mở và sau khi đổi cỡ cửa sổ). Có test đảo ngược: bóng lệch chéo thì test đỏ.
- 2026-10-28 sửa phản hồi chơi thử MVP: vẽ ở độ phân giải thật, thanh kéo dừng ở lực tối đa, bỏ thanh lực trái, lực = (kéo/tối đa)², giảm lực tối đa ~28%.
- 2026-10-28 MVP: vật lý thuần + tia ngắm, bàn + kéo thả, âm thanh tự tạo + hiệu ứng, menu vi/en + bảng bên.
- 2026-10-28: bộ workflow + hook + cổng `tools/gate.py` (lý do: máy chặn push, commit lên main, cài thư viện ngoài venv).
