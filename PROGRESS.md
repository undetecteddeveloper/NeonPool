# PROGRESS — MathofPool

## Đang mở
- CHƯA BẬT HOOK: hệ thống từ chối Claude ghi `.claude/settings.json`. Ba hook trong `.claude/hooks/` đã thử chạy đúng nhưng chưa có hiệu lực. Bản đề xuất nằm ở `.claude/settings.proposed.json`: người dùng đổi tên thành `settings.json` (hoặc cho phép Claude làm) rồi mở lại phiên. Xong thì xoá mục này.
- Chưa có code game. Bước kế tiếp đề xuất (hướng sản phẩm đã chốt ở `docs/GAME_DESIGN.md`):
  1. Bàn + bi + va chạm bi–bi/bi–băng + lỗ, chưa xoáy (`game/physics`, có test bất biến).
  2. Kéo thả ngắm + lực → `Shot`; bộ thông số có tên (người dùng chọn cảm giác).
  3. Xoáy cao/thấp.
  4. Luật 8-ball tập một mình (`game/rules`).
  5. Menu + HUD + i18n vi/en.
  6. Nhập công thức toán → `Shot` (bản sau).

## Vừa xong
- 2026-10-28: dựng bộ workflow (CLAUDE.md, `.claude/workflow/`, 3 hook, `tools/gate.py`), venv Python 3.13 + pygame-ce 2.5.8 + pytest + ruff. Lý do: dự án mới, cần luật gọn + máy chặn những lỗi hay quên (push, commit lên main, cài thư viện ngoài venv).
