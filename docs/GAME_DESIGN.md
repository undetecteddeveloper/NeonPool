# NeonPool — thiết kế đã chốt

Nguồn sự thật cho NỘI DUNG GAME (người dùng THẤY gì). Cách code: `ARCHITECTURE.md`. Đổi mục nào ở đây = hướng sản phẩm → phải hỏi người dùng (CLAUDE.md §5).

## Đã chốt (2026-10-28, người dùng)
| Hạng mục | Quyết định |
|---|---|
| Thể loại | Bida pool 2D nhìn từ trên xuống, pygame-ce, một người chơi |
| Luật | 8-ball (15 bi + bi trắng; bi nguyên 1–7, bi sọc 9–15, bi 8 đánh cuối) |
| Chế độ | Tập một mình: không đối thủ, không lượt; đếm số cú, lỗi chỉ bị phạt nhẹ |
| Chế độ chơi | MỘT chế độ: kéo thả kiểu truyền thống. Chế độ nhập công thức toán (y = ax + b) đã làm thử rồi BỎ HẲN (người dùng chốt 2026-10-29 sau khi chơi: khó chơi, ít thú vị hơn chơi thường). Mọi cách nhập vẫn chỉ sinh ra `Shot` (ARCHITECTURE.md) |
| Kéo thả | Hướng kéo ngược = hướng đánh; độ dài kéo = lực, CÓ GIỚI HẠN (kéo quá mức tối đa thì không mạnh thêm) |
| Vật lý | Có xoáy cơ bản: đánh cao/thấp (bi trắng chạy tới/lùi sau va chạm). CHƯA có xoáy ngang |
| Ngôn ngữ | Tiếng Việt + tiếng Anh, đổi được; mặc định tiếng Việt |
| Chỉnh cảm giác | Claude đề xuất 2–3 bộ thông số CÓ TÊN, người dùng chơi thử và chọn. Người chơi KHÔNG còn đổi được cảm giác bàn trong game (bỏ phím 1/2/3 và cụm "Cảm giác bàn", 2026-10-29): luôn là "Vừa" |

## Đồ họa, âm thanh, giao diện (bản hiện hành: ARCADE 80 / SYNTHWAVE, 2026-10-29, xem "Phản hồi lần 5" và "lần 6")
Hình học bàn và luật giữ nguyên. Hai phong cách trước đã bị THAY: hoạt hình viền đen (2026-10-28), rồi neon xanh đêm (bản đầu 2026-10-29). Các dòng dưới đây là bản hiện hành.
| Hạng mục | Quyết định |
|---|---|
| Phong cách | Arcade thập niên 80 (synthwave), neon trên nền đêm chàm: mặt trời sọc, lưới chân trời, bảng điểm máy xèng, chữ thông báo arcade, vệt quét CRT rất nhẹ. KHÔNG viền đen. Mức sáng: bộ "Đèn ống" (nét mảnh, quầng hẹp) trong `render/palette.py` (`LOOK`). Chữ: Tilt Neon (ống neon) cho tiêu đề, Chakra Petch (góc cạnh) cho chữ thường, cả hai đủ dấu tiếng Việt; số trên bảng điểm vẽ kiểu đèn 7 đoạn, đoạn tắt vẫn mờ thấy. Chữ đặt theo chiều cao chữ hoa nên dấu không đẩy chữ lệch; chữ luôn nằm trên mảng nền đặc |
| Màu | Xanh lơ `#28F0FF` là đường nét (viền bàn, biên băng, vạch ngắm, số), hồng `#FF2EC4` là thứ đang chọn hoặc đang xảy ra (nút chọn, lỗ, tiêu đề), tím `#8E40FF` nối hai màu; mặt trời vàng → cam → hồng. Nền đêm chàm `#0B051C`; mặt bàn một mảng phẳng `#150A32` |
| Bi | Như bóng đèn: thân tối, vòng và số phát sáng đúng màu bi (1 vàng, 2 xanh dương, 3 đỏ, 4 tím, 5 cam, 6 xanh lục, 7 hồng đậm, 8 bạc); bi sọc có hai đường sáng ngang thân và số trắng; bi trắng là một đĩa sáng. Quầng sáng đều quanh bi, KHÔNG còn bóng đổ (bản cũ: bóng rơi thẳng xuống) |
| Bàn | Bida chuẩn 6 lỗ (4 góc + 2 giữa), hình chữ nhật, KHÔNG vật cản. Vẽ TỐI GIẢN bằng nét neon (người dùng chốt 2026-10-29: chỉ đủ để chơi và nhận biết): một mảng tối phẳng, một vòng lơ ở mép ngoài, một đường lơ ở mép băng (biên chơi, hai đầu cong vào miệng lỗ), sáu vòng hồng là lỗ (trong đen). KHÔNG gỗ, kim cương, bóng băng, độ sâu lỗ |
| Vạch ngắm | Vạch sáng màu lơ đi từ bi trắng tới điểm chạm ĐẦU TIÊN (bi hoặc băng), kèm mũi tên hồng tím nhỏ cho hướng bi bị đụng; không dự đoán nảy băng |
| Kéo thả | Kéo lùi từ bi trắng; kéo càng xa lực càng mạnh. Thấy một CÂY CƠ NEON (thay thanh kéo cũ): rê chuột lên bi trắng thì cơ hiện dần sau bi (0,18 s), rời ra thì mờ dần (0,25 s); khi kéo, cơ lùi theo tay nhưng chỉ 75% quãng kéo (`CUE_SHOW_PULL`; lực KHÔNG đổi); lực thể hiện bằng MÀU, kéo càng căng càng nóng: lơ → tím → hồng → cam → trắng nóng (không vạch); đầu cơ trắng; căng tối đa thì cơ rung nhẹ; thả tay thì cơ lao tới chỗ bi rồi tắt |
| Âm thanh | Tiếng bi: gậy đánh, bi va (mạnh/nhẹ theo lực), nảy băng, rơi lỗ. Tiếng giao diện kiểu arcade (2026-10-29): bíp khi rê sang nút khác, hai nốt khi bấm, chuông nhẹ khi chọn nhóm / tới bi 8, tiếng rè khi lỗi, nhạc 8-bit ngắn khi thắng/thua. KHÔNG nhạc nền; tự tạo bằng mã; M tắt tiếng |
| Hiệu ứng | Bàn ĐỨNG YÊN khi ngắm. (1) Menu và Hướng dẫn: các sợi sóng ở chân trời là mô phỏng sợi dây thật (chuỗi điểm nối lò xo): tự thở, nghiêng theo con trỏ, có nhịp sáng chạy dọc khi chọn nút khác, bật lên như mặt nước khi bấm; lưới chân trời trôi về phía người chơi; sao lấp lánh; sọc mặt trời trượt xuống; tiêu đề chập chờn lúc vào menu rồi thở nhẹ. (2) Vòng sóng khi bi va chạm (lơ), chạm băng (tím), rơi lỗ (hồng, to và lâu hơn). (3) Hai vệt sáng (lơ, hồng) chạy rất chậm ở viền ngoài bàn. (4) Khi bi đã dừng: chữ arcade lớn ("LỖI!", "NHÓM SỌC!", "TỚI BI 8!") bật giữa bàn rồi thu về dải thông báo dưới bàn; bấm chuột là tắt ngay. (5) Bảng điểm: số nháy sáng khi đổi; bi vào lỗ bị gạch bằng nhịp sáng. (6) Bảng kết quả nở ra. Thêm: bi co nhỏ vào lỗ, rung rất nhẹ khi phá bi |
| Cửa sổ | Mở TOÀN MÀN HÌNH; F11 chuyển sang cửa sổ (kéo to/nhỏ được) và ngược lại. Không còn dải đen ở mọi tỉ lệ màn hình: nền và ánh sáng phủ kín, khung 1280×720 giữ đúng tỉ lệ ở giữa (màn siêu rộng: bàn + bảng bên ở giữa, nền trải hai bên) |
| MVP | Menu mở đầu (Chơi / Ngôn ngữ / Thoát) + bàn chơi tự do (15 bi tam giác, kéo thả, va chạm, nảy băng, vào lỗ, bi trắng rơi lỗ thì đặt lại) + bảng bên (số cú, bi còn lại) + phím R chơi lại, M tắt tiếng, H hướng dẫn. (Phím G lưới toạ độ có ở bản đầu, đã bỏ 2026-10-29 cùng chế độ công thức.) Luật thắng/thua làm sau (mục "Luật tập một mình"); CHƯA có xoáy |

## Phản hồi sau khi người dùng chơi thử MVP (2026-10-28)
- Đồ họa: phải là vector thật, mịn ở mọi cỡ cửa sổ (laptop HD 1280×720 của người dùng; cửa sổ mở đầu tự vừa màn hình). Đã chuyển sang vẽ ở độ phân giải thật.
- Thanh kéo: dài theo lực kéo, DỪNG ở mức tối đa (không dài vô tận), đổi màu theo lực (nay lơ → hồng tím, xem "Phản hồi lần 5"). Đã BỎ HẲN thanh lực dọc bên trái, không hiện số % (người dùng chọn).
- Đường cong lực: lực = (kéo / kéo tối đa)² — kéo nửa chừng chỉ ra ~1/4 lực (dễ đánh nhẹ chính xác). Kéo ngắn hơn 12 px khi thả = huỷ cú.
- Lực tối đa giảm ~28%: `TRON` 8,0 → 5,8 · `VUA` 7,0 → 5,0 · `CHAM` 6,0 → 4,3 m/s. Âm thanh và kéo to/nhỏ cửa sổ: người dùng hài lòng.

## Phản hồi lần 2 (2026-10-28, người dùng sau khi test)
- Bỏ ô ca-rô trên mặt nỉ.
- Bóng đổ của bi: từ trên xuống (thẳng xuống dưới bi), thay cho bóng nghiêng chéo.
- Thanh kéo: thanh thẳng góc cạnh, bỏ đầu bo tròn và bỏ độ thon.
- Bàn vẽ lại theo ảnh tham chiếu `ban-bida-anh-tham-chieu.webp` (ảnh của bên thứ ba, chỉ để tham khảo, KHÔNG đưa vào git): khung gỗ nâu có vân, tấm đồng/kem ở 4 góc và 2 lỗ giữa, nỉ xanh sáng ở giữa và tối dần ra mép, băng đệm xanh đậm có vạch sáng ở mép nỉ, lỗ đen có viền xám, chấm kim cương vàng trên khung (mỗi 1/8 cạnh dài, mỗi 1/4 cạnh ngắn). Hình học vật lý và vị trí lỗ KHÔNG đổi (mép nỉ = mặt băng). Mã: `game/render/table.py`.


## Phản hồi lần 3 (2026-10-29, người dùng sau khi chơi chế độ công thức)
- Bỏ chế độ công thức khỏi dự án: vừa khó chơi vừa không tạo nhiều cảm giác thích thú so với chơi thường. Kéo theo: bỏ mức toán Dễ/Vừa/Khó, nút Gợi ý, lưới toạ độ (phím G), đường cong y = f(x) khỏi kế hoạch. Menu còn Chơi / Ngôn ngữ / Thoát (sau đó thêm Hướng dẫn, xem mục dưới).
- Giữ: bàn vẽ lại, bóng thẳng xuống, thanh kéo vuông (lần 2) và luật 8-ball (mục dưới).
- Đã quyết (2026-10-29): game đổi tên thành NeonPool, dòng phụ vi "Mỗi cú đánh một vệt sáng" / en "Every shot leaves a glow"; không còn yếu tố toán trong tên và chữ hiện ra. (Tên cũ là MathofPool.)
- Việc kế tiếp theo thứ tự đã chọn: xoáy cao/thấp.

## Phản hồi lần 5 (2026-10-29, người dùng yêu cầu: đổi đồ họa sang neon nền tối + hiệu ứng wave, nâng giao diện theo phong cách neon)
Người dùng đã chọn (bằng câu hỏi, rồi chọn mức sáng bằng ảnh):
- Mặt bàn: nỉ tối, băng thành là đường neon (không lưới, không gỗ/đồng). Màu: xanh lơ + hồng tím.
- Sóng ở: nền menu và Hướng dẫn, mặt bàn khi bi va chạm hoặc rơi lỗ, viền bàn. KHÔNG có sóng ở vạch ngắm. Bàn tĩnh khi ngắm; vệt sáng ở viền chạy rất chậm, chỉ ở viền ngoài.
- Bi: tối, chỉ có vòng và số phát sáng như bóng đèn (đã báo trước: bi sọc và bi nguyên khó phân biệt hơn nên bi sọc có hai đường sáng ngang thân). Tiêu đề: chữ đặc sáng trắng, quầng xanh lơ thở nhẹ.
- Đổi tên game thành NeonPool, dòng phụ "Mỗi cú đánh một vệt sáng" / "Every shot leaves a glow". Tên thư mục dự án giữ `MathofPool` (đổi giữa phiên làm hỏng đường dẫn phiên).
- Mức sáng: chọn "Đèn ống" (nét mảnh, quầng hẹp) trong hai bộ đã phác; bộ "Quầng mờ" (nét dày, quầng rộng) bị loại vì bi nhoè, số bi sọc khó đọc ở cỡ 20 px. Ảnh (thư mục `tools/_out/`, git bỏ qua): `neon_a_*.png` (chọn), `neon_b_*.png` (loại), `neon_so_sanh_chi_tiet.png`.
- Hệ quả đã báo: bóng đổ của bi (phản hồi lần 2) bị thay bằng quầng sáng đều; thanh kéo đổi từ vàng → cam sang lơ → hồng tím (lõi sáng, hai đầu vuông như cũ).

## Phản hồi lần 6 (2026-10-29, người dùng: "UI trông rởm, phông tạm bợ, chưa có chất riêng"; muốn lấp đầy màn hình, bỏ cụm "Cảm giác bàn")
Yêu cầu: UI hoàn chỉnh để DÙNG chứ không để test; chữ và số không được lệch (đã gửi ảnh số trong vòng đánh số bị lệch, ba chấm cảm giác bàn không thẳng hàng); sóng menu phải sống chứ không phải ảnh ghép trôi qua. Người dùng chọn (hai vòng câu hỏi):
- Chất: arcade thập niên 80 (synthwave). Sóng menu: phản ứng với người chơi. Màn hình: nền tràn hết mép, mở là toàn màn hình. Phông: tiêu đề ống neon, chữ thường gọn sắc, số thẳng hàng.
- Thanh kéo → gậy neon (lần đầu có vạch nạp). Cảm giác bàn: bỏ hẳn, luôn "Vừa". Nét arcade: cả bốn (lưới chân trời + mặt trời sọc, bảng điểm máy xèng, chữ thông báo arcade, vệt quét CRT rất nhẹ). Âm thanh: thêm tiếng bíp arcade.
- Tinh chỉnh sau khi xem: cơ chỉ lùi 75% quãng kéo (lực giữ nguyên), hiện dần khi rê chuột lên bi trắng và mờ dần khi rời, BỎ vạch nạp, lực thể hiện bằng màu (căng → nóng); bàn vẽ lại tối giản bằng nét neon.
- Còn để ngỏ: trên màn siêu rộng bảng bên đứng cạnh bàn (giữa màn), không bám sát mép phải.

## Phản hồi lần 4 (2026-10-29, người dùng chơi bản 8-ball; ảnh tham chiếu thứ hai `ban-bida.png`, của bên thứ ba, KHÔNG đưa vào git)
- Thông báo (lỗi, chọn nhóm, "kéo bi trắng…") KHÔNG được che bàn: trước đây nằm trên nỉ ngay dưới lỗ giữa nên che bi lăn sát băng trên. Nay treo ở dải trống DƯỚI bàn (tối đa hai dòng; vừa cả ở cửa sổ 1050×590, cả vi và en).
- Lỗ có chiều sâu: vành kim loại sáng, vòng tối, thành lỗ xám và một hố đen lún về phía ngoài bàn (thành lỗ hiện như hình lưỡi liềm ở phía nỉ). Vị trí và bán kính lỗ cho vật lý KHÔNG đổi.
- Không được để tấm đồng hay gỗ lòi ra ở khoảng nêm giữa đầu băng bo cong và vành lỗ: tấm đồng chỉ nằm trên phần gỗ, phần băng liền màu xanh (kể cả hai bên lỗ giữa).
- Sáu thành băng xanh có hai đầu bo cong (bán kính = độ dày băng, 12 px) kết thúc sát vành lỗ; bóng đổ của băng lên nỉ đi theo đường bo. Mã: `game/render/table.py`.

## Màn Hướng dẫn chơi (người dùng chốt 2026-10-29; brief: docs/plans/20261029-huong-dan.md)
- Menu: Chơi · Hướng dẫn · Ngôn ngữ · Thoát. Trong ván, phím H mở hướng dẫn, Esc quay lại đúng ván đó.
- Bố cục "Trang lật" (người dùng chọn trong 3 hướng đã phác): mỗi lần một chủ đề, hình bên trái, vài câu có đánh số bên phải; nút Trước/Sau, phím ← →, chấm báo trang. Sáu trang: Cách đánh, Mục tiêu và nhóm bi, Lỗi, Bi trắng trong tay, Thắng và thua, Phím tắt.
- Hình minh họa là ẢNH THẬT chụp từ chính game (game tự vẽ một khung với thế bi dựng sẵn), chỉ phần đánh dấu (số, mũi tên, ✕/✓, nhãn) là vẽ thêm. KHÔNG vẽ lại bàn mini.

## Luật tập một mình (đề xuất theo WPA 8-ball, rút gọn; người dùng đã duyệt và đã làm 2026-10-28, chi tiết ở docs/plans/20261028-8ball.md)
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
