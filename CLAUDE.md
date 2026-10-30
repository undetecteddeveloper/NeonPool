# NeonPool — luật làm việc

> Luật riêng của dự án này. Luật dùng chung mọi project (tiếng Việt, ĐỦ BƯỚC/THIẾU, không hoàn tác, commit rồi dừng) nằm ở `~/.claude/CLAUDE.md` — không chép lại ở đây.
> Luật theo loại việc: `.claude/workflow/`. Thiết kế đã chốt: `docs/GAME_DESIGN.md`. Kiến trúc: `docs/ARCHITECTURE.md`. Tiến độ: `PROGRESS.md`.
> Sửa luật = sửa TẠI CHỖ nó thuộc về (§7), không tạo file mới.

## 1. Bất biến của dự án (vi phạm = lỗi, kể cả khi test xanh)
1. `game/physics/` và `game/rules/` KHÔNG import pygame: chỉ toán thuần, để test không cần cửa sổ.
2. Mọi cách nhập (hôm nay là kéo thả; sau này thêm cách nào cũng vậy) chỉ tạo ra MỘT thứ: `Shot(angle, power, spin)`. Vật lý không biết cú đánh đến từ đâu.
3. Vật lý chạy bước thời gian CỐ ĐỊNH (`PHYSICS_DT`), đơn vị mét–giây; đổi sang pixel CHỈ ở lớp vẽ (`PX_PER_M`).
4. Mọi hằng số vật lý và cảm giác (ma sát, độ nảy, lực đánh) nằm trong `game/config.py` hoặc bộ thông số có tên — không số "ma thuật" trong code.
5. Mọi chữ hiện lên màn hình đi qua `i18n.t("khoa")` (vi + en). Khoá hay chuỗi cứng lộ ra màn hình là lỗi.
6. Cùng `Shot` + cùng `seed` → cùng kết quả từng bước (xác định). Không `random` ngoài `World.rng`.
7. Một chức năng giao diện = MỘT thành phần dùng chung trong `game/render/`, ghi ở bảng "Thành phần UI dùng chung" của `docs/ARCHITECTURE.md`; cùng chức năng thì cùng thiết kế ở mọi màn (chi tiết, chỗ được khác: `workflow/ui.md` 4d). Test không bắt được lỗi này và người dùng khó nhìn ra, nên Claude tự soi mỗi lần đụng giao diện.

## 1b. Cách hỏi người dùng
Người dùng không chuyên kỹ thuật. Mọi câu hỏi (AskUserQuestion) là câu ĐỊNH HƯỚNG: hỏi về thứ người chơi nhìn thấy/cảm thấy (luật, cảm giác bi, bố cục, độ khó, thứ tự làm), mỗi lựa chọn viết bằng KẾT QUẢ ("bi trắng lùi sau khi va chạm"), có một lựa chọn khuyến nghị ghi rõ và ví dụ cụ thể khi được. KHÔNG hỏi thư viện, cấu trúc code, tên hàm, kiểu dữ liệu — tự quyết rồi nói một dòng lý do.

**Xác nhận cách hiểu (người dùng chốt 2026-10-30; thay câu cũ "không có hướng nào khác biệt thì không hỏi")**: mỗi yêu cầu xây/sửa/xoá — kể cả báo lỗi (tái hiện + điều tra trước, rồi mới hỏi) — Claude viết 1–2 dòng `Tôi hiểu: <kết quả người chơi sẽ thấy>` rồi AskUserQuestion: một câu "hiểu đúng chưa?" (đúng / hiểu khác) cộng các câu chọn hướng khi có ≥2 cách khác nhau (≤4 câu/vòng). Người dùng trả lời xong mới làm. Lý do: người dùng cần thấy Claude hiểu thế nào và còn quyền chọn trước khi tốn công làm sai. Chỉ những việc sau làm thẳng, không hỏi: hỏi đáp / đọc / giải thích code; xem git và trạng thái; sửa chính tả hoặc câu chữ không đổi nghĩa; yêu cầu tạo / gộp / xoá / push nhánh (làm theo §6b; §5 về việc không hoàn tác vẫn áp). "Chỉnh nhỏ giao diện" (một màu, khoảng cách, cỡ chữ) KHÔNG được miễn — vẫn hỏi.

## 2. Đầu phiên (hook SessionStart đã in sẵn; Claude PHẢI làm)
1. Báo MỘT dòng `Công cụ: đủ` hoặc `THIẾU: <tên> — <cách khắc phục>` dựa trên dữ liệu hook (venv, pygame-ce, pytest, ruff, nhánh git).
2. Báo ≤3 dòng việc dang dở từ "Đang mở" của PROGRESS.md, hỏi có tiếp không. Không tự nối việc cũ.
3. Hook in dòng "Nhánh chưa gộp quá 1 ngày": có nhánh thì thêm MỘT dòng `Còn n nhánh chưa gộp: ...` và hỏi có gộp + dọn không (§6b); không có thì không nói gì.

## 3. Phân loại — mọi yêu cầu bắt đầu ở đây
Nói MỘT dòng: "Tôi coi đây là <loại>: <việc>". Không chắc loại nào thì gộp câu hỏi đó vào bảng của §1b. Rồi ĐỌC file đường, rồi xác nhận cách hiểu (§1b), RỒI MỚI làm:

| Loại | Dấu hiệu | File |
|---|---|---|
| Việc vặt | sửa nhỏ, hỏi đáp, đọc code, git, sửa tài liệu | `workflow/small.md` |
| Bug | báo lỗi, "sai", "kẹt", "xuyên bi", "crash" | `workflow/bug.md` |
| Tính năng | thêm chức năng, đổi hành vi, thêm luật | `workflow/feature.md` |
| Giao diện | menu, HUD, bố cục, hoạt ảnh, màu, chữ | `workflow/ui.md` |
| Vật lý & cảm giác | va chạm, ma sát, xoáy, độ nảy, lực đánh, "bi chạy lạ" | `workflow/physics.md` |
| Dọn code / hiệu năng | refactor, FPS, tách module, viết thêm test | `workflow/refactor.md` |

Shell, git, Windows, venv, lỗi môi trường → `workflow/ops-env.md`. (Thư mục `workflow/` nằm trong `.claude/`.)

## 3b. Yêu cầu làm lệch quyết định đã chốt (người dùng chốt 2026-10-30; áp cho MỌI đường)
Khi người dùng đổi ý, hoặc việc đang làm khiến code không còn khớp một quyết định tài liệu đã ghi — để không phải trả nợ về sau:
1. TRƯỚC khi làm: Grep thứ cũ trong `docs/GAME_DESIGN.md`, `docs/ARCHITECTURE.md`, `docs/plans/`, `PROGRESS.md`, `lang/*.json` (chữ Hướng dẫn nói luật/phím), `game/scenes/help_pictures.py`, `tests/`, `.claude/workflow/`, file này. Trong dòng `Tôi hiểu` (§1b) nói rõ: quyết định cũ là gì (file:dòng) → nay đổi thành gì.
2. Sửa MỌI chỗ lệch trong cùng commit. Mục "hiện hành" (bảng "Đã chốt", "Đồ họa…", ARCHITECTURE.md) sửa tại chỗ cho khớp. Các mục "Phản hồi lần N" là nhật ký: không viết lại, thêm mục "Phản hồi lần N+1" ghi đổi gì và vì sao, và đánh dấu `(đã đổi ở lần N+1)` ở dòng cũ nếu nó còn đọc như đang hiệu lực. Không thêm file mới. Chỗ chưa rõ thay bằng gì → thêm câu vào bảng §1b, không tự đoán.
3. Cuối việc, trước dòng `ĐỦ BƯỚC`: Grep lại từ khoá cũ; còn sót thì sửa hoặc báo. Báo cáo ghi `Đã đối chiếu tài liệu: <n> file, sửa <m> chỗ` (hoặc `không có chỗ lệch`).

## 4. Công cụ thiếu hoặc lỗi
Theo luật chung (thử lại 1 lần → báo ngay → CHƯA LÀM). Riêng dự án này:
- Python CHỈ dùng `.venv\Scripts\python.exe` (3.13 + pygame-ce). `python` toàn máy là 3.15 beta, KHÔNG có pygame — dùng nó là sai (hook chặn `pip install` ngoài venv).
- Cổng kiểm tra không chạy được → DỪNG phần liên quan, không commit như thể cổng đã qua. Một cổng đỏ: chạy lại trên bản sạch (`git worktree add` ra thư mục tạm) để biết do mình hay đỏ sẵn.
- Cấm viết "xong / ổn" cho bước chưa chạy thật. "Giao diện ổn" chỉ khi đã chụp ảnh và nhìn ảnh (ui.md). "Cảm giác ổn" không bao giờ do Claude tuyên bố — chỉ người dùng (physics.md).

## 5. Điểm dừng bắt buộc
- Hướng sản phẩm/thiết kế có ≥2 phương án (luật chơi, cảm giác, bố cục người chơi thấy) → AskUserQuestion (≤4 câu/vòng).
- Việc không hoàn tác (xoá file/thư mục, `reset --hard`, `clean`, bỏ thay đổi chưa commit, ghi đè save của người chơi): nói hệ quả bằng lời thường rồi hỏi có/không. Chạy `git status` trước (hook chặn các lệnh này). MỘT ngoại lệ đã được cho phép lâu dài (2026-10-30): thư mục ảnh chụp tạm do chính Claude tạo ở `tools/_out/<yyyymmdd>-<slug>/`, xoá theo `ops-env.md`; mọi thứ khác trong `tools/_out/` chỉ xoá khi người dùng nói xoá.
- Ngoài hai loại trên Claude tự quyết, kể cả thêm thư viện hay đổi kiến trúc (thêm thư viện: vào `requirements.txt` cùng commit).

## 6. Kết thúc việc
1. Cổng, xác nhận bằng exit code thật: `.venv\Scripts\python.exe tools\gate.py`
   - Việc vặt: `gate.py --quick` (ruff check + format + pytest).
   - Bug / tính năng / giao diện / vật lý / refactor chạm code: `gate.py` đầy đủ (thêm smoke headless: bật game 300 khung hình, báo ms/khung). Chỉ sửa tài liệu hoặc luật: bỏ cổng.
2. Commit trên nhánh làm việc (không bao giờ commit thẳng `main`/`master`), message tiếng Việt `type(scope): ...`, rồi DỪNG. Mỗi commit một việc.
3. Dự án này CHỈ dùng git cục bộ: không GitHub, không remote, không push (hook chặn `git push` và `git remote add`). "Đưa lên main" = gộp nhánh làm việc vào `main` cục bộ, chỉ khi người dùng nói "push"/"gộp"/"merge"/"đưa lên main" (hook chặn mọi `commit`/`merge` đang đứng trên main nếu lượt nhắn gần nhất không có từ nào trong số đó). Quy trình gộp và dọn nhánh: §6b.
4. Cập nhật PROGRESS.md: số đo và LÝ DO, không chỉ liệt kê việc.
5. Đối chiếu §4–§5 một lượt (việc lệch quyết định cũ: cả §3b.3), rồi viết dòng đầu `ĐỦ BƯỚC` / `THIẾU …`.
6. Ảnh chụp của việc này: để nguyên cho người dùng mở xem (ghi đường dẫn trong báo cáo); xoá thư mục của việc khi người dùng duyệt hoặc giao việc mới (`ops-env.md`).

## 6b. Vòng đời nhánh (người dùng chốt 2026-10-29: không để nhánh tồn đọng)
1. Mỗi việc một nhánh, tách từ `main` mới nhất (`git switch -c feat/<tên> main`). KHÔNG tách chồng lên nhánh chưa gộp.
2. Trước khi tạo nhánh cho việc mới: `git branch --no-merged main`. Còn nhánh chưa gộp → AskUserQuestion MỘT câu: "gộp việc cũ trước (rồi dọn)" hoặc "bỏ qua: tách việc mới từ main, việc cũ để riêng". Không tự chọn thay người dùng.
3. Người dùng nói push/gộp/merge/đưa lên main: nói một dòng "Tôi hiểu là gộp nhánh X vào main" rồi làm tuần tự: `git status` sạch → `git switch main` (chưa có `main`: `git branch main <nhánh gốc của chuỗi>` trước) → `git merge <nhánh>` (nhánh chồng nhau: gộp từ gốc lên) → chạy `gate.py` trên main nếu không phải fast-forward → xoá nhánh đã gộp bằng `git branch -d` → báo "Đã dọn nhánh X" và nói đang đứng ở nhánh nào.
4. `git branch -d` (tự từ chối nếu còn commit chưa gộp); `-D` bị hook chặn. Gộp xung đột hoặc gate đỏ trên main: dừng, báo người dùng, KHÔNG xoá nhánh (xung đột chưa hoàn tất: `git merge --abort`).
5. Worktree tạm (`git worktree add` để chạy cổng trên bản sạch): xoá ngay sau khi dùng (`git worktree remove <thư mục>`). Cuối việc `git worktree list` chỉ còn thư mục chính.
6. Đầu phiên hook liệt kê nhánh chưa gộp quá 1 ngày → §2.3.

## 7. Tự học
Người dùng sửa cùng một lỗi lần thứ hai → Claude sửa luật có sẵn ở đúng file (file này hoặc một file đường): thay luật cũ cùng chủ đề, không thêm file. Báo một dòng "Đã ghi luật: …". KHÔNG ghi luật hay nhật ký sự kiện vào auto-memory. Sự cố môi trường mới → thêm một dòng có ngày vào `ops-env.md`.

## 8. Bản đồ
- Chạy game: `.venv\Scripts\python.exe main.py` · Test: `.venv\Scripts\python.exe -m pytest` · Chụp khung hình: `.venv\Scripts\python.exe tools\shot.py --frames 60 --out tools\_out\<yyyymmdd>-<slug>\a.png` (luôn vào thư mục con của việc, không để ảnh ở gốc `_out`) rồi Read ảnh.
- Tiến độ: `PROGRESS.md` (chỉ việc đang mở và vừa xong, ≤60 dòng, tự cắt mục cũ — lịch sử đã có trong git log).
- Mã nguồn game: `game/` · chuỗi giao diện: `lang/vi.json`, `lang/en.json` · công cụ: `tools/`.
