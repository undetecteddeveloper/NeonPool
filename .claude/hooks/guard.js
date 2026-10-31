// PreToolUse hook — chặn CỨNG những thứ máy kiểm được (luật bằng chữ dễ bị quên):
//   - `git push`: chỉ khi lượt nhắn gần nhất của người dùng có từ "push" (cờ do prompt-reminder.js ghi); `--force` luôn bị chặn;
//   - đang đứng trên main/master: chặn commit/rebase/cherry-pick/reset; `merge` chỉ khi lượt nhắn gần
//     nhất của người dùng có ý gộp (cờ do prompt-reminder.js ghi);
//   - lệnh git xoá thay đổi chưa commit (reset --hard, clean -f, checkout --, restore, stash drop/clear);
//   - `pip install` ngoài .venv (python toàn máy là 3.15 beta, không có pygame).
// Hook tự hỏng thì lệnh vẫn đi qua (không chặn oan) nhưng báo lỗi ra stderr để người dùng thấy.
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");

function deny(reason) {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: reason },
    })
  );
}

function mergeIntent() {
  try {
    const flag = JSON.parse(fs.readFileSync(path.join(os.tmpdir(), "neonpool-intent.json"), "utf8"));
    return flag.merge === true;
  } catch {
    return false;
  }
}

function currentBranch(cwd) {
  try {
    return execFileSync("git", ["branch", "--show-current"], { cwd, encoding: "utf8", timeout: 5000 }).trim();
  } catch {
    return "";
  }
}

// Bỏ nội dung trong dấu nháy trước khi tách lệnh: chuỗi như 'git push' hay commit message
// chứa "; git push" không phải là lệnh thật.
const stripQuoted = (cmd) => cmd.replace(/'[^']*'|"(?:[^"\\]|\\.)*"/g, '""');
const segments = (cmd) => stripQuoted(cmd).split(/&&|\|\||[;&|\r\n]/).map((s) => s.trim()).filter(Boolean);
// `git [-C x | -c k=v | --opt]* <sub> <rest>`
const GIT = /^git\s+(?:(?:-C|-c)\s+\S+\s+|--[\w-]+(?:=\S+)?\s+)*([\w-]+)(?:\s+(.*))?$/i;
const PIP_INSTALL = /(?:^|\s)(?:pip3?(?:\.exe)?|-m\s+pip)\s+install(?:\s|$)/i;

let data = "";
process.stdin.on("data", (c) => (data += c));
process.stdin.on("end", () => {
  try {
    const input = JSON.parse(data.replace(/^﻿/, ""));
    const cmd = String((input.tool_input && input.tool_input.command) || "");
    const cwd = input.cwd || process.cwd();
    let branch = null;

    for (const seg of segments(cmd)) {
      const g = GIT.exec(seg);
      if (g) {
        const sub = g[1].toLowerCase();
        const rest = (g[2] || "").toLowerCase();
        if (sub === "push") {
          if (/(^|\s)(-f|--force\S*)(\s|$)/.test(rest)) {
            deny("`git push --force` ghi đè lịch sử trên GitHub, không khôi phục dễ (CLAUDE.md §5). Không dùng; hỏi người dùng nếu thật sự cần.");
            return finish();
          }
          if (!mergeIntent()) {
            deny("Chỉ push lên GitHub khi người dùng nói \"push\" ở lượt nhắn gần nhất (CLAUDE.md §6). Hỏi người dùng trước.");
            return finish();
          }
        }
        const raw = g[2] || ""; // giữ nguyên hoa/thường: `-D` khác `-d`
        const forceDelete =
          sub === "branch" &&
          (/(^|\s)-[a-zA-Z]*D[a-zA-Z]*(\s|$)/.test(raw) ||
            (/(^|\s)(-[a-zA-Z]*d[a-zA-Z]*|--delete)(\s|$)/.test(raw) && /(^|\s)(-f|--force)(\s|$)/.test(raw)));
        if (forceDelete) {
          deny("`git branch -D` xoá nhánh dù còn commit chưa gộp, không khôi phục dễ (CLAUDE.md §6b). Dùng `git branch -d`: nó tự từ chối nếu nhánh chưa gộp vào main.");
          return finish();
        }
        const destructive =
          (sub === "reset" && /--hard/.test(rest)) ||
          (sub === "clean" && /(^|\s)-\w*[fd]/.test(rest)) ||
          (sub === "checkout" && /(^|\s)--(\s|$)/.test(rest)) ||
          (sub === "restore" && !/--staged/.test(rest)) ||
          (sub === "stash" && /^(drop|clear)\b/.test(rest));
        if (destructive) {
          deny(`\`git ${sub}\` có thể xoá thay đổi chưa commit, không khôi phục được (CLAUDE.md §5). Chạy \`git status\`, nói hệ quả bằng lời thường và hỏi người dùng có/không trước.`);
          return finish();
        }
        if (["commit", "merge", "rebase", "cherry-pick", "reset"].includes(sub)) {
          if (branch === null) branch = currentBranch(cwd);
          if (branch === "main" || branch === "master") {
            if (sub === "merge" && mergeIntent()) continue;
            deny(`Đang đứng trên \`${branch}\`: không commit/merge thẳng lên nhánh chính (CLAUDE.md §6). Chuyển sang nhánh làm việc (\`git switch -c feat/<tên>\`). Muốn gộp vào main thì người dùng phải nhắn "gộp"/"merge".`);
            return finish();
          }
        }
      }
      if (PIP_INSTALL.test(seg) && !/\.venv/i.test(cmd)) {
        deny("Chỉ cài thư viện vào .venv: `.venv\\Scripts\\python.exe -m pip install <gói>` rồi ghi vào requirements.txt (CLAUDE.md §4).");
        return finish();
      }
    }
  } catch (e) {
    // Hook tự hỏng: KHÔNG được im lặng. Exit 1 = lỗi không chặn nhưng hiện ra cho người dùng thấy.
    process.stderr.write(`guard.js lỗi (${e.message}) — lớp bảo vệ KHÔNG chạy cho lệnh này\n`);
    process.exit(1);
  }
  finish();
});

function finish() {
  process.exit(0);
}
