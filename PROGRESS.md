# PROGRESS — MathofPool

## Đang mở
- MVP đang làm trên nhánh `feat/mvp`, theo brief `docs/plans/20261028-mvp.md` (T1 vật lý → T2 vẽ + kéo thả → T3 âm thanh + hiệu ứng → T4 menu + i18n + bảng bên + cửa sổ). Sau MVP: người dùng chơi thử và chọn bộ cảm giác bi (phím 1/2/3 đổi bộ khi chơi).
- Sau MVP (đã chốt thứ tự ở `GAME_DESIGN.md`): xoáy cao/thấp → luật 8-ball tập một mình → công thức toán.

## Vừa xong
- 2026-10-28: dựng bộ workflow (CLAUDE.md, `.claude/workflow/`, 3 hook đã bật, `tools/gate.py`), venv Python 3.13 + pygame-ce + pytest + ruff. Lý do: dự án mới, cần luật gọn + máy chặn những lỗi hay quên (push, commit lên main, cài thư viện ngoài venv).
- 2026-10-28: chốt đồ họa/âm thanh/giao diện/phạm vi MVP qua 3 vòng hỏi (ghi ở `GAME_DESIGN.md`).
