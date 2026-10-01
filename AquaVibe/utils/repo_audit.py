"""Static repository audit for AquaVibe.

This is intentionally conservative: it reports suspicious/error-prone patterns
and gives an actionable fix, but it never rewrites source code automatically.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY_ROOT = ROOT / "AquaVibe"

EXTERNAL_IMPORT_MAP = {
    "aiofiles": "aiofiles", "aiohttp": "aiohttp", "bs4": "bs4", "edge_tts": "edge-tts",
    "heroku3": "heroku3", "httpx": "httpx", "pyrogram": "pyrofork", "motor": "motor",
    "nekosbest": "nekosbest", "ntgcalls": "ntgcalls", "PIL": "pillow", "psutil": "psutil",
    "pytgcalls": "py-tgcalls", "pydub": "pydub", "pymongo": "pymongo", "pyshorteners": "pyshorteners",
    "qrcode": "qrcode", "requests": "requests", "spotipy": "spotipy", "unidecode": "unidecode",
    "urllib3": "urllib3", "yt_dlp": "yt-dlp", "whois": "python-whois", "speedtest": "speedtest-cli",
    "yaml": "pyyaml",
}
SECRET_RE = re.compile(r"(?i)(api[_-]?(?:key|hash)|bot[_-]?token|password|passwd|secret|authorization)\s*[=:]\s*['\"][^'\"]{8,}['\"]")
COMMAND_RE = re.compile(r"filters\.command\(\s*(\[[^\]]+\]|['\"][^'\"]+['\"])" )


def _suggest(kind: str) -> str:
    return {
        "syntax": "Fix the syntax error at the reported file/line, then rerun the audit before deployment.",
        "missing_dep": "Add the missing third-party package to requirements.txt (or remove the import) and rebuild the image.",
        "bare_except": "Catch the specific exception and log it with traceback; avoid silently swallowing failures.",
        "swallowed": "Replace except/pass with a targeted fallback plus LOGGER.warning/error(..., exc_info=True).",
        "shell": "Avoid shell execution where possible; use subprocess.run([...], shell=False) with validated arguments.",
        "dynamic": "Remove eval/exec unless absolutely required; use a safe parser or explicit dispatch.",
        "secret": "Move the credential to an environment variable/secret and rotate the exposed credential.",
        "todo": "Review the TODO/FIXME and either implement it or document why it is intentionally deferred.",
        "duplicate_command": "Rename/remove the duplicate command registration or merge the handlers so only one handler owns the command.",
        "build": "Restore the missing build/runtime file so Railway can install and start the bot predictably.",
    }.get(kind, "Inspect the reported location and apply the smallest targeted fix.")


def audit_repo() -> dict:
    issues: list[dict] = []
    stats = Counter()
    python_files = sorted(ROOT.rglob("*.py"))
    third_party = Counter()
    commands = []

    for path in python_files:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            issues.append({"severity": "ERROR", "kind": "read", "file": str(path.relative_to(ROOT)), "line": 0, "message": str(exc), "fix": "Make the file readable or remove the broken artifact."})
            continue
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            stats["syntax"] += 1
            issues.append({"severity": "ERROR", "kind": "syntax", "file": str(path.relative_to(ROOT)), "line": exc.lineno or 0, "message": exc.msg, "fix": _suggest("syntax")})
            continue

        rel = str(path.relative_to(ROOT))
        lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in EXTERNAL_IMPORT_MAP:
                        third_party[root] += 1
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in EXTERNAL_IMPORT_MAP:
                    third_party[root] += 1
            elif isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    stats["bare_except"] += 1
                    issues.append({"severity": "WARNING", "kind": "bare_except", "file": rel, "line": node.lineno, "message": "Bare except catches every exception and can hide real bugs.", "fix": _suggest("bare_except")})
                if any(isinstance(x, ast.Pass) for x in node.body):
                    stats["swallowed"] += 1
                    issues.append({"severity": "WARNING", "kind": "swallowed", "file": rel, "line": node.lineno, "message": "Exception is swallowed with pass.", "fix": _suggest("swallowed")})
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                    stats["dynamic"] += 1
                    issues.append({"severity": "WARNING", "kind": "dynamic", "file": rel, "line": node.lineno, "message": f"Dynamic {node.func.id}() call detected.", "fix": _suggest("dynamic")})
                if isinstance(node.func, ast.Attribute) and node.func.attr in {"system", "popen"}:
                    stats["shell"] += 1
                    issues.append({"severity": "WARNING", "kind": "shell", "file": rel, "line": node.lineno, "message": f"os.{node.func.attr}() detected.", "fix": _suggest("shell")})

        for i, line in enumerate(lines, 1):
            if SECRET_RE.search(line) and "os.getenv" not in line and "getenv(" not in line and "REDACTED" not in line:
                stats["secret"] += 1
                issues.append({"severity": "HIGH", "kind": "secret", "file": rel, "line": i, "message": "Possible hard-coded credential/secret pattern.", "fix": _suggest("secret")})
            if re.search(r"\b(TODO|FIXME|XXX)\b", line, re.I):
                stats["todo"] += 1
                issues.append({"severity": "INFO", "kind": "todo", "file": rel, "line": i, "message": line.strip()[:300], "fix": _suggest("todo")})

        for m in COMMAND_RE.finditer(source):
            raw = m.group(1)
            if raw.startswith("["):
                names = re.findall(r"['\"]([^'\"]+)['\"]", raw)
            else:
                names = re.findall(r"['\"]([^'\"]+)['\"]", raw)
            for name in names:
                commands.append((name.lower(), rel, source[:m.start()].count("\n") + 1))

    # Build sanity checks.
    for required in ("requirements.txt", "Dockerfile", "start", "config.py"):
        if not (ROOT / required).exists():
            stats["build"] += 1
            issues.append({"severity": "ERROR", "kind": "build", "file": required, "line": 0, "message": "Required deployment file is missing.", "fix": _suggest("build")})

    req_text = (ROOT / "requirements.txt").read_text(encoding="utf-8", errors="ignore") if (ROOT / "requirements.txt").exists() else ""
    req_names = {re.split(r"[<>=!~\[]", x.strip().lower())[0].replace("_", "-") for x in req_text.splitlines() if x.strip() and not x.lstrip().startswith("#")}
    local_roots = {"AquaVibe", "strings", "config", "log_config"}
    for mod, count in third_party.items():
        package = EXTERNAL_IMPORT_MAP[mod].lower()
        if package not in req_names and package != "pyrofork":
            stats["missing_dep"] += 1
            issues.append({"severity": "ERROR", "kind": "missing_dep", "file": "requirements.txt", "line": 0, "message": f"Imported module '{mod}' maps to package '{package}' but it is not declared.", "fix": _suggest("missing_dep")})

    cmd_counts = Counter(name for name, _, _ in commands)
    for name, count in sorted(cmd_counts.items()):
        if count > 1:
            entries = [(f, l) for n, f, l in commands if n == name]
            stats["duplicate_command"] += 1
            issues.append({"severity": "WARNING", "kind": "duplicate_command", "file": entries[0][0], "line": entries[0][1], "message": f"Command '/{name}' is registered {count} times: {entries}.", "fix": _suggest("duplicate_command")})

    # Compile using the same interpreter that runs the audit command.
    try:
        proc = subprocess.run(["python", "-m", "compileall", "-q", str(ROOT)], capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            stats["compile"] += 1
            issues.append({"severity": "ERROR", "kind": "syntax", "file": "compileall", "line": 0, "message": (proc.stderr or proc.stdout).strip()[-3000:], "fix": _suggest("syntax")})
    except Exception as exc:
        issues.append({"severity": "WARNING", "kind": "compile", "file": "compileall", "line": 0, "message": str(exc), "fix": "Run python -m compileall manually in the deployment image."})

    severity_order = {"HIGH": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}
    issues.sort(key=lambda x: (severity_order.get(x["severity"], 9), x.get("file", ""), x.get("line", 0)))
    return {
        "summary": {
            "python_files": len(python_files),
            "issues": len(issues),
            "high": sum(x["severity"] == "HIGH" for x in issues),
            "errors": sum(x["severity"] == "ERROR" for x in issues),
            "warnings": sum(x["severity"] == "WARNING" for x in issues),
            "info": sum(x["severity"] == "INFO" for x in issues),
            "stats": dict(stats),
            "third_party_imports": dict(third_party),
        },
        "issues": issues,
    }


def render_report(report: dict) -> str:
    s = report["summary"]
    out = [
        "AQUAVIBE REPOSITORY AUDIT",
        "=" * 72,
        f"Python files: {s['python_files']}",
        f"Issues: {s['issues']} | HIGH: {s['high']} | ERROR: {s['errors']} | WARNING: {s['warnings']} | INFO: {s['info']}",
        "",
    ]
    if not report["issues"]:
        out.append("PASS: no static issues detected by the built-in audit rules.")
        return "\n".join(out)
    for i, item in enumerate(report["issues"], 1):
        out.extend([
            f"[{i}] {item['severity']} | {item['kind']}",
            f"File: {item['file']}:{item.get('line', 0)}",
            f"Problem: {item['message']}",
            f"Fix: {item['fix']}",
            "-" * 72,
        ])
    return "\n".join(out)


def write_report(report: dict, path: str | Path | None = None) -> Path:
    path = Path(path or (ROOT / "repo_audit_report.txt"))
    path.write_text(render_report(report), encoding="utf-8")
    (ROOT / "repo_audit_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
