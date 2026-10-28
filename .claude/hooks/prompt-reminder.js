// UserPromptSubmit hook — hai việc:
//   1) bơm lại vài dòng nhắc (luật đầy đủ nằm ở CLAUDE.md, không chép vào đây);
//   2) ghi cờ "người dùng có nói gộp vào main trong lượt nhắn này không" cho guard.js đọc.
const fs = require("fs");
const os = require("os");
const path = require("path");

const REMINDER = [
  "[NHẮC — MathofPool] Luật đầy đủ: CLAUDE.md.",
  '1) Đầu việc nói "Tôi coi đây là <loại>", rồi đọc .claude/workflow/<loại>.md. Chỉ hỏi người dùng về hướng ĐỊNH HƯỚNG (thứ người chơi thấy/cảm thấy, viết bằng kết quả); kỹ thuật tự quyết.',
  '2) Công cụ thiếu/lỗi: thử lại 1 lần → báo ngay → ghi CHƯA LÀM → không nói "xong". Chỉ dùng .venv\\Scripts\\python.exe.',
  "3) Bất biến: physics/rules không import pygame · mọi cú đánh = Shot · bước cố định, mét–giây · hằng số trong config · chữ qua i18n vi+en · xác định theo seed.",
  "4) Xong việc: tools\\gate.py → commit trên nhánh → DỪNG. Không GitHub/push. Gộp main chỉ khi người dùng nói.",
  '5) Cảm giác bi/giao diện: không tự tuyên bố "ổn" — chụp ảnh/đưa bộ thông số có tên cho người dùng chọn.',
  '6) Báo cáo cuối: dòng đầu "ĐỦ BƯỚC" hoặc "THIẾU n BƯỚC: <bước> — <lý do> — <người dùng cần làm gì>".',
].join("\n");

const MERGE_INTENT = /(^|[^\p{L}\p{N}])(gộp|merge|đưa vào main|đưa lên main|vào main|lên main)([^\p{L}\p{N}]|$)/iu;

let data = "";
process.stdin.on("data", (c) => (data += c));
process.stdin.on("end", () => {
  try {
    const prompt = String(JSON.parse(data.replace(/^﻿/, "")).prompt || "").normalize("NFC");
    fs.writeFileSync(
      path.join(os.tmpdir(), "mathofpool-intent.json"),
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
