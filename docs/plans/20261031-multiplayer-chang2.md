# Brief: NeonPool chơi đôi — Chặng 2: mã phòng qua internet (2026-10-31)

Nối tiếp `20261030-multiplayer.md` (Chặng 0+1) và `20261031-multiplayer-chang3.md` (Chặng 3). Luật chơi: `docs/GAME_DESIGN.md` "Chơi mạng" + "Phản hồi lần 20". Kiến trúc: `docs/ARCHITECTURE.md` "Chơi mạng".
Người dùng chốt 2026-10-31: làm Chặng 2 (Chặng 4 sau khi chơi thử); máy trung chuyển trên Cloudflare (miễn phí, không thẻ); mã phòng 4 chữ cái; mất internet thì không chơi được (không giữ ô gõ địa chỉ); cùng wifi thì tự nối thẳng.

## Yêu cầu (đo được)
- Tạo phòng → hiện mã 4 chữ (bỏ I, L, O); Vào phòng → gõ mã → vào ván. Màn hình không còn hiện địa chỉ mạng.
- Hai máy cùng mạng: nối thẳng nếu được trong `NET_LAN_TRY_S` (0,6 s), không thì qua máy trung chuyển. Người chơi không chọn.
- Mọi thứ Chặng 3 giữ nguyên qua máy trung chuyển: rớt mạng/vào lại 60 s, Đấu lại, đầu hàng, đồng hồ, biểu cảm.
- Lỗi báo rõ: không có mạng / máy chủ, không thấy phòng, phòng đủ người, máy chủ quá tải, khác bản.
- Máy trung chuyển chỉ chuyển tin, KHÔNG chạy vật lý hay luật; chủ phòng vẫn là trọng tài.
- Một chiều "thả chuột → máy kia áp cú" ≤ 50 ms p95 (qua Singapore dự kiến 40–60): ĐO SAU KHI ĐƯA LÊN, ghi nhãn thật/giả lập.
- Tập một mình KHÔNG đổi (AC1).

## Quyết định kỹ thuật (và lý do)
| Chủ đề | Quyết định | Lý do |
|---|---|---|
| Máy trung chuyển | Cloudflare Worker + Durable Object (`server/cloudflare/`, JavaScript), mỗi mã phòng một object, `locationHint: "apac"` | miễn phí không thẻ, không có máy để tự trông; object nằm gần người tạo phòng |
| Đường nối | WebSocket (`wss://`), mỗi khung game = một tin nhị phân nguyên vẹn; tin điều khiển là JSON chữ. Thư viện `websockets` (bản đồng bộ, luồng nền) | Cloudflare chỉ nhận HTTP/WebSocket, không UDP. Mất gói vẫn chờ chặn như TCP (đã đo ở Chặng 0: p99 ~220 ms khi mất 2%) — chấp nhận, ghi lại |
| Bản chạy máy mình | `server/local_relay.py` (Python, cùng giao thức) cho test, smoke, công cụ dev; bộ test giao thức chạy được trên CẢ hai bản (`NEONPOOL_RELAY_TEST_URL` trỏ tới `wrangler dev`) | test không cần internet; hai bản không lệch nhau |
| Giao thức trung chuyển v1 | `GET /v1/look?code=` (xem phòng, lấy thông tin nối thẳng) · WS `/v1/host[?code&key]` (tạo / lấy lại phòng) · WS `/v1/join?code=` · chủ nhận `peer on n / off`, trả `ack n`; tin của chủ chỉ tới khách sau `ack` | khung cũ của chủ không lọt sang người vào sau |
| Đứt một phía = đứt cả kênh | chủ mất kết nối → máy trung chuyển đóng luôn đường của khách, giữ phòng 90 s cho chủ lấy lại bằng `key`; khách mất → chủ nhận `peer off` | `Session` của Chặng 3 (Resume + token + dán bàn) lo phần còn lại; không có khung nào mất mà hai bên tưởng còn nối |
| Khách cũ treo | người vào mới thay chỗ khách cũ nếu khách cũ im > 4 s (game ping mỗi 1 s) | wifi đổi mạng thì đường cũ treo hàng phút ở máy chủ; không thì khách không vào lại được |
| Nối thẳng | chủ mở `TcpListener` (cổng `NET_PORT`, bận thì cổng bất kỳ) + chuỗi bí mật 16 byte, gửi "địa chỉ LAN + bí mật" qua máy trung chuyển (không hiện ra màn hình); khách thử nối thẳng có bí mật trước, quá 0,6 s thì vào qua máy trung chuyển | người cùng wifi mà không có mã thì không lọt vào; người chơi không thấy địa chỉ |
| Mã phòng | 4 chữ trong `ABCDEFGHJKMNPQRSTUVWXYZ` (23⁴ ≈ 280 nghìn), máy trung chuyển cấp, trùng thì cấp lại | người dùng chọn; bỏ I/L/O dễ nhầm với 1/0 |
| Phòng bỏ quên | phòng chưa có khách quá 30 phút thì máy trung chuyển đóng | giữ mức miễn phí (thời gian object chạy) |
| Địa chỉ máy trung chuyển | `config.NET_RELAY_URL`; `NEONPOOL_RELAY_URL` thay (test, dev). Rỗng = chưa đưa lên → báo "không có máy chủ" | địa chỉ thật chỉ biết sau khi đưa lên tài khoản của người dùng |

## Task (mỗi task một commit)
1. Tài liệu (commit này): brief, ARCHITECTURE, GAME_DESIGN lần 20.
2. `server/local_relay.py` + `game/net/relay.py` (`WsTransport`, `HostRoom`, `Join`, hai `Relinker`) + `tcp.py` (bí mật nối thẳng) + test (AC18–AC21).
3. `server/cloudflare/` (Worker + Durable Object) + chạy bộ test giao thức trên `wrangler dev` (AC22).
4. Phác giao diện (mã phòng, ô gõ mã, lỗi) → người dùng chọn.
5. Bảng Chơi theo hướng được chọn + chữ vi/en + Hướng dẫn trang Chơi đôi + công cụ dev.
6. Smoke hai game qua máy trung chuyển cục bộ (AC8); `netbench.py --relay`; PROGRESS; cổng đầy đủ.
7. (KHI NGƯỜI DÙNG NÓI) đưa lên Cloudflare, điền `NET_RELAY_URL`, đo thật.

## Tiêu chí chấp nhận → test
| # | Tiêu chí | Test |
|---|---|---|
| AC18 | tạo phòng có mã đúng dạng; vào bằng mã → khung đi hai chiều đúng thứ tự; mã sai / phòng đủ người / phòng đã đóng báo đúng lỗi | `test_ac18_*` trong `tests/test_net_relay.py` |
| AC19 | chủ hoặc khách đứt → cả kênh đứt; chủ lấy lại phòng bằng key, khách vào lại; khung cũ của chủ không tới khách mới; khách cũ treo bị thay | `test_ac19_*` |
| AC20 | cùng máy có nối thẳng → dùng nối thẳng; nối thẳng hỏng → qua trung chuyển; không có bí mật thì không vào được cửa thẳng | `test_ac20_*` |
| AC21 | ván hai `Session` qua máy trung chuyển: rớt giữa ván rồi vào lại → `same_table`, ván xong cùng kết quả | `test_ac21_*` |
| AC22 | bộ test giao thức xanh trên bản Cloudflare chạy máy mình (`wrangler dev`) | `NEONPOOL_RELAY_TEST_URL=... pytest tests/test_net_relay.py` (ghi kết quả ở đây) |
| AC23 | bảng Chơi: mã hiện, gõ mã, lỗi; vi/en cùng bộ khoá; ảnh đã nhìn ở 1280×720 và 1050×590 | `test_net_play.py`, `test_i18n.py`, `tools/_out/20261031-ma-phong/` |

## Kết quả (2026-10-31, nhánh `feat/ma-phong`, đã gộp vào `main` và xoá nhánh)
Task 1–7 xong. Task 7 (đưa lên Cloudflare) làm 2026-10-31 sau khi người dùng tạo tài khoản và nói "đưa lên": `wrangler login` (người dùng bấm Allow), `wrangler deploy`; Worker `neonpool-relay` ở `wss://neonpool-relay.neonpool-relay.workers.dev` (tên miền con `neonpool-relay` do wrangler đăng ký tự động cho tài khoản; đổi được ở trang Workers của Cloudflare, khi đó phải sửa `config.NET_RELAY_URL`). Gói miễn phí, Durable Object SQLite.
Giao diện người dùng chọn (ảnh `tools/_out/20261031-ma-phong/`, GAME_DESIGN lần 20): bốn ô (`hud.code_tiles`), đủ 4 chữ tự vào, bỏ dòng gợi ý, giữ nối thẳng. Hướng dẫn trang Chơi đôi không nhắc địa chỉ/wifi nên không đổi.
| Kiểm | Kết quả |
|---|---|
| AC18–AC21 trên `server/local_relay.py` | 15/15 xanh (`tests/test_net_relay.py`) |
| AC22: cùng bộ test trên bản Cloudflare chạy máy mình (`wrangler dev`, wrangler 4.156.0) | 14 xanh, 1 bỏ qua (mốc 90 s / 30 phút); thử riêng mốc 90 s: chủ rời → "away", 60 s vẫn "away", 95 s → "no_room" (đúng). Mốc 30 phút phòng bỏ quên trên Cloudflare: CHƯA THỬ |
| AC22 trên bản THẬT (`NEONPOOL_RELAY_TEST_URL=wss://neonpool-relay.neonpool-relay.workers.dev`) | 14 xanh, 2 bỏ qua (hai mốc thời gian cần bản máy mình: 90 s, 30 phút). Lần chạy đầu 9 đỏ vì lỗi dưới đây |
| Lỗi chỉ lộ ở bản thật | Cloudflare chặn tên trình khách mặc định `Python-urllib` (HTTP 403, mã 1010) ở bước `look`, và `relay.py` hiểu mọi lỗi HTTP là "máy chủ bận" → mọi người vào phòng đều bị báo "hết lượt miễn phí" dù tạo phòng chạy. Sửa: mọi yêu cầu mang `User-Agent: NeonPool/<bản>` (`relay.USER_AGENT`). Máy trung chuyển cục bộ nay chặn y như Cloudflare nên test bắt được (11 đỏ khi bỏ bản sửa, 16 xanh khi có) |
| Lỗi bộ test bắt được ở bản Cloudflare | khung nhị phân tới Durable Object dạng `Blob` (ngày tương thích mới) và bị gửi đi thành chữ `{}` → sửa `binaryType = "arraybuffer"` |
| Lỗi tìm được khi chạy cả bộ test (AC21 đỏ 1 lần, chạy riêng 6 lần xanh) | khách đang nối lại thì bộ nối lại mở thêm đường sau 0,1 s và `Session` bỏ đường thừa mà không đóng → ở máy trung chuyển đường thừa có thể chiếm chỗ đường thật. Sửa: `Session` đóng ngay, `GuestRelink` chờ hết `NET_HANDSHAKE_TIMEOUT_S` sau mỗi lần nối được; test đỏ trước sửa / xanh sau sửa. Chưa chứng minh đây là nguyên nhân duy nhất của lần đỏ đó |
| Smoke hai game (bảng Chơi thật, cửa nối thẳng đóng → cả ván qua máy trung chuyển cục bộ, Đấu lại) | xanh, mọi giai đoạn ≤ 16,7 ms/khung |
Số đo (`tools\netbench.py --relay`, 300 khung mỗi chiều, luồng chính bận 4 ms/khung, ms p50/p95/p99, **trên máy này, đã đo**): máy trung chuyển Python 0,72/1,44/1,82 (khách → chủ), 0,71/1,29/1,70 (chủ → khách); bản Cloudflare trong `wrangler dev` 0,89/1,33/1,73 và 0,89/1,28/1,67 (chưa có đường internet).
**Qua Cloudflare THẬT (2026-10-31, một máy ở Việt Nam, đầu A và B cùng ở máy này nên mỗi khung đi máy → Cloudflare → máy; trạm Cloudflare thấy là HKG)**: khách → chủ 48,2/97,8/137,9; chủ → khách 48,9/88,7/116,3. Hiểu: nếu hai người cùng cách máy trung chuyển cỡ này thì một chiều giữa hai người ≈ 48 ms trung vị; **p95 ≈ 90–98 ms VƯỢT mục tiêu 50 ms** (chưa kể chờ đầu khung ~8 ms). Hai người ở xa nhau hơn hoặc xa trạm hơn thì còn cao hơn. CHƯA làm gì để giảm (chưa biết phần nào do đường truyền, do Durable Object nằm xa trạm vào, hay do TCP chờ gói); xem 'Việc tiếp' dưới. Cùng wifi thì nối thẳng (~1 ms) nên không bị.
Giới hạn đã biết: WebSocket chạy trên TCP nên mất gói vẫn chờ chặn như Chặng 1 (p99 có thể ~200 ms khi mạng mất 2%); Cloudflare không cho UDP.

Việc tiếp cho độ trễ (CHƯA LÀM, cần người dùng chọn hướng): (1) đo lại từ máy thứ hai ở nhà khác; (2) kiểm Durable Object đang chạy ở đâu (`locationHint: "apac"` chỉ là gợi ý); (3) nếu vẫn cao: tách đường tin cậy / không tin cậy hoặc chuyển nền tảng. Dùng gói miễn phí: giới hạn 100.000 yêu cầu/ngày tính theo tin gửi lên (20 tin = 1 yêu cầu), ước tính ~9 giờ ngắm cơ liên tục mỗi ngày cho hai người, CHƯA đo thực tế.
