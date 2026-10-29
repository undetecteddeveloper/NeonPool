// SessionStart hook — in sẵn dữ liệu đầu phiên để Claude không phải nhớ:
//   1) kiểm CƠ HỌC công cụ (venv, pygame-ce, pytest, ruff, nhánh git);
//   2) phần "Đang mở" của PROGRESS.md.
// Gốc project suy từ vị trí file này, không từ cwd.
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const root = path.resolve(__dirname, "..", "..");
const venv = path.join(root, ".venv");
const site = path.join(venv, "Lib", "site-packages");

function has(rel) {
  return fs.existsSync(path.join(root, rel));
}

function openProgress() {
  try {
    const text = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8").replace(/\r/g, "");
    const start = text.indexOf("## Đang mở");
    if (start < 0) return "(PROGRESS.md không có mục '## Đang mở' — báo người dùng)";
    const end = text.indexOf("\n## ", start + 5);
    const lines = text.slice(start, end < 0 ? undefined : end).split("\n").slice(0, 40);
    return lines.map((l) => (l.length > 400 ? l.slice(0, 400) + "…" : l)).join("\n");
  } catch {
    return "(không đọc được PROGRESS.md — báo người dùng)";
  }
}

function branch() {
  try {
    const b = execFileSync("git", ["branch", "--show-current"], { cwd: root, encoding: "utf8", timeout: 5000 }).trim();
    return b || "(chưa có nhánh/chưa commit)";
  } catch {
    return "KHÔNG phải git repo — chạy `git init`";
  }
}

// Nhánh làm việc chưa gộp vào main mà commit mới nhất đã quá 1 ngày (CLAUDE.md §6b.6).
// Chưa có `main` thì mọi nhánh khác đều tính là chưa gộp.
function staleBranches() {
  const git = (args) => execFileSync("git", args, { cwd: root, encoding: "utf8", timeout: 5000 }).trim();
  try {
    let hasMain = true;
    try {
      git(["rev-parse", "--verify", "--quiet", "refs/heads/main"]);
    } catch {
      hasMain = false;
    }
    const rows = git(["for-each-ref", "--format=%(refname:short)|%(committerdate:unix)", "refs/heads"])
      .split("\n")
      .filter(Boolean);
    const now = Date.now() / 1000;
    const stale = [];
    for (const row of rows) {
      const [name, ts] = row.split("|");
      if (name === "main" || name === "master") continue;
      if (hasMain) {
        try {
          git(["merge-base", "--is-ancestor", name, "main"]);
          continue; // đã gộp
        } catch {
          // chưa gộp: xét tuổi bên dưới
        }
      }
      const days = Math.floor((now - Number(ts)) / 86400);
      if (days >= 1) stale.push(`${name} (${days} ngày)`);
    }
    return stale.length ? stale.join(", ") : "không có";
  } catch {
    return "(không kiểm được — chạy `git branch --no-merged main`)";
  }
}

const missing = [];
if (!has(".venv/Scripts/python.exe")) missing.push(".venv (py -3.13 -m venv .venv)");
else {
  if (!fs.existsSync(path.join(site, "pygame"))) missing.push("pygame-ce");
  if (!fs.existsSync(path.join(site, "pytest"))) missing.push("pytest");
  if (!has(".venv/Scripts/ruff.exe")) missing.push("ruff");
}
const toolsLine = missing.length
  ? `THIẾU: ${missing.join(", ")} — khắc phục: .venv\\Scripts\\python.exe -m pip install -r requirements.txt`
  : "đủ (venv, pygame-ce, pytest, ruff)";
const gateLine = has("tools/gate.py") ? "có tools/gate.py" : "THIẾU tools/gate.py";
const br = branch();
const brWarn = br === "main" || br === "master" ? " — ĐANG Ở NHÁNH CHÍNH: tạo nhánh làm việc trước khi sửa" : "";

const context = [
  "[PHIÊN MỚI — NeonPool] Làm CLAUDE.md §2 NGAY, trước việc đầu tiên: báo MỘT dòng về công cụ, rồi ≤3 dòng việc dang dở và hỏi có tiếp không.",
  "Hook đã kiểm cơ học:",
  `- Công cụ Python: ${toolsLine}`,
  `- Cổng kiểm tra: ${gateLine}`,
  `- Nhánh git: ${br}${brWarn}`,
  `- Nhánh chưa gộp quá 1 ngày: ${staleBranches()}`,
  "--- PROGRESS.md ---",
  openProgress(),
].join("\n");

process.stdout.write(
  JSON.stringify({ hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: context } })
);
process.exit(0);
