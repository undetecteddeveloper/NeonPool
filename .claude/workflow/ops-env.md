# Ghi chú vùng: Môi trường, git, Windows

## Python
- Dùng `.venv\Scripts\python.exe` (3.13, pygame-ce 2.5.8). Python toàn máy là 3.15 beta và không có pygame: không dùng. `pip install` ngoài venv bị hook chặn; trong venv: `.venv\Scripts\python.exe -m pip install <gói>` rồi ghi vào `requirements.txt` cùng commit.
- Dựng lại venv nếu mất: `py -3.13 -m venv .venv` rồi `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
- Không có cửa sổ: `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy` (tools/tests tự đặt). Chạy game thật thì KHÔNG đặt hai biến này.
- Đọc/ghi file chữ (lang/*.json, tiến độ) luôn `encoding="utf-8"`.
- Đóng gói .exe (PyInstaller) chưa cài; cài khi người dùng yêu cầu phát hành.

## Shell
- PowerShell 5.1: không có `&&`/`||`; nối bằng `;` hoặc dùng Bash tool. Đường dẫn có dấu cách phải bọc nháy (`E:\pygame projects\MathofPool`).

## Git (chỉ cục bộ, không GitHub)
- Nhánh làm việc `chore/...`, `feat/...`, `fix/...`; `main` chỉ nhận bằng "gộp" khi người dùng nói. Không có remote nên không push, không CI; cổng kiểm tra = `tools\gate.py` chạy tay.
- Trước mọi lệnh có thể xoá thay đổi chưa commit: `git status`. Hook chặn `reset --hard`, `clean -f`, `checkout -- `, `restore` (không `--staged`), `stash drop/clear`.
- Ảnh chụp, profile: `tools/_out/` (git bỏ qua).

## Sự cố đã biết
(Thêm dòng có ngày khi gặp: `YYYY-MM-DD — hiện tượng — nguyên nhân — cách xử lý`.)
