# Brief — Luyện tập nhiều chế độ: thêm "Gọi Lỗ" và "Nước Rút" (2026-11-04)

Nội dung người chơi thấy: `GAME_DESIGN.md` "Phản hồi lần 40". Nối tiếp brief `docs/plans/20261102-luyen-tap.md` (AC1–AC26); đánh số tiếp từ AC27. Brief này chỉ chốt cách làm và tiêu chí kiểm.

## Yêu cầu (người dùng, 2026-11-04)
Luyện tập hiện chỉ có MỘT bài (trên màn gọi là "Đấu Ma"; tài liệu cũ gọi "Thử Ma", trong code là `GhostRun`). Người dùng xin thêm chế độ; sau khi xem nghiên cứu bài tập bida một người, chọn qua câu hỏi: THÊM HAI BÀI **Gọi Lỗ** và **Nước Rút**; chọn bài ở BƯỚC RIÊNG (hai bước); bi vào NHẦM lỗ ở Gọi Lỗ = trượt, mất 1 mạng; kỷ lục RIÊNG từng bài.

## Quyết định (kèm lý do)
| Chỗ | Chọn | Vì |
|---|---|---|
| Tên chế độ | khoá `"ghost"` (Đấu Ma), `"call"` (Gọi Lỗ / Call the Pocket), `"sprint"` (Nước Rút / Sprint); `config.PRACTICE_MODES` | khoá ổn định cho code, settings, dev tool; chữ trên màn qua `i18n` |
| Cấu trúc luật | `CallRun` và `SprintRun` kế thừa `GhostRun`; `make_run(mode, rng)` dựng đúng loại | hai bài chỉ khác điều kiện thành công / phạt; mọi thứ còn lại (bi mục tiêu ngẫu nhiên có đường vào lỗ, cầm tay, cú phá không mục tiêu) dùng lại nguyên. Đấu Ma giữ hành vi, mọi test cũ phải xanh |
| Gọi Lỗ: lỗ chỉ định | thêm `physics/pot_lines.pot_pockets` (trả CHỈ SỐ lỗ đánh thẳng được; `pot_lines` = `len(pot_pockets)`); lỗ chọn ngẫu nhiên đều (`World.rng`) trong các lỗ đó | cùng bộ đếm đường của lần 39, không viết hình học mới |
| Gọi Lỗ chặt hơn: `CALL_MAX_CUT_DEG` = 45 (Đấu Ma 75) | lỗ chỉ định phải có góc cắt ≤ 45° (đo bằng bot: lỗ cắt 45–60° chỉ vào 52% dù ngắm hoàn hảo) | ở Đấu Ma người chơi tự chọn lỗ dễ nhất trong số lỗ có đường; ở Gọi Lỗ lỗ bị GIAO nên không được giao lỗ gần như bất khả thi |
| Vào nhầm lỗ | `lost_life = practice.miss`; bi đó vẫn xuống bàn và tính vào `pocketed`, chọn mục tiêu mới | người dùng chọn "nhầm lỗ = trượt"; bi đã rơi thì không đặt lại được |
| Nước Rút: giờ chung | `SPRINT_START_S` 60, `SPRINT_CAP_S` 90; vào +12 s; trượt −4 s; bi cái rơi lỗ −8 s (đã chỉnh sau khi đo bằng bot: số đầu +8/−5/−10 quá khắc nghiệt) (cầm tay, không mất gì thêm) | thay đồng hồ từng cú bằng MỘT quỹ giờ: vào bi thì có thêm giờ, sai thì hao; hết giờ là thua. Cú phá không phạt trượt (như Đấu Ma) nhưng bi cái rơi lỗ vẫn trừ |
| Nước Rút: giờ chỉ chạy khi được ngắm | `SprintRun.tick(dt)` do scene gọi mỗi khung chỉ lúc `_can_aim()`, cùng điều kiện đồng hồ cú của Đấu Ma | bi đang lăn không ăn giờ của người chơi; đúng cách đã chọn cho đồng hồ cú. Không đếm giờ trong 7 s đếm ngược đầu ván |
| Nước Rút: không có mạng | `lives` không đổi, không hiện hàng mạng; không đồng hồ từng cú | áp lực đã đến từ giờ; thêm mạng là hai lớp phạt chồng nhau |
| Nước Rút: điểm | `streak` = số bi vào (nhãn "Bi vào" / "Balls", khoá `practice.potted`) | "Chuỗi" không đúng nghĩa khi trượt không dừng ván |
| Hai bước chọn | bảng Chơi: Chơi đơn → Tự do / Luyện tập → [bước `PRACTICE`] Đấu Ma / Gọi Lỗ / Nước Rút; Esc / Quay lại lùi một bước | người dùng chọn; ba nút lớn cùng kiểu bước MODE (`hud.live_button(..., sub=)`, cao 76, cách 12) |
| Kỷ lục riêng | `settings.practice_best_call`, `practice_best_sprint` cạnh `practice_best`; `PRACTICE_BEST_FIELD`, `best_for(settings, mode)` | điểm các bài không so sánh được với nhau (có mạng / có giờ) |
| Dấu lỗ trên bàn | thành phần chung MỚI `draw.draw_pocket_call` (vòng sáng nhấp nháy quanh lỗ chỉ định, không che bi) | một chức năng một thành phần (CLAUDE.md §1.7); ghi ở bảng "Thành phần UI dùng chung" |
| Bốn con số của Nước Rút | 60 / 90 / +12 / −4 / −8 (và `CALL_MAX_CUT_DEG` 45) là TỰ CHỌN, CHƯA AI CHƠI THỬ | không có số liệu để suy ra; chờ người dùng chơi thử rồi chỉnh |

Nguồn nghiên cứu: chỉ là KẾT QUẢ TÌM KIẾM hạn chế (nhiều trang không truy cập được nên không đọc được nội dung đầy đủ). Từ đó Claude đề xuất năm dạng (Gọi Lỗ, Nước Rút, Giữ Bi Trắng, Gôn, Chạy bàn tăng dần) và người dùng chọn hai dạng đầu. Mọi con số của hai bài là SUY LUẬN của Claude, không lấy từ nguồn nào.

## Tiêu chí chấp nhận
**Luật** (`tests/test_pot_lines.py`, `tests/test_practice_rules.py`, `tests/test_settings_and_controls.py`)
- AC27 `pot_pockets(...)` trả chỉ số lỗ (index vào `POCKETS`) có đường đánh thẳng, cùng điều kiện như `pot_lines`; `pot_lines` giữ chữ ký và bằng `len(pot_pockets)`; thuần, không pygame (`test_ac27_…`).
- AC28 `make_run("ghost"|"call"|"sprint", rng)` trả `GhostRun`/`CallRun`/`SprintRun`, thuộc tính lớp `mode` đúng; `GhostRun` hành vi không đổi, test AC1–AC26 vẫn xanh (`test_ac28_…`).
- AC29 `CallRun.pocket`: lỗ chỉ định luôn nằm trong `pot_pockets(..., max_cut_deg=CALL_MAX_CUT_DEG)` của bi mục tiêu lúc gán; xác định theo hạt giống; `None` ở cú phá và khi hết bi (`test_ac29_…`).
- AC30 `CallRun`: bi mục tiêu vào ĐÚNG lỗ = thành công (`hit`, `streak`+1); vào lỗ KHÁC = `practice.miss`, mất 1 mạng, bi vẫn xuống bàn và vào `pocketed`, chọn mục tiêu mới; bi cái rơi lỗ = `foul.scratch` như cũ (`test_ac30_…`).
- AC31 `CallRun` sau một cú trượt: (bi, lỗ) còn đường thì giữ; mất đường thì đổi lỗ (cùng bi nếu còn lỗ khác) hoặc đổi bi, `target_swapped = True`; không bao giờ để `pocket` trỏ vào lỗ không có đường lúc gán (`test_ac31_…`).
- AC32 `SprintRun`: bắt đầu `SPRINT_START_S`; `tick(dt)` trừ giờ, về ≤ 0 khi đang chơi → `LOST`, `lost_life = practice.time_up`; vào bi +`SPRINT_POT_BONUS_S` (không quá `SPRINT_CAP_S`), trượt −`SPRINT_MISS_COST_S`, bi cái rơi lỗ −`SPRINT_SCRATCH_COST_S` (cầm tay); không mất mạng; cú phá không phạt trượt; hết 15 bi = `WON` (`test_ac32_…`).
- AC33 Kỷ lục riêng: `practice_best_call`, `practice_best_sprint` (kẹp 0..15, chỉ tăng, còn nguyên sau khi tắt mở game); `best_for(settings, mode)` đọc đúng trường (`test_ac33_…`).

**Giao diện & vòng đời** (`tests/test_play_panel*.py`, `tests/test_practice_scene.py`, `tests/test_dev_tool.py`, chụp ảnh)
- AC34 Menu hai bước: bấm "Luyện tập" ở bước MODE mở bước `PRACTICE` (chưa vào bàn); bấm Đấu Ma / Gọi Lỗ / Nước Rút vào đúng chế độ (`App.go_practice(mode)`); "Quay lại" về MODE; mọi nút vừa khung và dòng mô tả chừa ≥ 40 px mỗi bên (như AC20) ở vi và en.
- AC35 Gọi Lỗ: lỗ chỉ định có vòng sáng nhấp nháy trên bàn khi chơi (không hiện lúc đếm ngược hay khi `pocket is None`); dòng gợi ý nói "vào đúng lỗ sáng"; đổi lỗ / đổi bi có thông báo riêng.
- AC36 Nước Rút: ô ĐẾM hiện giờ chung (làm tròn lên, nhãn "Giờ"/"Time"; đỏ nháy ở 10 s cuối), KHÔNG vẽ hàng mạng, nhãn ô điểm "Bi vào"/"Balls"; giờ chỉ chạy khi được ngắm và không chạy trong đếm ngược; đang Hướng dẫn thì đứng yên.
- AC37 Thẻ kết quả và kỷ lục theo chế độ: nhãn điểm và lý do thua đúng chế độ (Nước Rút: "Hết giờ"); hàng "Kỷ lục" đọc và cập nhật đúng trường của chế độ đó; ván mới (R, thẻ kết quả) GIỮ chế độ hiện tại.
- AC38 `tools/dev.py --check` và smoke qua mọi chế độ (ván mới, đang chơi, thắng, thua) không sập.
- AC39 Chữ vi và en đủ cho mọi khoá mới (`practice.mode.*`, `*_sub`, `practice.time`, `practice.potted`, `practice.time_up`, các dòng riêng của Gọi Lỗ) và vừa nút / ô ở cả hai ngôn ngữ.

## File
Mã: `game/config.py`, `game/physics/pot_lines.py`, `game/rules/practice.py`, `game/settings.py`, `game/scenes/practice.py`, `game/scenes/play_panel.py`, `game/app.py`, `game/render/draw.py`, `game/render/hud.py` · Chữ: `lang/vi.json`, `lang/en.json` · Công cụ: `tools/devkit/states.py`, `tools/devkit/harness.py`, `tools/shot.py` · Test: `tests/test_pot_lines.py`, `tests/test_practice_rules.py`, `tests/test_practice_scene.py`, `tests/test_play_panel*.py`, `tests/test_settings_and_controls.py`, `tests/test_dev_tool.py` · Tài liệu: `docs/GAME_DESIGN.md` (lần 40), `docs/ARCHITECTURE.md`, `PROGRESS.md`.

## Ngoài phạm vi
- Giữ Bi Trắng (đưa bi cái về vùng chỉ định), Gôn, Chạy bàn tăng dần: đã nghiên cứu, người dùng CHƯA chọn; để sau nếu họ muốn.
- Hướng dẫn chơi (`lang/*.json` trang Hướng dẫn, `help_pictures.py`) chưa nói gì về Luyện tập (từ lần 30); không thêm ở đợt này.
- Mạng ở Nước Rút, đồng hồ từng cú ở Nước Rút, màn chọn độ khó, âm thanh riêng cho chế độ mới, nhãn "kỷ lục mới!".
