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
| Đồng hồ | `Session.turn_left_s`: cộng dồn CHỈ khi `settled` và đã hết tung xu (`NET_COIN_S`); về 0 mỗi khi cú bắt đầu / điểm kiểm tới / hết giờ. Cả hai máy đếm để hiển thị. Chủ phòng tự cắt lượt của MÌNH ở 60 s; lượt khách: khách gửi `TurnTimeout` khi đồng hồ của khách về 0, chủ phòng cũng tự cắt sau 60 + `NET_TURN_GRACE_S` (1 s) nếu tin không tới | khách bấm ở giây 59,9 không bị từ chối vì trễ một chiều |
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

## Chưa đo được (một máy)
Nối lại trên hai máy thật qua wifi (đổi mạng, cắm lại cáp) CHƯA thử; ổ cắm thật cùng máy thì thử được bằng cách đóng đường nối từ một phía.
