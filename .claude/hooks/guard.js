// PreToolUse guard for Quote Studio. Runs before every tool call, in every permission mode.
//  - deny  any tool call that touches staff/ or reference/costing-and-margins.xlsx
//  - deny  force-pushes and GitHub repository deletion
//  - ask   before any other push to GitHub
// Reads the hook payload (JSON) on stdin and answers with a permissionDecision on stdout.

let raw = "";
process.stdin.on("data", (c) => (raw += c));
process.stdin.on("end", () => {
  let input;
  try {
    input = JSON.parse(raw);
  } catch {
    return deny("guard.js could not parse the hook input, so the call is blocked to be safe.");
  }
  const tool = input.tool_name || "";
  const ti = input.tool_input || {};
  const isShell = tool === "Bash" || tool === "PowerShell";

  // 1. Confidential paths. For shell commands check the command text; for every other tool check
  //    only path-like fields, so file *content* such as a "Service staff" quote line is not blocked.
  const PATH_FIELDS = ["file_path", "path", "notebook_path", "glob", "url", "cwd", "directory"];
  const texts = isShell
    ? [ti.command || ""]
    : PATH_FIELDS.map((k) => ti[k]).concat(tool === "Glob" ? [ti.pattern] : []).filter((v) => typeof v === "string");
  // "staff" as a folder name: a whole word not followed by "-" (so "staff-pay" wording is fine).
  const STAFF = /(^|[^a-z0-9_-])staff(?![a-z0-9_-])/i;
  const COSTING = /costing-and-margins/i;
  for (const t of texts) {
    const norm = t.replace(/\\\\?/g, "/");
    if (COSTING.test(norm) || STAFF.test(norm)) {
      return deny("Blocked by project rule: staff/ and reference/costing-and-margins.xlsx are confidential and must never be accessed.");
    }
  }

  if (!isShell) return allowThrough();
  const cmd = ti.command || "";

  // 2. GitHub repository deletion.
  if (/\bgh\s+repo\s+delete\b/i.test(cmd) || (/\bgh\s+api\b/i.test(cmd) && /(-X|--method)\s*DELETE\b/i.test(cmd) && /\brepos\//i.test(cmd))) {
    return deny("Blocked by project rule: deleting the GitHub repository is not allowed.");
  }

  // 3. Pushes. Split on shell separators and look at each git push segment on its own.
  const segments = cmd.split(/&&|\|\||[;|\n]/);
  let pushes = false;
  for (const seg of segments) {
    const ghPush = /\bgh\s+repo\s+(create|sync)\b/i.test(seg) && /--push\b|\bsync\b/i.test(seg);
    const gitPush = /\bgit\b(\s+-\S+(\s+\S+)?)*\s+push\b/i.test(seg);
    if (!gitPush && !ghPush) continue;
    pushes = true;
    if (/\s(-f|--force|--force-with-lease|--force-if-includes|--mirror)(?=[\s=]|$)/i.test(seg) || /\s-[a-z]*f[a-z]*(?=\s|$)/.test(seg) || /\s\+[^\s]+/.test(seg) || (/\bgh\s+repo\s+sync\b/i.test(seg) && /--force\b/i.test(seg))) {
      return deny("Blocked by project rule: force-pushing (--force, -f, --force-with-lease, +refspec, --mirror) is not allowed.");
    }
  }
  if (pushes) return ask("Project rule: every push to GitHub needs your approval.");
  return allowThrough();
});

function decide(decision, reason) {
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision: decision, permissionDecisionReason: reason },
  }));
}
function deny(reason) { decide("deny", reason); }
function ask(reason) { decide("ask", reason); }
// No output = no opinion: the normal permission rules decide.
function allowThrough() {}
