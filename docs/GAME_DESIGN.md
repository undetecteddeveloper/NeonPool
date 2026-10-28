# MathofPool — thiết kế đã chốt

Nguồn sự thật cho NỘI DUNG GAME (người dùng THẤY gì). Cách code: `ARCHITECTURE.md`. Đổi mục nào ở đây = hướng sản phẩm → phải hỏi người dùng (CLAUDE.md §5).

## Đã chốt (2026-10-28, người dùng)
| Hạng mục | Quyết định |
|---|---|
| Thể loại | Bida pool 2D nhìn từ trên xuống, pygame-ce, một người chơi |
| Luật | 8-ball (15 bi + bi trắng; bi nguyên 1–7, bi sọc 9–15, bi 8 đánh cuối) |
| Chế độ | Tập một mình: không đối thủ, không lượt; đếm số cú, lỗi chỉ bị phạt nhẹ |
| Chế độ chơi | HAI chế độ (người dùng đổi định hướng 2026-10-28, trước đó là "bản đầu kéo thả, bản sau công thức"): (1) kéo thả kiểu truyền thống; (2) nhập công thức toán để đánh. Cả hai cùng sinh ra `Shot` (ARCHITECTURE.md). Chi tiết chế độ công thức: xem mục "Chế độ công thức" bên dưới |
| Kéo thả | Hướng kéo ngược = hướng đánh; độ dài thanh kéo = lực, CÓ GIỚI HẠN (kéo quá mức tối đa thì thanh không dài thêm) |
| Vật lý | Có xoáy cơ bản: đánh cao/thấp (bi trắng chạy tới/lùi sau va chạm). CHƯA có xoáy ngang |
| Ngôn ngữ | Tiếng Việt + tiếng Anh, đổi được; mặc định tiếng Việt |
| Chỉnh cảm giác | Claude đề xuất 2–3 bộ thông số CÓ TÊN, người dùng chơi thử và chọn |

## Đồ họa, âm thanh, giao diện (chốt 2026-10-28, người dùng)
Ảnh tham khảo phong cách do người dùng đưa: game golf 2D, nền ca-rô hai tông xanh lục, khối/viền ĐEN DÀY bo tròn, bi trắng viền đen, lỗ là hình tròn đen, vạch ngắm vàng-xanh phát sáng, thanh lực dọc bo tròn (nền đen, lõi vàng) ở góc trái. CHỈ lấy phong cách; KHÔNG bắt chước nội dung ảnh (đường nảy băng, khối cản).
| Hạng mục | Quyết định |
|---|---|
| Phong cách | Vector 2D phẳng, viền đen dày kiểu hoạt hình; giao diện tối giản hiện đại |
| Màu | Khung giao diện tối nhẹ (xanh than), mặt bàn xanh lục tươi ca-rô hai tông, viền bàn đen dày, bi màu bão hòa |
| Bi | Màu đặc + viền đen; bi sọc = dải trắng ngang; số nhỏ trong chấm trắng; bi trắng trơn |
| Bàn | Bida chuẩn 6 lỗ (4 góc + 2 giữa), hình chữ nhật, KHÔNG vật cản |
| Vạch ngắm | Sáng, đi từ bi trắng tới điểm chạm ĐẦU TIÊN (bi hoặc băng), kèm mũi tên nhỏ cho hướng bi bị đụng; không dự đoán nảy băng |
| Kéo thả | Kéo lùi từ bi trắng như kéo dây cung; kéo càng xa lực càng mạnh; thanh lực dọc bên trái |
| Lưới toạ độ | Ẩn mặc định, phím G bật/tắt (hệ toạ độ cho chế độ công thức về sau). Tạm: gốc ở TÂM bàn, x sang phải, y hướng LÊN (quy ước toán), đơn vị mét, vạch mờ mỗi 0,1 m — chốt lại khi làm chế độ công thức |
| Âm thanh | Hiệu ứng cơ bản: gậy đánh, bi va (mạnh/nhẹ theo lực), nảy băng, rơi lỗ; KHÔNG nhạc nền; tự tạo bằng mã (nghe hơi "máy", thay file thật được); có tắt tiếng |
| Hiệu ứng | Vừa đủ, tinh tế: bi co nhỏ biến mất khi vào lỗ, vòng gợn nhẹ khi va chạm mạnh, rung rất nhẹ khi phá bi |
| Cửa sổ | Mở ~1280×720, kéo to/nhỏ được, F11 toàn màn hình; hình co theo, giữ đúng tỉ lệ bàn |
| MVP | Menu mở đầu (Chơi / Ngôn ngữ / Thoát) + bàn chơi tự do (15 bi tam giác, kéo thả, va chạm, nảy băng, vào lỗ, bi trắng rơi lỗ thì đặt lại) + bảng bên (số cú, bi còn lại) + phím R chơi lại, M tắt tiếng, G lưới. CHƯA có luật thắng thua, xoáy, công thức |

## Phản hồi sau khi người dùng chơi thử MVP (2026-10-28)
- Đồ họa: phải là vector thật, mịn ở mọi cỡ cửa sổ (laptop HD 1280×720 của người dùng; cửa sổ mở đầu tự vừa màn hình). Đã chuyển sang vẽ ở độ phân giải thật.
- Thanh kéo: dài theo lực, DỪNG ở lực tối đa (không dài vô tận), đổi màu vàng → cam. Thanh lực bên trái vẫn giữ, chờ người dùng quyết (xem câu hỏi).
- Lực tối đa giảm ~28%: `TRON` 8,0 → 5,8 · `VUA` 7,0 → 5,0 · `CHAM` 6,0 → 4,3 m/s. Âm thanh và kéo to/nhỏ cửa sổ: người dùng hài lòng.

## Luật tập một mình (đề xuất theo WPA 8-ball, rút gọn — người dùng duyệt khi làm tính năng luật)
- Bàn "mở" sau cú phá. Bi đầu tiên vào lỗ hợp lệ (nguyên hoặc sọc) quyết định nhóm của người chơi.
- LỖI: bi trắng rơi lỗ; bi nhảy khỏi bàn; cú đánh không chạm bi nào; chạm bi nhóm khác trước; sau khi chạm không có bi nào vào lỗ hay chạm băng.
- Hậu quả lỗi (tập một mình): +1 lỗi trên bảng điểm, bi trắng được đặt lại TỰ DO trên bàn (luật WPA cho "ball in hand" sau lỗi).
- Bi 8 vào lỗ khi còn bi nhóm mình, hoặc vào cùng lúc với lỗi → thua ván (làm lại). Bi 8 vào lỗ sau khi hết nhóm → thắng ván.
- ĐIỂM MỞ (chưa hỏi, chưa cần cho bản đầu): có bắt "chỉ lỗ" cho bi 8 không; bi trắng rơi lỗ khi phá đặt ở đâu (sau dây đầu hay tự do — nguồn khác nhau, xem nguồn).

## Tham chiếu vật lý (hệ số KHỞI ĐẦU để dựng bộ thông số có tên; chưa kiểm cảm giác)
- Độ nảy băng ≈ 0,98 và ma sát trượt bi–băng ≈ 0,14; mô hình băng cứng chỉ đúng tới ≈ 2,5 m/s vận tốc vuông góc băng (Loughborough, xem nguồn).
- Ma sát lăn nhỏ hơn ma sát trượt cỡ chục lần, bậc ≈ 0,01 (Townsend, UIUC).
- Bi trượt rồi chuyển sang lăn tại một điểm xác định: cần trạng thái trượt/lăn cho từng bi nếu có xoáy (đây là chỗ phức tạp nhất của xoáy cơ bản).
- Hệ số bi–bi, ma sát mặt bàn, khối lượng, bán kính: chưa có số trong tra cứu; chọn khi dựng bộ có tên và ghi nguồn vào đây.

## Nguồn tra cứu
- Mathavan, Jackson, Parkin (2014), va chạm bi–bi có ma sát: https://link.springer.com/article/10.1007/s12283-014-0158-y
- Ball behaviour under cushion impacts (Loughborough): https://dspace.lboro.ac.uk/2134/15087
- Pooltool (engine mã nguồn mở, dùng làm tham chiếu): https://pooltool.readthedocs.io/en/latest/autoapi/pooltool/physics/index.html
- Townsend, The Math and Physics of Billiards (UIUC): https://new.math.uiuc.edu/math198/MA198-2003/townsend/math.html
- Tóm tắt luật 8-ball (diễn đàn, CHƯA phải bản WPA chính thức — kiểm lại ở wpapool.com trước khi chốt luật): https://billiards.colostate.edu:443/resource_files/rules_summary.pdf
