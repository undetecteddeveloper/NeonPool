# Brief: NeonPool chơi đôi — Chặng 3 (2026-10-31)

Nối tiếp `docs/plans/20261030-multiplayer.md` (Chặng 0+1 xong). Luật chơi: `docs/GAME_DESIGN.md` "Chơi mạng" + "Phản hồi lần 17". Kiến trúc: `docs/ARCHITECTURE.md` "Chơi mạng".
Người dùng chốt 2026-10-31: làm TRỌN Chặng 3; Đấu lại: người bấm trước chờ người kia, KHÔNG hết giờ.
Chặng 2 (mã phòng + máy trung chuyển) và 4 (trang vận hành) KHÔNG làm ở đây.

## Yêu cầu (đo được)
- Đồng hồ: 60 s cho MỖI cú (kể cả đặt bi trắng trong tay); chỉ chạy khi bàn đứng yên; hết giờ mất lượt, không phạt lỗi; hai máy cùng kết quả.
- Đầu hàng và thoát giữa trận = thua; người kia thấy Thắng kèm lý do; điểm theo công thức cũ.
- Đấu lại: cả hai bấm → ván mới (seed mới, tung xu lại); tỉ số thắng của hai bên luôn giống nhau.
- Rớt mạng: chờ vào lại tối đa 60 s; vào lại → hai bàn giống nhau, chơi tiếp; quá hạn → bên còn lại thắng.
- Biểu cảm 3 mã; Hướng dẫn thêm trang chơi đôi; vi + en cùng bộ khoá.
- Tập một mình KHÔNG đổi (AC1: dấu vân tay + ảnh trước/sau).

## Quyết định kỹ thuật (và lý do)
| Chủ đề | Quyết định | Lý do |
|---|---|---|
| Giao thức | `PROTOCOL_VERSION` 1 → 2: thêm `Rematch`(50), `Surrender`(51), `Resume`(52); `Welcome` mang `token` u32; `CHECK_END`=3; lý do thua mới `LOST_SURRENDER`, `LOST_DROPPED` nối cuối `REASONS` | thêm loại tin, không đổi khung; hai bản khác phiên bản đã tự từ chối nhau ở bắt tay |
| Ai phán | Chủ phòng vẫn là trọng tài: khách gửi `Surrender`, chủ phòng ghi thua rồi gửi `Checkpoint(CHECK_END)` | giữ bất biến 3 |
| Đồng hồ | `Session.turn_left_s`: cộng dồn CHỈ khi `settled` và đã hết đoạn mở ván (`toss.total_s`, xem phần "Phản hồi sau khi test"); về 0 mỗi khi cú bắt đầu / điểm kiểm tới / hết giờ. Cả hai máy đếm để hiển thị. Chủ phòng tự cắt lượt của MÌNH ở 60 s; lượt khách: khách gửi `TurnTimeout` khi đồng hồ của khách về 0, chủ phòng cũng tự cắt sau 60 + `NET_TURN_GRACE_S` (1 s) nếu tin không tới | khách bấm ở giây 59,9 không bị từ chối vì trễ một chiều |
| Rớt mạng | Mất đường nối (hoặc im > `NET_SILENT_S` = 5 s; hai bên đã ping mỗi giây) → `link_down_s` bắt đầu đếm; phiên KHÔNG đóng. Mô phỏng vẫn chạy cho xong cú đang lăn nhưng cấm đánh/đặt bi; đồng hồ lượt đóng băng. Chủ phòng giữ `TcpListener` mở và nhận kết nối mới; khách thử nối lại mỗi 1 s. Khách gửi `Resume(version, token)`; chủ phòng đúng token → `Welcome` + `Checkpoint(CHECK_RESYNC)` ép dán bàn | ván là mô phỏng xác định: chỉ cần dán lại bàn + trạng thái luật là hai máy khớp |
| Hết 60 s | Chủ phòng: khách chưa vào lại → khách thua (`LOST_DROPPED`), chủ phòng thắng. Khách: hết 60 s → thẻ "mất kết nối" (không có kết quả thắng/thua). Giới hạn đã biết: nếu chính mạng của CHỦ PHÒNG đứt thì chủ phòng vẫn tính khách thua (không có cách phân biệt từ trong game) | thiết kế "chủ phòng là trọng tài" đã chốt |
| Người lạ | `token` ngẫu nhiên do chủ phòng cấp lúc `Welcome`; `Resume` sai token → `Reject(BUSY)` | không ai chiếm chỗ người rớt |
| Đấu lại | `Session.ask_rematch()` gửi `Rematch`; chủ phòng thấy đủ hai bên → `Start` mới (seed, người phá ngẫu nhiên) → `game_no` += 1. Cảnh ván nhận ra `game_no` đổi thì `App.start_net` dựng cảnh mới (sạch mọi trạng thái, có chuyển cảnh) | tránh viết lại việc đặt lại từng biến của `PlayScene` |
| Tỉ số | `Session.wins[2]`: mỗi bên tự cộng khi thấy ván xong (cờ đã tính cho từng ván; vào lại không tính đôi) | cùng quy tắc nên luôn bằng nhau |
| Biểu cảm | `Emote(code)` 0..2; gửi tối đa 1 lần / `NET_EMOTE_GAP_S` (1,5 s); mã ≥ 3 bị bỏ | không chat, chống spam |
| Giao diện | ĐÃ phác và người dùng chọn (2026-10-31, `tools/_out/20261031-chang3/`): đồng hồ = thanh cạn dần dưới khung + tiếng tích 10 giây cuối (không hiện số); tỉ số = số arcade giữa hai khung và hàng "VÁN THẮNG" ở thẻ; hai nút Đấu lại / Về menu; biểu cảm = ba nút góc trên phải; thẻ Esc / Đầu hàng? / Mất kết nối như ảnh (chi tiết: GAME_DESIGN lần 17) | `ui.md` |

## Task (mỗi task một commit)
1. Tài liệu (commit này): brief, GAME_DESIGN lần 17, ARCHITECTURE.
2. `rules/two_player.py` `Match.surrender`; `protocol.py` v2 (3 tin mới, `Welcome.token`, `CHECK_END`, lý do mới) + test khung tin (AC3).
3. `session.py`: đồng hồ lượt + `TurnTimeout` (AC11).
4. `session.py`: Đầu hàng / thoát = thua, `wins`, Đấu lại, `game_no`, biểu cảm có giới hạn (AC12, AC13, AC15).
5. `session.py` + `transport.py` (`NetSim` cắt / nối lại) + `tcp.py` (người nối lại): rớt mạng, `Resume`, token (AC14).
6. Phác giao diện (ảnh) → người dùng chọn.
7. Giao diện theo hướng được chọn: đồng hồ + tỉ số ở khung tên, bảng Esc / Đầu hàng, thẻ kết quả có Đấu lại, biểu cảm, lớp mất kết nối.
8. Hướng dẫn: trang chơi đôi (vi + en, có hình).
9. Smoke hai game: ván → Đấu lại → ván hai (AC8); PROGRESS; cổng đầy đủ.

## Tiêu chí chấp nhận → test
| # | Tiêu chí | Test |
|---|---|---|
| AC11 | đồng hồ chỉ chạy khi bàn yên, hết 60 s mất lượt, đóng băng lúc rớt; khách bấm ở giây 59,9 không bị từ chối | `test_ac11_*` trong `test_net_session.py` |
| AC12 | đầu hàng (cả hai phía) và thoát giữa trận → bên kia thắng, cùng kết quả; điểm đúng công thức | `test_ac12_*` |
| AC13 | một bên bấm chờ không hết giờ; đủ hai bên → ván mới seed khác; `wins` bằng nhau hai máy; rời phòng thì Đấu lại bị từ chối | `test_ac13_*` |
| AC14 | rớt giữa lúc bi lăn / đúng lượt khách / đang đặt bi trắng → vào lại trong hạn thì `same_table`; quá hạn: chủ thắng, khách "mất kết nối"; token sai bị từ chối | `test_ac14_*` + `test_net_tcp.py` (ổ cắm thật: cắt rồi nối lại) |
| AC15 | mã lạ bị bỏ; gửi quá nhanh bị bỏ | `test_ac15_*` |
| AC16 | vi/en cùng bộ khoá; Hướng dẫn 7 trang | `test_i18n.py`, `test_help.py` |
| AC17 | ảnh các màn mới đã nhìn (vi + en, 1280×720 và 1050×590) | `tools/_out/20261031-chang3/` |

## Kết quả
Task 1–9 xong trên `feat/multiplayer` (xem PROGRESS.md: số đo và lý do). Thêm ngoài brief theo yêu cầu người dùng: `tools\dev.py` (công cụ dev, đối thủ giả). Khác brief: tiếng tích thay số ở đồng hồ (người dùng chọn khi xem ảnh phác); bảng bên của ván hai người có danh sách phím riêng (`hud.NET_PANEL_KEYS`, không còn R / H vô tác dụng).

## Phản hồi sau khi test (2026-10-31, cùng nhánh; quyết định ở `docs/GAME_DESIGN.md` "Phản hồi lần 18")
Người dùng chơi thử: tung xu nhanh quá, không có hồi hộp, chưa kịp nhìn giao diện; tỉ số cần animation cộng điểm.
| Việc | Cách làm | Lý do |
|---|---|---|
| Đoạn mở ván có nhịp | `game/net/toss.py` (`Toss`, `total_s`): nhìn bàn 1,3 s (Đấu lại 2,1 s) → tối bàn + xu chờ 1,7 s → xu tung 1,5 s → xu nằm 1 s; hằng số `NET_TOSS_*` thay `NET_COIN_S`; `Session._toss_left = toss.total_s(game_no > 1)` | đo: 0,34 s đầu của 2,2 s cũ bị hiệu ứng đổi cảnh che nên xu đã quay ~54% góc khi màn hình mở; cả hai máy cùng đọc một đường thời gian |
| Tối bàn | `hud.dim_rect` (một tấm tối, chỉ đổi độ trong suốt), vùng `TABLE_RECT` = bàn + quầng sáng quanh bàn | chỉ tối bàn để khung tên vẫn đọc được (người dùng chọn); vùng đúng bằng bàn thì quầng sáng ngoài rìa vẫn sáng và lộ một đường viền sáng quanh bàn tối (thấy trong ảnh), nên nới ra 10 px hai bên và 6 px trên dưới (`layout.TABLE_GLOW`) |
| Tiếng | `synth_coin_up` (tung), tiếng tích có sẵn mỗi lần xu lật (cao dần), `synth_coin_land` (keng); tiếng ting có sẵn khi điểm được cộng | tái dùng tiếng đếm số của thẻ kết quả cho điểm; chỉ phát tiếng của khoảng giữa hai khung hình (nhảy cóc của công cụ dev thì im) |
| Cộng điểm ở ván mới | `Session.prev_winner`; cảnh giữ `_wins_before`, `_shown_wins()` đổi số ở `NET_TOSS_SCORE_AT_S` (0,9 s); `hud.versus` dùng `Scoreboard` + `rolling_number` (cuộn, nháy trắng) + "+1" | cùng ngôn ngữ với số ở bảng bên; thẻ kết quả hiện số trước ván (`_card_wins`) để khỏi thấy 1 → 0 → 1 |
| Công cụ dev | F7 và trạng thái "Xem lại đoạn mở ván (tung xu) từ đầu" (`Harness.replay_toss`) | xem lại đoạn 6 giây mà không phải chơi lại |
Số đo (mỗi khung, `tools/_out/20261031-toss/` + script đo trong phiên): tối bàn thêm ~1,1 ms ở 1280×720, ~2,2 ms ở 1920×1080, ~3,8 ms ở 2560×1440 (tổng khung xu bay 3,1 / 5,8 / 10,1 ms).

## Lỗi trạng thái tìm thấy bằng dev tool (2026-10-31, cùng nhánh; quyết định ở `docs/GAME_DESIGN.md` "Phản hồi lần 19")
Người dùng bật bot tự chơi, bấm trạng thái thắng, rồi Đấu lại: thẻ kết quả, điểm và xu chồng nhau.
| Lỗi | Nguyên nhân | Sửa |
|---|---|---|
| Số giữa hai khung +1 khi thẻ kết quả đang hiện | `_shown_wins()` đọc thẳng `session.wins` (đã gồm ván vừa hết); chỉ hàng thẻ dùng `_card_wins()` | `_shown_wins()` trả `_wins_before` trước `NET_TOSS_SCORE_AT_S`, sau đó `_card_wins()` |
| Xu và tối bàn nằm dưới thẻ khi ván hết giữa lúc tung xu | `_draw_toss` và `_toss_sounds` không hỏi ván đã hết chưa | cả hai thoát sớm khi `match.over` (tiếng ting cộng điểm vẫn phát) |
| Bot đánh lúc xu còn trên không | `Session._free` bỏ qua `_toss_left`; chỉ màn hình chặn | `_free` có `_toss_left <= 0` (cũng chặn đặt bi trắng) |
| Bi lệch tâm vòng ở bảng xoáy (ảnh người dùng) | ảnh bi phóng nhỏ lệch nửa điểm ảnh và dán số nguyên; vòng vẽ ở điểm danh nghĩa | `hud._dial_centre` đo tâm bi thật (theo độ phủ), vòng / thanh / chấm / chữ vẽ quanh đó |
Kiểm: ba lỗi đầu và bảng xoáy mỗi cái có test (đỏ trên bản chưa sửa, xanh sau sửa); thêm bộ canh `tests/test_net_invariants.py` (5 mốc kết thúc ván × 2 ván liền với bot tự chơi, soi từng khung) để lớp lỗi "hai thành phần nói khác nhau" bị bắt không cần người dùng mở dev tool. Các helper dựng ván của `tests/test_net_session.py` (`started`, `room_pair`, `pass_turn_to`) nay chờ xu rơi (`coin_lands`) trước khi đánh; `joined` giữ lại cho test cần xu còn trên không.

## Chưa đo được (một máy)
Nối lại trên hai máy thật qua wifi (đổi mạng, cắm lại cáp) CHƯA thử; ổ cắm thật cùng máy thì thử được bằng cách đóng đường nối từ một phía.
