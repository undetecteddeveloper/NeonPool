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
| Kéo thả | CÂY CƠ NEON, ngắm kiểu VẶN NÚM (người dùng chốt 2026-10-29): rê chuột lên bi trắng thì cơ hiện dần sau bi (0,18 s), rời ra thì mờ dần (0,25 s); trong vùng bi, rê con trỏ vòng quanh tâm bi thì cơ quay theo đúng góc đó (1 vòng chuột = 1 vòng cơ; sát tâm bi không tính). Bấm giữ rồi kéo NGƯỢC hướng muốn đánh (tính từ chỗ bấm): kéo càng xa lực càng mạnh, và hướng đánh đi theo hướng kéo suốt lúc kéo, KHÔNG khoá góc (người dùng bỏ khoá 2026-10-29); kéo lệch khỏi hướng đã vặn thì cơ chuyển theo, huỷ giữa chừng thì cơ nằm nguyên ở hướng vừa kéo. Cơ lùi 75% quãng kéo (`CUE_SHOW_PULL`, lực không đổi); lực thể hiện bằng màu nóng dần: lơ → tím → hồng → cam → trắng nóng; căng tối đa thì rung nhẹ; thả tay thì cơ lao tới bi rồi tắt. Vạch ngắm CHỈ hiện khi đang kéo |
| Âm thanh | Tiếng bi: gậy đánh, bi va (mạnh/nhẹ theo lực), nảy băng, rơi lỗ. Tiếng giao diện kiểu arcade (2026-10-29): bíp khi rê sang nút khác, hai nốt khi bấm, chuông nhẹ khi chọn nhóm / tới bi 8, tiếng rè khi lỗi, nhạc 8-bit ngắn khi thắng/thua. NHẠC NỀN (2026-10-30): hai bài lặp vô hạn, một cho menu và một lúc chơi, tự tạo bằng mã (xem "Phản hồi lần 10"). Hai thanh trong Cài đặt: Âm lượng (tiếng bi, bíp) và Nhạc nền; M tắt TẤT CẢ nhanh (chỉ trong phiên, không lưu) |
| Cài đặt | Menu: Chơi / Hướng dẫn / Cài đặt / Thoát. Cài đặt là bảng nổi trượt lên trên menu (khi bảng đã mở yên, menu là ảnh đứng yên dưới lớp phủ tối; lúc bảng đang đóng lại thì menu chạy lại — xem "Phản hồi lần 11"). Đóng bằng nút Xong, KHÔNG có nút ✕ như Hướng dẫn (người dùng chốt 2026-10-30: không cần). Gồm: Ngôn ngữ (vi/en), Âm lượng (0–100%, nấc 10%, có bíp thử), Nhạc nền (0–100%, nấc 10%, mặc định 50%; nghe ngay vì nhạc đang chạy), Rung màn hình (bật/tắt), Hiện FPS (bật/tắt; số đèn 7 đoạn nhỏ ở góc trên trái, vàng < 50, đỏ < 30). Mọi thay đổi áp ngay và LƯU NGAY vào %APPDATA%\NeonPool\settings.json, còn nguyên khi mở lại game |
| Hiệu ứng | Bàn ĐỨNG YÊN khi ngắm. (1) Menu: bi lần lượt (1→15 rồi bi trắng, tối đa 5 bi, ~2,4 s một bi) nổi lên từ đáy màn hình cùng một cỡ (1,43 lần bi trên bàn), đi CHÉO sang phải khoảng 20° do dòng chảy (dòng mạnh dần khi gần dải sóng nên đường đi cong thành trôi ngang), chậm dần khi tới dải sóng rồi dập dềnh; bi KHÔNG làm sóng lõm hay gợn (dải sóng y như khi không có bi); số và vạch sọc xoay qua lại ±90° lúc nổi, ±35° và chậm hơn lúc trôi; bi nằm GIỮA các nét sóng (độ sâu đổi dần: vài nét chạy sau bi bị thân bi che, vài nét chạy trước cắt ngang mặt bi, luôn có ít nhất một nét mỗi phía), và trôi theo sóng sang phải tới khi khuất; sóng menu KHÔNG còn phản ứng với chuột. Hướng dẫn là khung nổi: cảnh phía sau đứng yên và tối ~90% (xem "Màn Hướng dẫn chơi", lần 10–11). Lưới chân trời trôi, sao lấp lánh, sọc mặt trời trượt, tiêu đề chập chờn lúc vào rồi thở nhẹ. (2) Vòng sóng nhỏ khi bi va chạm (lơ) / chạm băng (tím). (3) Bi rơi lỗ: một vòng sóng màu của viên bi lan từ lỗ ra cả mặt bàn, đường viền và biên bàn sáng bừng chỗ sóng đi qua (thay hai vệt sáng chạy quanh bàn, đã bỏ). (4) Bi đã dừng: chữ arcade lớn bật giữa bàn rồi thu về dải thông báo; bấm chuột là tắt. (5) Bảng bên: số lăn như đồng hồ máy xèng khi đổi và nháy sáng; bi vừa vào lỗ thu nhỏ rồi bị gạch bằng nhịp sáng. (6) Nút: chọn thì sáng dần, nở nhẹ, mũi tên trượt vào, một vệt sáng chạy một vòng viền; bấm thì nhún và loé; ở menu khung sáng trượt từ nút cũ sang nút mới. (7) Đổi màn kiểu tắt/bật TV CRT: màn cũ gập thành vệt sáng ngang rồi tắt, màn mới bung ra (~0,34 s). (8) Rung màn hình (tắt được): cú phá và cú bi trắng va rất mạnh, mạnh yếu theo lực. Thêm: bi co vào lỗ |
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

## Phản hồi lần 8 (2026-10-29, chỉnh cuối sau khi xem bản arcade)
- Menu: bi nổi trông mờ và hơi giật khi chạm dải sóng. Nguyên nhân mờ: ánh sáng cộng của dải sóng được vẽ ĐÈ lên thân bi (bi vẽ trước dải sóng); nguyên nhân giật: cú đẩy "gợn" lúc bi chạm sóng làm mặt sóng rung theo mà bi bám đúng mặt sóng. Sửa: bi vẽ sau dải sóng, bỏ gợn khi chạm sóng (dải sóng giống hệt khi không có bi), bi nhỏ đi 35% (cỡ 2,2 → 1,43 lần bi trên bàn; người dùng nói "giảm xuống khoảng 35%", hiểu là giảm bớt 35%, như lần giảm biên độ cơ 20–30% ở lượt 6).
- Kéo cơ: bỏ khoá góc. Bấm giữ rồi kéo NGƯỢC hướng muốn đánh, hướng đánh theo hướng kéo suốt lúc kéo (tính từ chỗ bấm, nên bấm chỗ nào trên bi cũng không làm cơ nhảy). Vặn núm khi rê chỉ còn là bước ngắm trước; kéo dọc theo cơ thì giữ nguyên góc đã vặn.

## Phản hồi lần 11 (2026-10-30, tinh chỉnh sau khi người dùng chạy thử lần 10; người dùng chọn đủ các phương án khuyến nghị, riêng thứ tự số chọn phương án 2)
- LẬT TRANG ở carousel (cả ở menu và khi bấm H lúc chơi): bỏ chớp CRT, thay bằng TRƯỢT + MỜ theo hướng bấm. Bấm mũi tên phải (hoặc →, D, Enter): trang cũ trượt sang trái 72 px và mờ dần, trang mới từ bên phải trượt vào và rõ dần (0,26 s, giảm tốc cuối); bấm trái thì ngược lại; bấm chấm trang thì trượt về phía trang đó (tới gần hơn = trượt trái). Trang không bao giờ tràn ra ngoài chỗ của nó trên khung. MỞ/ĐÓNG khung vẫn là bung từ vệt sáng ngang.
- SỐ CHẠY ở thẻ kết quả: Điểm, Số cú, Lỗi đều ĐẾM LÊN TỪ 0, nhanh lúc đầu rồi chậm dần, dừng đúng ở giá trị cuối, rồi số LOÉ trắng sáng 0,4 giây (như ô số ở bảng cạnh bàn khi nó đổi). Thứ tự: ĐIỂM (1,1 s) → SỐ CÚ (0,6 s) → LỖI (0,5 s), cách nhau 0,15 s, bắt đầu 0,7 s sau khi ván kết thúc (tiếng thắng/thua kịp vang trước); xong sau ~3,2 s. Số 0 (ví dụ 0 lỗi) không đếm và không kêu. Nút Chơi ván mới / Về menu dùng được NGAY từ đầu, không phải chờ đếm xong. ÂM THANH: mỗi bước có một tiếng "tích" ngắn kiểu bíp arcade, cao độ nhích lên dần theo số (thang ngũ cung G5 → B6), tối đa 14 tiếng mỗi số và thưa dần khi số chậm lại; khi số dừng có một tiếng "ting" như chuông thuỷ tinh nhỏ: sáng khi thắng (E6 + B6), trầm hơn khi thua (A4 + E5), tiếng của Điểm to nhất.
- NHẠC LÚC CHƠI nghe buồn ngủ (bản cũ 68 BPM, không trống) → làm lại theo hướng "nhịp vừa, có trống nhẹ + bass": khoảng 100–108 BPM, kick nhẹ ở nhịp 1 và 3, bass chạy nhịp tám (có nhảy quãng tám), hi-hat nhẹ, arpeggio rõ hơn, hợp âm sáng hơn (maj7/min7); KHÔNG có giai điệu chính (để không xao nhãng lúc ngắm). Ba bản ứng viên có tên: `play_groove` (104 BPM, C–G–Am–F, đang dùng), `play_glide` (100 BPM, arpeggio mười sáu lấp lánh, chuông thưa) và `play_bounce` (108 BPM, có thêm vỗ tay ở nhịp 2 và 4, bass nảy, sôi động nhất trong ba).
- CHỐT CUỐI (2026-10-30, người dùng đã chơi và hài lòng): bố cục khung Hướng dẫn là `wide` (mũi tên tròn ngoài khung; kiểu `inside` đã bỏ); nhạc đang dùng giữ nguyên: menu `menu_dusk`, lúc chơi `play_groove` (các bản ứng viên `menu_city`, `play_glide`, `play_bounce` đã xoá khỏi code, còn trong git log).
- LỖI FPS khi mở Cài đặt ở menu (người dùng báo: tụt xuống ~40 rồi lên 60): xem PROGRESS. Bảng Cài đặt và khung Hướng dẫn giờ chụp sẵn cảnh phía sau và giữ nguyên (đứng yên dưới lớp phủ tối ~80–90%), nên menu KHÔNG còn chạy mờ phía sau khi bảng đã mở yên (khác lần 7); khi bảng đang đóng lại, menu chạy lại bình thường.

## Phản hồi lần 10 (2026-10-30, ba việc giao diện: điểm, hướng dẫn carousel, nhạc nền; người dùng chọn đủ các phương án khuyến nghị)
- ĐIỂM ở thẻ kết quả: một dòng ngay dưới tiêu đề Thắng/Thua (dưới cả dòng lý do khi thua), số 7 đoạn vàng, to hơn Số cú và Lỗi, có đường kẻ mảnh ngăn. Cách tính ("thưởng gọn gàng"): THẮNG = 1000 − 10 mỗi cú − 50 mỗi lỗi, thấp nhất 100 (22 cú, 6 lỗi → 480); THUA = 50 mỗi bi đã vào lỗ, không tính bi 8. Điểm CHỈ hiện ở thẻ kết quả: không có điểm chạy lúc chơi, không có kỷ lục lưu lại.
- HƯỚNG DẪN thành carousel nổi (xem mục "Màn Hướng dẫn chơi"). Chuyển động (người dùng chọn): MỞ/ĐÓNG = khung bung ra từ một vệt sáng ngang ở giữa, đóng thì gập lại thành vệt (0,28 s / 0,2 s); LẬT TRANG: (lần 10 là chớp CRT, đã ĐỔI ở lần 11) trượt + mờ theo hướng bấm. Mũi tên và nút ✕ dùng chuyển động nút sẵn có (sáng lên và phóng nhẹ khi rê, lún rồi loé khi bấm). Không thêm hiệu ứng phụ (số chú thích hiện lần lượt, chấm trang co giãn, mũi tên gợi ý lúc đầu). Người dùng nhìn ảnh rồi chọn bố cục: `wide` (mũi tên tròn ngoài khung) hoặc `inside` (mũi tên viên thuốc trong hàng dưới) — chưa chọn thì dùng `wide`.
- NHẠC NỀN: tự tạo bằng mã (không file nhạc, không lo bản quyền), hai bài lặp vô hạn, mỗi bài chạy liền mạch. Chuyển menu ↔ bàn chéo mờ 1 giây; thẻ kết quả hiện thì nhạc nhỏ xuống 30% cho tiếng thắng/thua nghe rõ. Ứng viên có tên để người dùng nghe chọn (`tools/music_preview.py` ghi ra `tools/_out/music/*.wav`): menu — `menu_dusk` (hoàng hôn: pad dài, arpeggio mềm, chuông thưa, 84 BPM; đang dùng) và `menu_city` (đêm thành phố: trống nhẹ, bass nhịp, 100 BPM). Lúc chơi: xem lần 11. Claude không nghe được nhạc: "nghe ổn hay không" là của người dùng.
- Thanh "Nhạc nền" riêng trong Cài đặt (mặc định 50%), tắt hẳn nhạc mà vẫn nghe tiếng bi được; phím M tắt cả hai.
- Tên thư mục dự án đã đổi `MathofPool` → `NeonPool` (người dùng tự đổi giữa hai phiên); đã kiểm: venv, test, hook vẫn chạy.

## Phản hồi lần 9 (2026-10-30, điểm cuối về bi nổi ở menu; người dùng chọn đủ các phương án khuyến nghị)
- Chiều sâu: bi nằm xen giữa các nét sóng, không đè lên cả dải. Mỗi bi có độ sâu riêng, đổi dần (chìm nổi nhẹ) trong khoảng giữa nét 1 và nét 5 trên 6 nét, nên luôn có ít nhất một nét chạy sau và một nét chạy trước. Nét chạy trước chỉ vẽ trong lòng bi (sắc, không phủ sương).
- Quỹ đạo: nổi lên chéo nhẹ (~20° lệch phương thẳng đứng, sang phải) ngay từ đáy; gần dải sóng dòng chảy mạnh hơn nên đường đi uốn cong dần thành trôi ngang (70 px/s) rồi theo sóng ra khỏi màn.
- Xoay: số và vạch sọc xoay qua lại ±90° lúc nổi; sau khi tới dải sóng vẫn xoay nhưng nhẹ (±35°) và chậm (55%). Vòng ring, quầng sáng và thân bi đứng yên.
- Tên thư mục dự án: người dùng muốn đổi `MathofPool` → `NeonPool`, nhưng đồng ý để đó và tự đổi sau (đổi giữa phiên làm hỏng đường dẫn phiên).

## Phản hồi lần 7 (2026-10-29, người dùng chơi bản arcade)
- Cơ xoay quanh bi trắng khi rê chuột trong bi: người dùng chọn kiểu VẶN NÚM (rê vòng quanh tâm, 1:1), bấm là khoá góc và kéo chỉ để nạp lực (phần khoá góc đã BỎ ở lần 8), vạch ngắm chỉ hiện khi kéo.
- Lỗi chữ: các chữ hoa hai tầng dấu (Ố, Ỗ, Ế, Ẵ…) bị sụt trong nhãn "SỐ CÚ", "LỖI", "TIẾNG: BẬT". Nguyên nhân: phông nới ô chữ ở phía trên khi dấu cao quá; nay mọi chữ đặt theo đường chân chữ, có test quét mọi chữ hoa của cả hai ngôn ngữ ở cả bốn kiểu chữ.
- Bỏ hai vệt sáng chạy quanh bàn; bi rơi lỗ thì sóng lan cả mặt bàn (người dùng chọn).
- Thêm chuyển động giao diện: người dùng chọn chuyển cảnh CRT, nút sống, số và bi trong bảng bên chuyển động (KHÔNG chọn bảng/thông báo trượt; riêng bảng Cài đặt trượt lên như đã mô tả khi hỏi).
- Thêm màn Cài đặt (bảng nổi), gộp Ngôn ngữ vào đó; lưu cài đặt khi đóng game.
- Menu: bỏ tương tác chuột với sóng; thay bằng bi nổi lên rồi trôi theo sóng (người dùng chọn: trôi ra khỏi màn, thưa 3–5 bi lần lượt 1→15, giữ một cỡ, chạm sóng thì gợn rồi dập dềnh; phần gợn và cỡ đã đổi ở lần 8).

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
- Menu: Chơi · Hướng dẫn · Cài đặt · Thoát. Trong ván, phím H mở hướng dẫn, Esc/H đóng và ván tiếp tục đúng chỗ đó.
- (2026-10-30, "Phản hồi lần 10") KHÔNG còn là màn riêng: một khung carousel nhỏ NỔI đè lên menu (hoặc lên bàn chơi khi bấm H), cảnh phía sau bị làm đen (~90%); lật bằng mũi tên (hoặc ← →, A/D, Enter), lật VÒNG TRÒN, chấm báo trang bấm được, nút ✕ và bấm ra ngoài khung để đóng. Mỗi lần một chủ đề, hình bên trái, vài câu có đánh số bên phải. Sáu trang: Cách đánh, Mục tiêu và nhóm bi, Lỗi, Bi trắng trong tay, Thắng và thua, Phím tắt.
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
