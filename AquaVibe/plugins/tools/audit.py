"""Owner-only repository/runtime diagnostics."""
from pyrogram import filters
from pyrogram.types import Message

from config import OWNER_ID, LOGGER_ID
from AquaVibe.core.runtime import app
from AquaVibe.utils.repo_audit import audit_repo, write_report
from AquaVibe.utils.errors import _ERROR_COUNTS


@app.on_message(filters.command(["audit", "repoaudit", "errorscan"]) & filters.user(OWNER_ID))
async def repository_audit(_, message: Message):
    report = audit_repo()
    path = write_report(report)
    s = report["summary"]
    text = (
        "🧪 <b>AquaVibe Diagnostic Scan</b>\n\n"
        f"📦 Python files: <code>{s['python_files']}</code>\n"
        f"🔴 High: <code>{s['high']}</code>\n"
        f"🟠 Errors: <code>{s['errors']}</code>\n"
        f"🟡 Warnings: <code>{s['warnings']}</code>\n"
        f"🔵 Info: <code>{s['info']}</code>\n\n"
        "<b>What this checks</b>\n"
        "• syntax/compile failures\n"
        "• missing declared dependencies\n"
        "• swallowed/bare exceptions\n"
        "• shell/dynamic execution\n"
        "• possible hard-coded secrets\n"
        "• duplicate command registrations\n"
        "• TODO/FIXME hotspots\n\n"
        "📄 Full report is attached below.\n"
        "Runtime exceptions are separately captured with traceback + diagnosis + recommended fix."
    )
    await message.reply_text(text)
    await message.reply_document(str(path), caption="AquaVibe repository audit report")


@app.on_message(filters.command(["runtimeerrors", "recenterrors"]) & filters.user(OWNER_ID))
async def runtime_errors(_, message: Message):
    if not _ERROR_COUNTS:
        return await message.reply_text("✅ No runtime error fingerprints recorded in this process yet.")
    rows = sorted(_ERROR_COUNTS.items(), key=lambda x: x[1].get("last", 0), reverse=True)[:20]
    lines = ["🚨 <b>Recent runtime error fingerprints</b>", ""]
    for fp, state in rows:
        lines.append(f"• <code>{fp}</code> — occurrences: <code>{state.get('count', 0)}</code>")
    await message.reply_text("\n".join(lines))
