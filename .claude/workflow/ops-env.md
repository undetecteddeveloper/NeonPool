# Ghi chú vùng: Môi trường, git, Windows

## Python
- Dùng `.venv\Scripts\python.exe` (3.13, pygame-ce 2.5.8). Python toàn máy là 3.15 beta và không có pygame: không dùng. `pip install` ngoài venv bị hook chặn; trong venv: `.venv\Scripts\python.exe -m pip install <gói>` rồi ghi vào `requirements.txt` cùng commit.
- Dựng lại venv nếu mất: `py -3.13 -m venv .venv` rồi `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
- Không có cửa sổ: `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy` (tools/tests tự đặt). Chạy game thật thì KHÔNG đặt hai biến này.
- Đọc/ghi file chữ (lang/*.json, tiến độ) luôn `encoding="utf-8"`.
- Đóng gói .exe (PyInstaller) chưa cài; cài khi người dùng yêu cầu phát hành.

## Shell
- PowerShell 5.1: không có `&&`/`||`; nối bằng `;` hoặc dùng Bash tool. Đường dẫn có dấu cách phải bọc nháy (`E:\pygame projects\NeonPool`).

## Git (cục bộ + repo GitHub công khai `origin`, từ 2026-10-31)
- Nhánh làm việc `chore/...`, `feat/...`, `fix/...`; `main` chỉ nhận khi người dùng nói push/gộp/merge/đưa lên main; sau khi gộp nhánh bị xoá bằng `git branch -d` (quy trình đầy đủ: CLAUDE.md §6b). Push lên `origin` chỉ khi người dùng nói "push" (hook chặn nếu không); không CI, cổng kiểm tra = `tools\gate.py` chạy tay. Bản exe: `tools\build_exe.py` (xem README).
- Trước mọi lệnh có thể xoá thay đổi chưa commit: `git status`. Hook chặn `reset --hard`, `clean -f`, `checkout -- `, `restore` (không `--staged`), `stash drop/clear`.
- Ảnh chụp, profile: `tools/_out/` (git bỏ qua). Trong `_out/` còn có file công cụ cần giữ (vd `tool-settings.json` của `shot.py`).
- Ảnh tạm của một việc (người dùng chốt 2026-10-30): luôn chụp vào thư mục con `tools/_out/<yyyymmdd>-<slug>/` (`shot.py --out` tự tạo thư mục cha), không để ảnh ở gốc `_out`. Giữ nguyên cho người dùng mở xem sau báo cáo. Xoá ĐÚNG thư mục đó (và chỉ nó) khi người dùng duyệt/gộp, hoặc giao việc MỚI (sửa tiếp chính việc đang làm thì giữ thư mục và ghi đè ảnh). Việc này được phép không hỏi (ngoại lệ ở CLAUDE.md §5). Ảnh của phiên cũ và file công cụ trong `_out/`: KHÔNG đụng, chỉ xoá khi người dùng nói xoá (hết hoặc một phần).

## Sự cố đã biết
(Thêm dòng có ngày khi gặp: `YYYY-MM-DD — hiện tượng — nguyên nhân — cách xử lý`.)
- 2026-10-28 — hình mờ, lỗ có răng cưa trên laptop HD — vẽ lên canvas cố định 1280×720 rồi phóng/thu, `pg.draw` không khử răng cưa; Windows có thể còn tự kéo giãn cửa sổ khi màn hình bật tỉ lệ 125%/150% — vẽ ở độ phân giải thật (`View`), gọi `SetProcessDpiAwareness` trước `pg.init()`, cỡ cửa sổ mở đầu tự vừa màn hình (`_start_size`).
- 2026-10-28 — `smoothscale` trên ảnh có alpha làm viền đen quanh bi — nó trộn màu của pixel trong suốt (đen) — nhân trước alpha (`premul_alpha`) rồi blit bằng `BLEND_PREMULTIPLIED`.
- 2026-10-28 — "Invalid font (font module quit since font created)" khi pygame tắt/bật lại (test) — phông đã cache chết theo `pg.quit()`; `register_quit` chỉ chạy một lần nên không đủ — `fonts.get` kiểm tra phông còn sống rồi tạo lại.
- 2026-10-30 — đo FPS menu cho kết quả lệch khỏi game thật, và `clock.tick(60)` ở máy không cửa sổ lúc giữ 60 lúc rơi ~38 FPS dù mã y hệt — script đo không bật `help.prefetch` (chỉ `run_forever` bật) nên bỏ sót đứng hình ~1 s lúc dựng trước; đồng hồ ngủ của Windows (độ phân giải timer) bị ảnh hưởng khi không có cửa sổ thấy được — đo bằng dt cố định và thời gian vẽ từng khung, bật prefetch, xem workflow/refactor.md mục 2.
- 2026-10-30 — luồng mạng trễ ~10–25 ms (p95 55 ms) mỗi lần gói về khi luồng chính đang bận vẽ/mô phỏng — trên Windows luồng nền chờ GIL bị làm tròn lên một nhịp đồng hồ (chu kỳ chuyển luồng mặc định 5 ms, 1 ms cũng vậy; DƯỚI 1 ms thì Python bỏ thời gian chờ và bàn giao ngay) — `tcp.py` đặt `sys.setswitchinterval(0.0002)` ở kết nối đầu tiên; đo lại bằng `tools\netbench.py --tcp` (0,37 ms p95).
- 2026-10-30 — lệnh Bash có heredoc chứa nhiều dấu nháy (mã Python có `'''`, chuỗi có `'`) báo "unexpected EOF while looking for matching" hoặc treo, nên một lần chạy dở không ghi gì — dùng công cụ Write ghi file `.py` rồi chạy, không nhét mã dài vào heredoc.
- 2026-10-30 — đổi tên thư mục dự án (`MathofPool` → `NeonPool`) giữa hai phiên — venv chỉ hỏng ở các script `activate*` và `pip.exe` (đường dẫn cũ ghi cứng); `python.exe` trong venv vẫn chạy — đã thử 2026-10-30: `pip.exe` thoát mã 1, `python.exe -m pip` chạy tốt — luôn gọi `.venv\Scripts\python.exe` (và `-m pip`) trực tiếp, không dùng `pip.exe`/`activate`.
- 2026-10-31 — `wrangler dev` (máy trung chuyển Cloudflare chạy máy mình) không nạp code mới, rồi thoát với `SQLITE_BUSY` — dừng tác vụ nền chỉ tắt `npx`, các tiến trình `node ...wrangler` và `workerd` con vẫn sống giữ cổng 8787 và khoá `.wrangler/state` — tắt hết `workerd` + `node` có dòng lệnh chứa `wrangler` (do chính mình bật) rồi chạy lại; đừng tin "Reloading" khi cổng còn tiến trình cũ. Thêm: ngày tương thích mới giao tin WebSocket nhị phân dạng `Blob` — đặt `ws.binaryType = "arraybuffer"` (đã có trong `server/cloudflare/src/index.js`).
- 2026-10-31 — gọi máy trung chuyển Cloudflare thật bằng `urllib` báo HTTP 403 "error code: 1010", game hiểu thành "máy chủ bận" — Cloudflare chặn tên trình khách mặc định của thư viện (Python-urllib); WebSocket của `websockets` thì qua được — mọi yêu cầu tới Cloudflare phải đặt `User-Agent` riêng (`relay.USER_AGENT`); bản máy mình (`wrangler dev`) và `server/local_relay.py` KHÔNG bắt được lỗi này nếu không bắt chước (local_relay đã bắt chước), nên chạy bộ test giao thức trên bản thật sau mỗi lần đổi `relay.py`: `$env:NEONPOOL_RELAY_TEST_URL="wss://neonpool-relay.neonpool-relay.workers.dev"`.
