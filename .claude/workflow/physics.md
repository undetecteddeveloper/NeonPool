# Đường: Vật lý & cảm giác

Va chạm, ma sát, xoáy, độ nảy băng, lực đánh, "bi chạy lạ". Đây là chỗ dễ sai nhất của dự án: lỗi thường im lặng (bi vẫn chạy nhưng sai).

## Trước khi đổi
1. Đọc `GAME_DESIGN.md` (mục tham chiếu vật lý + nguồn) và `ARCHITECTURE.md`. Công thức mới phải ghi nguồn (bài báo / tài liệu) hoặc ghi rõ "tự đặt" trong chú thích và GAME_DESIGN.md.
2. Giữ bất biến §1: `physics/` thuần, bước cố định, mét–giây, hằng số trong config, xác định theo seed.

## Bộ test bất biến (có từ ngày đầu của `physics/`; đổi vật lý mà làm đỏ bộ này là sai, không sửa test cho xanh)
- Không chồng lấn: sau mỗi bước, mọi cặp bi cách tâm ≥ 2R − ε; không bi nào ra ngoài băng trừ khi vào lỗ.
- Năng lượng động năng tổng không tăng sau cú đánh (trừ va chạm có xoáy được mô hình hoá — nêu rõ trong test). Với xoáy: đánh cao CÓ tăng nhẹ tốc độ bi trắng trên đường tới (ma sát trượt đổi xoáy thành tốc độ, `world._slide`), nên bất biến này chỉ áp cho cú xoáy 0 (`test_energy_never_increases`); cú có xoáy phải dừng hẳn, ở trong bàn, không chồng lấn (`tests/test_spin.py`).
- Va chạm bi–bi thẳng, không ma sát, cùng khối lượng: trao nguyên vận tốc.
- Xác định: cùng seed + `Shot` → trạng thái giống từng bit sau N bước.
- Không xuyên: `Shot` lực tối đa vào băng/vào bi đứng yên không bao giờ xuyên qua.
- Mọi bi dừng hẳn trong ≤ T giây (không rung vô hạn).
- Xoáy: đánh cao → bi trắng chạy tới sau va chạm thẳng; đánh thấp → lùi (kiểm dấu vận tốc); xoáy 0 y hệt bản không xoáy (`tests/test_spin.py`, và dấu vân tay kết quả một loạt cú khi đổi vật lý).

## Chỉnh cảm giác (người dùng không chuyên: Claude không tự tuyên bố "ổn")
1. Dựng 2–3 bộ thông số CÓ TÊN trong `config.py` (vd `BAN_TRON`, `BAN_CHAM`), mỗi bộ ghi một dòng "cảm giác thế nào" bằng lời thường.
2. Đưa kèm số đo dễ hiểu: "bi trắng lăn bao lâu thì dừng", "nảy ra khỏi băng còn bao nhiêu % tốc độ". Không đưa hệ số trần.
3. Người dùng chơi thử rồi chọn (CLAUDE.md §1b). Chốt thì ghi vào GAME_DESIGN.md; các bộ không chọn xoá đi.

## Kết thúc
`gate.py` đầy đủ (bộ test bất biến phải xanh); commit `feat/fix(physics): ...`; PROGRESS.md ghi số đo trước/sau. Báo cáo dòng đầu `ĐỦ BƯỚC` / `THIẾU …`.
