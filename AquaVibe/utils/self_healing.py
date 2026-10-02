"""Owner-approved self-healing proposals.

The AI may inspect an error and prepare a patch, but it never writes production
files until OWNER_ID explicitly approves the proposal in Telegram.

How a proposal is made (and why it is more reliable than a full-file rewrite):

1. Only real code bugs are analysed (AttributeError, KeyError, NameError ...).
   Network errors, FloodWait, Telegram permission errors etc. are skipped, and
   the same error is analysed at most once per ``SELF_HEALING_COOLDOWN``.
2. The AI receives the traceback, the failing line with numbered context and the
   file, and answers with a small list of exact ``old`` -> ``new`` edits (not a
   whole new file), so it cannot silently drop or rewrite unrelated code.
3. Every edit must match the file exactly once.  The patched file is then
   checked *before* the owner ever sees it: valid Python, no top-level
   definitions lost, changes limited to the failing area (or imports), small
   diff, and no risky calls added.  Anything that fails a check is discarded.
4. On APPROVE the file is re-checked against the current version on disk, backed
   up, written atomically, compile-tested, and rolled back if anything fails.
"""
from __future__ import annotations

import ast
import asyncio
import difflib
import hashlib
import io
import json
import logging
import os
import re
import shutil
import sys
import time
import traceback
import uuid
from html import escape
from pathlib import Path

from pyrogram.types import InlineKeyboardMarkup

import config
from AquaVibe.core.runtime import app
from AquaVibe.utils.ai import ask
from AquaVibe.utils.colored_buttons import ColoredInlineKeyboardButton
from AquaVibe.utils.database import create_healing_issue, get_healing_issue, mark_healing_issue

InlineKeyboardButton = ColoredInlineKeyboardButton
_LOG = logging.getLogger("AquaVibe.self_healing")
ROOT = Path(__file__).resolve().parents[2]
HEAL_DIR = ROOT / "AquaVibeBackup" / "self_healing"
HEAL_DIR.mkdir(parents=True, exist_ok=True)

# Exceptions that point at a bug in our source.  Everything else (network,
# FloodWait, permissions, missing packages ...) cannot be fixed by editing a file.
_CODE_BUGS = (
    AttributeError, TypeError, KeyError, IndexError, NameError, UnboundLocalError,
    ValueError, ZeroDivisionError, AssertionError, UnicodeError, StopIteration,
)
_SKIP_DIRS = ("__pycache__", "AquaVibeBackup")
_SELF = Path(__file__).resolve()

_SEEN: dict[str, float] = {}          # fingerprint -> last analysed time
_RECENT: list[float] = []             # timestamps of analyses, for the hourly cap
_MAX_PER_HOUR = 6
_LOCK = asyncio.Lock()                # one analysis at a time

_RISKY = re.compile(
    r"\b(os\.system|os\.popen|subprocess|eval\s*\(|exec\s*\(|__import__|shutil\.rmtree|"
    r"os\.remove|os\.unlink|os\.rmdir|rmtree|socket\.|pickle\.loads|marshal\.loads)\b"
)
_SECRET = re.compile(r"(?i)(api[_-]?key|token|secret|password|mongo(?:db)?(?:\+srv)?://)\s*[=:]\s*['\"][^'\"]{8,}")

SYSTEM = (
    "You are a senior Python engineer repairing a production Telegram bot (Pyrogram/Pyrofork, asyncio, MongoDB). "
    "You fix exactly one runtime error with the smallest correct change. "
    "You never guess: if the cause is not visible in the given file (environment, config, another module, "
    "network, permissions, bad user input that is already handled), you say so instead of inventing a fix."
)


# ───────────────────────── helpers ─────────────────────────
def _fingerprint(error: BaseException, rel: str, lineno: int) -> str:
    msg = re.sub(r"\d+", "N", str(error))[:200]          # 12345 and 67890 are the same bug
    return hashlib.sha256(f"{type(error).__name__}|{msg}|{rel}|{lineno}".encode("utf-8", "replace")).hexdigest()[:20]


def _project_frames(error: BaseException):
    out = []
    for f in (traceback.extract_tb(error.__traceback__) if error.__traceback__ else []):
        try:
            p = Path(f.filename).resolve()
            p.relative_to(ROOT)
        except Exception:
            continue
        if p == _SELF or any(part in _SKIP_DIRS for part in p.parts):
            continue
        out.append((p, f))
    return out


def _numbered(source: str, lineno: int, radius: int) -> str:
    lines = source.splitlines()
    lo, hi = max(0, lineno - 1 - radius), min(len(lines), lineno + radius)
    return "\n".join(f"{i + 1:5d}{'>' if i + 1 == lineno else ' '}| {lines[i]}" for i in range(lo, hi))


def _extract_json(text: str) -> dict | None:
    """Pull the first valid JSON object out of a reply (handles fences / chatter)."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    dec = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = dec.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _apply_edits(source: str, edits) -> tuple[str | None, str]:
    """Apply exact-match edits. Each ``old`` must occur exactly once."""
    if not isinstance(edits, list) or not edits:
        return None, "no edits returned"
    if len(edits) > 8:
        return None, "too many edits"
    content = source
    for n, e in enumerate(edits, 1):
        if not isinstance(e, dict) or not isinstance(e.get("old"), str) or not isinstance(e.get("new"), str):
            return None, f"edit {n} is malformed"
        old, new = e["old"], e["new"]
        if not old.strip():
            return None, f"edit {n} has an empty 'old' snippet"
        if old == new:
            return None, f"edit {n} changes nothing"
        count = content.count(old)
        if count != 1:
            return None, f"edit {n}: snippet matched {count} times (must be exactly 1)"
        content = content.replace(old, new, 1)
    return content, ""


def _top_level_names(tree: ast.AST) -> set[str]:
    names = set()
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


def _enclosing_range(tree: ast.AST, lineno: int) -> tuple[int, int]:
    """Line range of the innermost function containing ``lineno`` (fallback: +-40 lines)."""
    best = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            if node.lineno <= lineno <= end and (best is None or node.lineno > best[0]):
                best = (node.lineno, end)
    return best or (max(1, lineno - 40), lineno + 40)


def _validate(rel: str, old: str, new: str, lineno: int) -> tuple[bool, str, int]:
    """Return (ok, reason, changed_line_count) for a candidate patched file."""
    if new == old:
        return False, "patch changes nothing", 0
    if rel.endswith(".py"):
        try:
            new_tree = ast.parse(new)
            compile(new, rel, "exec")
        except SyntaxError as exc:
            return False, f"patched file is not valid Python ({exc.msg}, line {exc.lineno})", 0
        try:
            old_tree = ast.parse(old)
        except SyntaxError:
            old_tree = None
        if old_tree is not None:
            lost = _top_level_names(old_tree) - _top_level_names(new_tree)
            if lost:
                return False, "patch removes top-level definitions: " + ", ".join(sorted(lost)[:5]), 0
            lo, hi = _enclosing_range(old_tree, lineno)
        else:
            lo, hi = max(1, lineno - 40), lineno + 40
    else:
        lo, hi = 1, 10 ** 9

    old_lines, new_lines = old.splitlines(), new.splitlines()
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    changed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        changed += max(i2 - i1, j2 - j1)
        removed = old_lines[i1:i2]
        added = new_lines[j1:j2]
        import_only = all(re.match(r"\s*(from\s+\S+\s+import|import)\s", l) or not l.strip() for l in removed + added)
        inside = i1 + 1 <= hi and i2 >= lo - 1          # hunk overlaps the failing function / window
        if not inside and not import_only:
            return False, f"patch edits unrelated code (lines {i1 + 1}-{i2}) far from the failing line {lineno}", changed
        for line in added:
            if _RISKY.search(line) and not _RISKY.search("\n".join(old_lines)):
                return False, "patch adds a risky call: " + line.strip()[:80], changed
            if _SECRET.search(line):
                return False, "patch contains something that looks like a secret", changed
    limit = int(getattr(config, "SELF_HEALING_MAX_CHANGED_LINES", 80))
    if changed > limit:
        return False, f"patch is too large ({changed} lines changed, limit {limit})", changed
    return True, "", changed


def _build_prompt(error, tb: str, label: str, rel: str, source: str, lineno: int, frames) -> str:
    cap = int(getattr(config, "SELF_HEALING_MAX_INPUT", 60000))
    if len(source) <= cap - 12000:
        file_block = source
        note = "FULL FILE"
    else:  # very large file: send the area around the failure (snippets must still match exactly)
        lines = source.splitlines()
        lo, hi = max(0, lineno - 1 - 300), min(len(lines), lineno + 300)
        file_block = "\n".join(lines[lo:hi])
        note = f"EXCERPT (lines {lo + 1}-{hi} of {len(lines)})"
    chain = "\n".join(f"  {p.relative_to(ROOT).as_posix()}:{f.lineno} in {f.name}" for p, f in frames[-6:])
    err_text = f"{type(error).__name__}: {error}"
    return f"""Fix this runtime error in the file `{rel}`.

ERROR ({label}):
{err_text}

PROJECT FRAMES (oldest -> newest, the last one is where it failed):
{chain}

FAILING LINE ({rel}:{lineno}, marked with >):
{_numbered(source, lineno, 25)}

TRACEBACK:
{tb[-6000:]}

{note} of `{rel}` (raw text; your snippets must match this exactly):
<<<FILE
{file_block}
FILE>>>

RULES
1. Work out the root cause from the traceback and the code, then fix only that.
2. Reply with ONE JSON object and nothing else:
   {{"cannot_fix": false, "confidence": "high|medium|low", "root_cause": "one sentence",
     "summary": "what you changed, one or two sentences",
     "edits": [{{"old": "exact existing text", "new": "replacement text"}}]}}
3. Each "old" must be copied character for character from the file (keep indentation), include enough
   surrounding text to appear exactly once, and be as short as possible. Use 1-3 edits. Never return the whole file.
4. Keep function names, signatures, behaviour and code style. Do not refactor, rename, reformat or add features.
5. Only edit `{rel}`. Do not add new dependencies, shell/eval/exec calls, network calls or secrets.
6. If the error comes from environment, configuration, another file, a network/Telegram limit, or cannot be fixed
   safely here, reply {{"cannot_fix": true, "reason": "why", "edits": []}}.
7. Prefer guarding the bad value (None checks, .get(), try/except on the exact failing call) over hiding errors broadly."""


# ───────────────────────── proposal ─────────────────────────
async def propose(error: BaseException, tb: str, label: str = "Runtime Error"):
    if not config.SELF_HEALING_ENABLED or not config.LOGGER_ID:
        return
    if not isinstance(error, _CODE_BUGS):
        return                                   # not something a source edit can fix
    frames = _project_frames(error)
    if not frames:
        return
    path, frame = frames[-1]
    if path.suffix != ".py" or not path.exists() or path.stat().st_size > 2 * 1024 * 1024:
        return
    rel = path.relative_to(ROOT).as_posix()

    fp = _fingerprint(error, rel, frame.lineno)
    now = time.time()
    cooldown = int(getattr(config, "SELF_HEALING_COOLDOWN", 3600))
    if now - _SEEN.get(fp, 0) < cooldown:
        return
    _RECENT[:] = [t for t in _RECENT if now - t < 3600]
    if len(_RECENT) >= _MAX_PER_HOUR:
        return
    _SEEN[fp] = now
    if len(_SEEN) > 500:
        for k in sorted(_SEEN, key=_SEEN.get)[:100]:
            _SEEN.pop(k, None)

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return
    base_sha = hashlib.sha256(source.encode("utf-8", "replace")).hexdigest()

    async with _LOCK:
        _RECENT.append(time.time())
        prompt = _build_prompt(error, tb, label, rel, source, frame.lineno, frames)
        data = None
        failure = ""
        # Up to two tries: the second one tells the AI exactly why the first was rejected.
        for attempt in (1, 2):
            try:
                reply = await asyncio.wait_for(
                    ask(
                        prompt if attempt == 1 else prompt + f"\n\nYour previous answer was rejected: {failure}\nReturn a corrected JSON object.",
                        system=SYSTEM,
                        max_tokens=int(getattr(config, "SELF_HEALING_MAX_TOKENS", 8000)),
                        temperature=0.1,
                        max_input=int(getattr(config, "SELF_HEALING_MAX_INPUT", 60000)),
                        timeout=150,
                        prefer="Anthropic",
                        strict=True,
                    ),
                    timeout=180,
                )
            except Exception as exc:
                failure = f"AI request failed: {type(exc).__name__}"
                _LOG.warning("self-healing: %s (%s)", failure, rel)
                return
            obj = _extract_json(reply)
            if not obj:
                failure = "the reply was not a valid JSON object"
                continue
            if obj.get("cannot_fix"):
                return                               # the AI says a source edit is not the right fix
            new_content, why = _apply_edits(source, obj.get("edits"))
            if new_content is None:
                failure = why
                continue
            ok, why, changed = _validate(rel, source, new_content, frame.lineno)
            if not ok:
                failure = why
                continue
            data = (obj, new_content, changed)
            break
        if not data:
            _LOG.info("self-healing: no proposal for %s (last rejection: %s)", rel, failure)
            return
        obj, new_content, changed = data

        try:
            issue_id = uuid.uuid4().hex[:12]
            confidence = str(obj.get("confidence", "medium")).lower()
            if confidence not in {"high", "medium", "low"}:
                confidence = "medium"
            summary = str(obj.get("summary") or "Targeted repair proposal")
            root = str(obj.get("root_cause") or "")
            await create_healing_issue(issue_id, {
                "status": "pending", "file": rel, "new_content": new_content, "edits": obj["edits"],
                "base_sha256": base_sha, "line": frame.lineno, "confidence": confidence,
                "summary": summary, "root_cause": root, "changed_lines": changed,
                "error": f"{type(error).__name__}: {error}\n{tb}"[:6000], "created_at": time.time(),
            })
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👀 VIEW DIFF", callback_data=f"avheal:view:{issue_id}"),
                 InlineKeyboardButton("❌ REJECT", callback_data=f"avheal:reject:{issue_id}")],
                [InlineKeyboardButton("✅ APPROVE", callback_data=f"avheal:approve:{issue_id}")],
            ])
            icon = {"high": "🟢", "medium": "🟡", "low": "🟠"}[confidence]
            msg = (
                f"🚨 <b>Claude Error Found</b>\n\n"
                f"📁 File: <code>{escape(rel)}</code>\n📍 Line: <code>{frame.lineno}</code>\n\n"
                f"❌ <b>Error:</b>\n<code>{escape(str(error))[:1200]}</code>\n\n"
                + (f"🔎 <b>Root cause:</b>\n{escape(root[:600])}\n\n" if root else "")
                + f"💡 <b>Proposed fix:</b>\n{escape(summary[:1200])}\n\n"
                f"{icon} Confidence: <b>{confidence}</b> · {changed} line(s) changed · checked: valid Python, "
                f"no definitions removed, edits limited to the failing area\n\n"
                f"🔐 <b>Production repository is unchanged.</b>\nOwner approval is required before any write."
            )
            await app.send_message(config.OWNER_ID, msg, reply_markup=keyboard)
        except Exception as exc:
            _LOG.warning("self-healing: could not deliver proposal for %s to OWNER_ID: %s", rel, exc)
            return


# ───────────────────────── owner buttons ─────────────────────────
def _original_html(q) -> str:
    """Current message text as HTML so edit_text keeps the formatting."""
    try:
        return q.message.text.html
    except Exception:
        return escape(q.message.text or "")


async def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".heal_tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


@app.on_callback_query(__import__("pyrogram").filters.regex(r"^avheal:(view|approve|reject):"))
async def healing_callback(_, q):
    if q.from_user.id != config.OWNER_ID:
        return await q.answer("Owner only.", show_alert=True)
    action, issue_id = q.data.split(":", 2)[1:]
    issue = await get_healing_issue(issue_id)
    if not issue:
        return await q.answer("Issue not found.", show_alert=True)

    if action == "reject":
        await mark_healing_issue(issue_id, "rejected")
        return await q.message.edit_text(_original_html(q) + "\n\n❌ <b>Rejected — repository unchanged.</b>")

    if action == "view":
        target = (ROOT / issue["file"]).resolve()
        old = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
        diff = "".join(difflib.unified_diff(
            old.splitlines(True), issue["new_content"].splitlines(True),
            fromfile=issue["file"], tofile=issue["file"] + " (proposed)", n=4,
        ))
        await q.answer()
        if not diff:
            return await q.message.reply_text("No textual difference detected.")
        if len(diff) <= 3500:
            return await q.message.reply_text(f"<pre>{escape(diff)}</pre>")
        bio = io.BytesIO(diff.encode("utf-8"))
        bio.name = f"{issue_id}.diff"
        return await q.message.reply_document(bio, caption="Proposed diff (too long for a message).")

    # ── approve ──
    if issue.get("status") != "pending":
        return await q.answer(f"Already {issue.get('status')}.", show_alert=True)
    target = (ROOT / issue["file"]).resolve()
    try:
        target.relative_to(ROOT)
    except ValueError:
        return await q.answer("Unsafe target.", show_alert=True)
    if not target.exists():
        return await q.answer("Target file no longer exists.", show_alert=True)

    current = target.read_text(encoding="utf-8", errors="replace")
    new_content = issue["new_content"]
    if hashlib.sha256(current.encode("utf-8", "replace")).hexdigest() != issue.get("base_sha256"):
        # The file changed after the proposal: re-apply the small edits to the current version and re-check.
        redone, why = _apply_edits(current, issue.get("edits"))
        ok, why2, _ = _validate(issue["file"], current, redone, int(issue.get("line", 1))) if redone else (False, why, 0)
        if not ok:
            await mark_healing_issue(issue_id, "stale")
            return await q.message.edit_text(
                _original_html(q) + f"\n\n⚠️ <b>Not applied — the file changed since this proposal.</b>\n<code>{escape(why2 or why)[:300]}</code>"
            )
        new_content = redone

    backup = HEAL_DIR / f"{issue_id}_{target.name}.bak"
    shutil.copy2(target, backup)
    try:
        await _atomic_write(target, new_content)
        if target.suffix == ".py":
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "py_compile", str(target),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, err = await proc.communicate()
            if proc.returncode:
                raise RuntimeError(err.decode(errors="replace")[:1500] or "py_compile failed")
    except Exception as exc:
        try:
            shutil.copy2(backup, target)
        except Exception:
            pass
        await mark_healing_issue(issue_id, "rolled_back")
        return await q.message.edit_text(
            _original_html(q) + f"\n\n❌ <b>Test failed — automatically rolled back.</b>\n<code>{escape(str(exc))[:1500]}</code>"
        )

    await mark_healing_issue(issue_id, "approved_applied")
    await q.message.edit_text(
        _original_html(q)
        + f"\n\n✅ <b>Approved & applied.</b>\nBackup: <code>{escape(str(backup.relative_to(ROOT)))}</code>"
        "\n\nRestart the bot when ready to load the changed module."
    )
