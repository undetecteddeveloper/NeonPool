# Brief: NeonPool chơi mạng — Chặng 0 + 1 (2026-10-30)

Luật chơi đã chốt: `docs/GAME_DESIGN.md` "Chơi mạng". Kiến trúc và bất biến mạng: `docs/ARCHITECTURE.md` "Chơi mạng".
Phiên này: Chặng 0 (đo, chốt kiến trúc) + Chặng 1 (hai máy CÙNG WIFI chơi trọn một ván có luật).

## Yêu cầu (đo được)
- Một chiều "thả chuột ở A → B bắt đầu chạy cú" ≤ 50 ms p95 khi RTT thẳng ≤ 40 ms; phần GAME tự cộng ≤ 5 ms p95.
- Cơ đối thủ ≤ 30 gói/s, < 2 KB/s mỗi chiều, lệch hiển thị ≤ 1 khung ngoài trễ mạng, không đệm quá 1 gói.
- Cú đánh chỉ gửi `Shot` đã lượng tử hoá + seed + số thứ tự; hết cú chủ phòng gửi điểm kiểm, lệch → dán + đếm.
- Số mili-giây THẬT chỉ đo được với máy thứ hai (người dùng chỉ có MỘT máy): số đo ở đây ghi nhãn "giả lập"; hai máy thật: CHƯA ĐO + kịch bản chạy (cuối file).

## Quyết định kỹ thuật (và lý do)
| Chủ đề | Quyết định | Lý do |
|---|---|---|
| Truyền | TCP (`TCP_NODELAY`) cho chặng 1; giao diện `Transport.send(frame, reliable)` | LAN không cần NAT; TCP đã có thứ tự + tin cậy. Chặng 2 (qua NAT) có thể cần UDP: thêm transport mới, KHÔNG đổi giao thức/`Session` |
| Mất gói | `NetSim` mô phỏng đúng TCP: gói tin cậy bị mất = giao muộn thêm RTO và chặn các gói sau (head-of-line); gói không tin cậy (`AIM`) bị mất thật | thử đúng thứ sẽ gặp ở mạng thật, không giả vờ UDP |
| Luồng | `tcp.py` chạy socket ở luồng nền, hai hàng đợi; `Session.update(dt)` ở luồng chính chỉ lấy ra | bất biến 1: vòng lặp pygame không chờ socket |
| Ai tính luật | Chủ phòng. `Match` bọc `EightBall` làm giám khảo từng cú, đổi `group` theo người đang đánh | dùng lại 100% luật lỗi/bi 8 đã có test; tập một mình không đổi một dòng |
| Khách đánh | Áp ngay (tiên đoán), gửi `SHOT` yêu cầu; chủ phòng áp khi nhận. Hai bên chạy cùng mô phỏng, nên hiệu lực không phụ thuộc lúc áp | ẩn trễ một chiều cho người đánh |
| Điểm kiểm | float64 chính xác, luôn dán | lượng tử hoá vị trí sẽ làm cú sau lệch dần; 16 bi ≈ 270 byte mỗi cú |
| Xoáy | Có (`Shot.spin` i8, nấc 1/32 — đúng nấc của bảng xoáy) | người dùng chốt; xoáy đã có sẵn |
| Cơ đối thủ | Chỉ giữ gói MỚI NHẤT, làm mượt bằng lọc mũ τ = 1 khung (không đệm) | yêu cầu "không bộ đệm > 1 gói" |
| Bắt tay | `PROTOCOL_VERSION` + chuỗi `GAME_VERSION`; lệch → `REJECT(VERSION)` | tiêu chí phiên bản |
| Giao diện | Phác 2–3 hướng bằng ảnh cho menu 5 nút, màn Chơi mạng, bảng hai người; người dùng chọn rồi mới code (task 9) | `ui.md` |

## Task (mỗi task một commit `feat(net): ...`)
Chặng 0
1. Tài liệu (commit này) + brief.
2. `net/protocol.py` + test khung tin (AC2, AC3). (Làm sau task 5: `Checkpoint` mang `MatchState`.)
3. `net/transport.py` (giao diện, loopback, `NetSim`) + test.
4. `tools/netbench.py` + số đo (AC7); số ghi ở mục "Số đo" dưới đây, kiến trúc giữ nguyên (đã làm, sau task 5).
Chặng 1
5. `rules/two_player.py` (`Match`) + test luật (AC4 đồng hồ-khung, AC5).
6. `net/session.py` (bắt tay, tung xu, lượt, điểm kiểm, đếm lệch) + test (AC4, AC6).
7. `net/tcp.py` nối thẳng LAN + test ổ cắm thật trên 127.0.0.1 (+ `netbench.py --tcp`).
8. `PlayScene` tách móc nối (bước mô phỏng, vẽ bàn / bảng bên / lớp phủ), tập một mình y hệt (AC1, dấu vân tay + ảnh trước/sau).
9. Phác giao diện, người dùng chọn.
10. Menu 5 nút + tên người chơi trong Cài đặt + màn Chơi mạng (tạo / vào phòng) + ô nhập chữ dùng chung.
11. `NetPlayScene`: tung xu, bảng hai người, cơ đối thủ, bi trắng trong tay, thẻ Thắng/Thua (không điểm), mất kết nối (AC9, AC10).
12. Smoke hai instance qua loopback trong `gate.py` (AC8), PROGRESS.md, cổng đầy đủ.

## Tiêu chí chấp nhận → test
| # | Tiêu chí | Test |
|---|---|---|
| AC1 | tập một mình không đổi | toàn bộ test cũ (422) + `test_ac1_solo_fingerprint_unchanged` |
| AC2 | hai World, cùng Shot lượng tử hoá + seed, qua giao thức → cùng trạng thái | `test_ac2_same_shot_same_seed_same_state_through_protocol` |
| AC3 | khứ hồi mọi tin; tin hỏng/cụt/lạ bị từ chối gọn | `test_ac3_roundtrip_every_message`, `test_ac3_corrupt_truncated_unknown_rejected` |
| AC4 | người không có lượt bị từ chối; hết giờ mất lượt (khung) | `test_ac4_shot_out_of_turn_rejected`, `test_ac4_timeout_passes_the_turn` |
| AC5 | đổi lượt, lỗi → bi trắng tự do cho đối thủ, nhóm đối ngược, bi 8 từng bên | `test_ac5_*` trong `test_two_player_rules.py` |
| AC6 | NetSim (20 ms, jitter, 2% mất): ván kết thúc, hai bên cùng kết quả, báo đếm lệch | `test_ac6_netsim_game_ends_with_same_result_on_both` |
| AC7 | `netbench.py` in số đo hai nhãn | `test_ac7_netbench_reports_both_labels` |
| AC8 | smoke hai instance → thắng/thua, exit 0, trong gate | `tools/smoke.py` (bước "ván hai máy") |
| AC9 | vi/en cùng bộ khoá | `tests/test_i18n.py` sẵn có + `test_ac9_net_keys_in_both_languages` |
| AC10 | ảnh các màn mới đã nhìn | `tools/_out/20261030-multiplayer/` |

## Số đo (`tools\netbench.py`; nhãn "giả lập" = thời gian ảo của NetSim + đồng hồ thật cho phần việc của game)
Một chiều "thả chuột ở A → B áp cú đánh", 4000 cú mỗi dòng, ms, **giả lập (đã đo)**, 2026-10-30:
| Kịch bản | tới hàng đợi p50/p95/p99 | + chờ khung B p95 | + chờ khung A p95 | phần game p95 |
|---|---|---|---|---|
| LAN tốt | 1,3 / 1,5 / 1,5 | 17,1 | 29,1 | 0,03 |
| VN thường (RTT 40, jitter 2) | 21,0 / 21,9 / 22,0 | **36,8** (mục tiêu ≤ 50: đạt) | 49,0 | **0,03** (≤ 5: đạt) |
| VN xấu vừa (RTT 40, jitter 10, mất 2%) | 25,1 / 29,7 / **223,5** | 43,3 | 55,4 | 0,02 |
| xa (RTT 80, jitter 20, mất 5%) | 50,4 / 59,9 / 256,1 | 75,0 | 88,0 | 0,03 |
Cơ đối thủ: 30 gói/s, 240 byte/s nội dung (~1440 kể cả tiêu đề TCP/IP; mục tiêu < 2048). Điểm kiểm sau mỗi cú: 303 byte.
**Hai máy thật: CHƯA ĐO.** Kịch bản chạy khi nhờ được bạn: cuối bản in của `netbench.py`.

Điều số đo cho thấy (và quyết định):
- Phần game tự cộng là ~0,03 ms: mã hoá + giải mã + áp cú không đáng kể. Phần lớn "tới khung" là chờ ĐẦU KHUNG HÌNH (60 FPS), vốn có ở mọi game pygame; không cố giảm bằng cách áp cú ngoài luồng chính (mất an toàn luồng).
- Chờ khung ở CẢ HAI máy làm p95 vượt 48 ms ở "VN thường" (49,0). Mục tiêu 50 ms tính ở mức "+ khung B"; mức "+ khung A" ghi để không giấu.
- Mất 2% gói làm p99 nhảy từ 22 lên 223 ms: gói tin cậy bị mất phải chờ RTO 200 ms (TCP). Với `SHOT` nằm trong 1% tệ nhất thì người chơi thấy khựng ~0,2 s. Chặng 1 (LAN, TCP) chịu được; **Chặng 2 (internet) nên dùng UDP + lớp tin cậy RTO ≈ 1,5×RTT (~70 ms)** thay vì TCP — transport mới, giao thức và `Session` giữ nguyên. Đo lại ở chặng 2.

- **Ổ cắm thật cùng máy (`netbench.py --tcp`, đã đo)**: từ `send` tới hàng đợi bên nhận, p50/p95/p99 ms: luồng chính rảnh 0,16/0,31/0,50; luồng chính BẬN (khung 4 ms) với chu kỳ chuyển luồng mặc định 5 ms của Python 25,6/55,0/66,1 (!); 1 ms 25,6/46,8/56,6; **0,2 ms (game dùng) 0,23/0,37/0,54**. Nguyên nhân: trên Windows luồng nền chờ GIL bị làm tròn lên một nhịp đồng hồ (~10–15 ms) khi luồng chính bận; dưới 1 ms thì bàn giao ngay. `tcp.py` đặt `sys.setswitchinterval(0.0002)` lúc tạo kết nối đầu tiên. Đây vẫn là cùng một máy, chưa phải hai máy thật.

Kiến trúc `net/` được GIỮ như dự kiến (protocol / transport / session thuần; TCP cho LAN). Lý do không đổi: phần game không phải nút cổ chai, nên không cần đường đặc biệt nào ở chặng 1.

## Chặng sau (KHÔNG làm ở phiên này)
- Chặng 2: mã phòng + danh bạ + máy trung chuyển miễn phí + tự chuyển trực tiếp/trung chuyển; đo lại 50 ms. Tra lại điều khoản gói miễn phí bằng WebSearch trước khi chốt nền tảng (CHƯA LÀM). Hiện địa chỉ → bỏ.
- Chặng 3: rớt mạng/vào lại 60 s, đồng hồ 60 s (khung `TURN_TIMEOUT` + `Match.timeout` đã có), Đấu lại + tỉ số, biểu cảm (`EMOTE`), nút Đầu hàng + thoát = thua. Hướng dẫn thêm trang chơi mạng.
- Chặng 4: trang xem nhanh (số phòng, người, độ trễ), nhật ký có lý do ngắt, cập nhật một lệnh, thông báo khi máy chủ sập.
- Không bao giờ: tài khoản, xếp hạng, chat tự do, khán giả, 3–4 người, ghép ngẫu nhiên, tự cập nhật, bot, vật lý trên máy chủ.

## Kịch bản đo hai máy thật (người dùng chạy khi nhờ được bạn)
(điền ở task 4)
