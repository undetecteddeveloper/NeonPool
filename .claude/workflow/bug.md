# Đường: Bug

Mặc định Claude tự tìm nguyên nhân, tự sửa, rồi báo lại — không chờ duyệt.

1. Tái hiện trước bằng thứ máy chạy lại được: test pytest đỏ (với lỗi vật lý: dựng `World(seed)` + `Shot` cố định, mô phỏng N bước); với lỗi hiển thị: `tools\shot.py` chụp ảnh trước và nhìn ảnh. Không tái hiện được → báo, đừng đoán rồi sửa.
2. Tìm NGUYÊN NHÂN, không vá triệu chứng. Lỗi "ngẫu nhiên" thì tìm chỗ vi phạm bất biến §1 (`random` ngoài rng, dt không cố định, thứ tự set/dict). Trước khi kết luận cổng đỏ là do mình, đối chiếu `ops-env.md`.
3. Sửa tối thiểu: test đỏ → xanh, giữ test làm bảo hiểm. Cùng nguyên nhân còn ở nơi khác (Grep) thì sửa cùng đợt và nêu trong báo cáo.
4. Nguyên nhân chưa rõ sau lần điều tra đầu: thu thập quan sát (số liệu, ảnh, log) rồi báo người dùng đang biết gì, chưa biết gì. Không đoán.
5. Chỉ dừng hỏi khi cách sửa đổi điều người chơi THẤY/CẢM THẤY (≥2 hướng) — hỏi theo CLAUDE.md §1b.
6. Kết thúc: `gate.py` đầy đủ nếu chạm code; commit `fix(scope): ...`. Báo cáo: dòng đầu `ĐỦ BƯỚC` / `THIẾU …`; nguyên nhân MỘT câu; đã sửa gì; số đo trước/sau.
