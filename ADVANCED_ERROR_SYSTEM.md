# Advanced Error System

AquaVibe now has an always-on, centralized error system designed for production hosting.

## Enabled by default

- `ERROR_SYSTEM_ENABLED=true`
- `REMOTE_ERROR_REPORTING=true`
- Structured local JSONL events in `runtime_errors.jsonl`
- Telegram owner/logger alerts when `LOGGER_ID` is configured
- Global process, thread and asyncio exception hooks
- Command, callback and internal-handler decorators
- Stable error fingerprints for grouping repeated failures
- Duplicate suppression and alert-storm rate limiting
- Severity classification and built-in diagnosis/fix guidance
- Full sanitized traceback attachment for oversized reports
- Secret redaction before local structured storage or Telegram reporting

## Railway/hosting variables

Set these in the hosting provider:

```text
LOGGER_ID=<your private logger chat ID>
ERROR_SYSTEM_ENABLED=true
REMOTE_ERROR_REPORTING=true
ERROR_DEDUP_WINDOW_SEC=300
ERROR_MAX_PER_WINDOW=30
ERROR_LOG_FILE=runtime_errors.jsonl
ERROR_INCLUDE_TRACEBACK=true
ERROR_REDACT_SECRETS=true
```

`LOGGER_ID` is the destination for Telegram error alerts. If it is `0` or missing, errors are still captured locally and in the hosting logs, but no Telegram alert is sent.

## Safety behavior

The error system never attempts arbitrary source-code rewriting or AI-generated self-modification. It only records, diagnoses, groups and reports failures. Repeated identical exceptions are grouped to prevent Telegram alert spam.

## Repository-wide diagnostic scanner

The bot also includes an owner-only static scanner:

- `/audit`, `/repoaudit`, `/errorscan` — scans the repository and sends a full report.
- `/runtimeerrors`, `/recenterrors` — shows runtime error fingerprints captured during the current process.
- The scanner checks Python syntax/compile failures, undeclared dependencies, swallowed/bare exceptions, shell/dynamic execution, possible hard-coded secrets, duplicate command registrations, and TODO/FIXME hotspots.
- Every finding includes a file/line, problem description, and a concrete recommended fix.
- A scan also runs after the bot connects and writes `repo_audit_report.txt` and `repo_audit_report.json`. Startup is never blocked by an audit failure.

Runtime exceptions remain separate from static findings: the runtime system stores a fingerprint, severity, sanitized traceback, likely cause, recommended fix, and owner action. Repeated identical errors are deduplicated to prevent logger spam. This follows the normal Pyrogram pattern of preserving/logging the complete traceback instead of silently catching RPC errors.
