# PROGRESS — MathofPool

## Đang mở
- NHÁNH `feat/ban-moi-8ball` (chưa gộp vào `main`, 178 test, cổng xanh): MVP kéo thả + bàn vẽ lại theo ảnh tham chiếu + luật 8-ball (lỗi, nhóm nguyên/sọc, bi trắng trong tay, bảng kết quả, bảng bên Lỗi/Nhóm). Không còn chế độ công thức.
- VIỆC CỦA NGƯỜI DÙNG: chơi thử bản kéo thả và góp ý: (1) bàn mới, bóng thẳng xuống, thanh kéo vuông có hợp không; (2) luật 8-ball có dễ hiểu không, thông báo lỗi và việc kéo bi trắng sau lỗi có tự nhiên không; (3) lực tối đa và đường cong lực (từ lần trước). Claude chưa nghe âm thanh và chưa thử chuột thật.
- HỎI người dùng khi tới lúc: tên game "MathofPool" và dòng phụ "Bida và những con số" còn nhắc toán; nếu muốn giữ yếu tố toán thì nó nằm ở đâu.
- Việc kế tiếp: xoáy cao/thấp (`Shot.spin` đã có trong hợp đồng, vật lý chưa dùng). Chưa lưu cài đặt (ngôn ngữ, tắt tiếng chỉ trong phiên).
- Nhánh `feat/cong-thuc` (chế độ công thức, 302 test) giữ lại tới khi người dùng nói xoá (hook chặn `git branch -D`: người dùng tự chạy hoặc bảo Claude hướng dẫn). Không gộp vào `main`.
- Ảnh `ban-bida-anh-tham-chieu.webp` và `ban-bida.png` ở thư mục gốc là của bên thứ ba, chỉ để tham khảo, cố ý KHÔNG đưa vào git.

## Vừa xong
- 2026-10-29 chỉnh tinh: tấm đồng/gỗ không còn lòi ra ở khoảng nêm giữa đầu băng bo cong và vành lỗ (lót nền băng sẫm dưới băng, nên tấm đồng chỉ còn nằm trên phần gỗ, băng xanh liền hai bên lỗ giữa như ảnh tham chiếu). Test mới đỏ khi bỏ lớp lót. Ảnh: `tools/_out/backing_mid.png`, `backing_corner.png`, `after2.png`.
- 2026-10-29 sửa theo phản hồi bản 8-ball: thông báo dời xuống dải trống dưới bàn (không còn che bi sát băng trên); lỗ có vành sáng + thành + hố đen lún ra ngoài; thành băng bo cong hai đầu sát lỗ, bóng băng theo đường bo. Test 178 → 185. Dựng bàn 46 ms (cỡ 0,82), 62 ms (1×), 115 ms (2×); smoke 2,1–4,1 ms/khung. Đã chụp ảnh và nhìn: `tools\_outfter.png`, `banner_vi.png`, `banner_en_small.png`, `edge_corner.png`.
- 2026-10-29 bỏ chế độ công thức (người dùng chốt: khó chơi, ít thú vị): gỡ ô nhập, mức toán, Gợi ý, lưới toạ độ (phím G), đường nét đứt; menu còn Chơi / Ngôn ngữ / Thoát. Test 302 → 178 (bỏ các test của phần công thức và mức toán; test luật 8-ball và bàn giữ nguyên). Smoke 2,1–4,7 ms/khung (ngân sách 16,7).
- 2026-10-29 dọn nhánh: `main` = đỉnh `fix/phan-hoi-mvp` (gồm MVP và sửa theo phản hồi); đã xoá `chore/workflow`, `feat/mvp`, `fix/phan-hoi-mvp` bằng `git branch -d` sau khi gộp.
- 2026-10-28 luật 8-ball tập một mình (`rules/eight_ball.py` thuần) + bi trắng trong tay + bảng kết quả; sự kiện va chạm phát từ 0,001 m/s để luật thấy cả cú chạm rất nhẹ (âm thanh vẫn bỏ < 0,05 m/s).
- 2026-10-28 bàn vẽ lại (`render/table.py`): dựng bàn tốn 57 ms ở 1280×720, 103 ms ở 2× (chỉ lúc mở và sau khi đổi cỡ cửa sổ). Có test đảo ngược: bóng lệch chéo thì test đỏ.
- 2026-10-28 sửa phản hồi chơi thử MVP: vẽ ở độ phân giải thật, thanh kéo dừng ở lực tối đa, bỏ thanh lực trái, lực = (kéo/tối đa)², giảm lực tối đa ~28%.
- 2026-10-28 MVP: vật lý thuần + tia ngắm, bàn + kéo thả, âm thanh tự tạo + hiệu ứng, menu vi/en + bảng bên.
- 2026-10-28: bộ workflow + hook + cổng `tools/gate.py` (lý do: máy chặn push, commit lên main, cài thư viện ngoài venv).
