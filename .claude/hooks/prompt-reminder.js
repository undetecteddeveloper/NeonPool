// UserPromptSubmit hook — hai việc:
//   1) bơm lại vài dòng nhắc (luật đầy đủ nằm ở CLAUDE.md, không chép vào đây);
//   2) ghi cờ "người dùng có nói gộp vào main trong lượt nhắn này không" cho guard.js đọc.
const fs = require("fs");
const os = require("os");
const path = require("path");

const REMINDER = [
  "[NHẮC — NeonPool] Luật đầy đủ: CLAUDE.md.",
  '1) Đầu việc nói "Tôi coi đây là <loại>", rồi đọc .claude/workflow/<loại>.md, rồi XÁC NHẬN CÁCH HIỂU (CLAUDE.md §1b): "Tôi hiểu: <kết quả người chơi thấy>" + AskUserQuestion (hiểu đúng chưa? + chọn hướng nếu ≥2) cho MỌI yêu cầu xây/sửa/xoá, kể cả bug (điều tra trước) và chỉnh nhỏ giao diện. Chỉ làm thẳng: hỏi đáp/đọc code, xem git, chính tả, tạo/gộp/xoá/push nhánh. Câu hỏi nói bằng kết quả người chơi thấy; kỹ thuật tự quyết.',
  "1b) Giao diện: cùng chức năng = cùng một thành phần dùng chung, cùng thiết kế ở mọi màn (workflow/ui.md 4d, bảng ở ARCHITECTURE.md); muốn khác thì hỏi. Yêu cầu làm lệch quyết định đã chốt → rà mọi tài liệu cùng commit (CLAUDE.md §3b). Ảnh chụp vào tools\\_out\\<yyyymmdd>-<slug>\\, xoá thư mục đó khi người dùng duyệt hoặc giao việc mới (ops-env.md).",
  '2) Công cụ thiếu/lỗi: thử lại 1 lần → báo ngay → ghi CHƯA LÀM → không nói "xong". Chỉ dùng .venv\\Scripts\\python.exe.',
  "3) Bất biến: physics/rules không import pygame · mọi cú đánh = Shot · bước cố định, mét–giây · hằng số trong config · chữ qua i18n vi+en · xác định theo seed.",
  '4) Xong việc: tools\\gate.py → commit trên nhánh → DỪNG. Không GitHub/push thật. Người dùng nói push/gộp/merge/đưa lên main = gộp vào main cục bộ rồi xoá nhánh bằng `git branch -d` (CLAUDE.md §6b). Việc mới: tách từ main; còn nhánh chưa gộp thì HỎI người dùng trước.',
  '5) Cảm giác bi/giao diện: không tự tuyên bố "ổn" — chụp ảnh/đưa bộ thông số có tên cho người dùng chọn.',
  '6) Báo cáo cuối: dòng đầu "ĐỦ BƯỚC" hoặc "THIẾU n BƯỚC: <bước> — <lý do> — <người dùng cần làm gì>".',
].join("\n");

const MERGE_INTENT = /(^|[^\p{L}\p{N}])(push|gộp|merge|đưa vào main|đưa lên main|vào main|lên main)([^\p{L}\p{N}]|$)/iu;

let data = "";
process.stdin.on("data", (c) => (data += c));
process.stdin.on("end", () => {
  try {
    const prompt = String(JSON.parse(data.replace(/^﻿/, "")).prompt || "").normalize("NFC");
    fs.writeFileSync(
      path.join(os.tmpdir(), "neonpool-intent.json"),
      JSON.stringify({ merge: MERGE_INTENT.test(prompt), at: Date.now() })
    );
  } catch {
    // Không ghi được cờ thì guard.js coi như chưa có ý gộp (an toàn hơn).
  }
  process.stdout.write(
    JSON.stringify({ hookSpecificOutput: { hookEventName: "UserPromptSubmit", additionalContext: REMINDER } })
  );
  process.exit(0);
});
