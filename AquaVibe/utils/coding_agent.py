"""Safe repo coding agent for AquaVibe VIP/VIP Pro.

The agent is intentionally workspace-scoped: it can inspect/edit only the job
workspace and never receives host/VPS shell access. The model returns a strict
JSON edit plan; changes are applied to a disposable copy and compiled before
being zipped.
"""
from __future__ import annotations
import asyncio, json, os, re, shutil, tempfile, zipfile
from pathlib import Path
from typing import Any

import config
from AquaVibe.utils.ai import ask

ROOT = Path(__file__).resolve().parents[2]
WORK_ROOT = ROOT / config.CODING_WORKSPACE_DIR
WORK_ROOT.mkdir(parents=True, exist_ok=True)
_QUEUE = None
_WORKERS = []
_QUEUE_LOCK = asyncio.Lock()

_SECRET = re.compile(r"(?i)(bot[_ -]?token|api[_ -]?(?:key|hash)|password|secret|bearer|mongo(?:db)?(?:\+srv)?://)[^\s\n]+")


def _safe_path(root: Path, rel: str) -> Path:
    rel = str(rel or "").replace("\\", "/").lstrip("/")
    if not rel or rel.startswith("../") or "/../" in rel or rel in {".", ".."}:
        raise ValueError(f"Unsafe path: {rel!r}")
    out = (root / rel).resolve()
    if root.resolve() not in out.parents:
        raise ValueError("Path escapes workspace")
    return out


def _redact(s: str) -> str:
    return _SECRET.sub("[REDACTED]", s)


def _inventory(root: Path) -> str:
    rows=[]
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(x in p.parts for x in {".git","__pycache__","node_modules","venv",".venv"}):
            continue
        rel=p.relative_to(root).as_posix()
        try: size=p.stat().st_size
        except OSError: size=0
        rows.append(f"{rel}\t{size} bytes")
        if len(rows) >= config.CODING_MAX_FILES: break
    return "\n".join(rows)


def _read_text_files(root: Path, limit_chars: int) -> str:
    chunks=[]; total=0
    allowed={".py",".txt",".md",".toml",".yaml",".yml",".json",".js",".ts",".tsx",".jsx",".ini",".cfg",".env.example",".dockerfile",".sh"}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.stat().st_size > config.CODING_MAX_FILE_MB*1024*1024:
            continue
        if any(x in p.parts for x in {".git","__pycache__","node_modules","venv",".venv"}): continue
        if p.suffix.lower() not in allowed and p.name not in {"Dockerfile","requirements.txt"}: continue
        try: text=p.read_text(encoding="utf-8",errors="replace")
        except Exception: continue
        piece=f"\n===== {p.relative_to(root).as_posix()} =====\n{_redact(text)}\n"
        if total+len(piece)>limit_chars: break
        chunks.append(piece); total += len(piece)
    return "".join(chunks)


def _extract_json(text: str) -> dict:
    text=text.strip()
    if text.startswith("```"):
        text=re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text=re.sub(r"\s*```$", "", text)
    start=text.find("{"); end=text.rfind("}")
    if start<0 or end<=start: raise ValueError("AI did not return a JSON edit plan")
    return json.loads(text[start:end+1])


def _validate_plan(plan: dict):
    if not isinstance(plan,dict): raise ValueError("Invalid edit plan")
    ops=plan.get("operations",[])
    if not isinstance(ops,list) or len(ops)>config.CODING_MAX_FILES: raise ValueError("Too many file operations")
    for op in ops:
        if op.get("action") not in {"write","delete","mkdir"}: raise ValueError("Unsupported file action")
        _safe_path(Path("/tmp"), op.get("path","x"))
        if op.get("action")=="write" and len(str(op.get("content",""))) > config.CODING_MAX_FILE_MB*1024*1024:
            raise ValueError("Generated file is too large")


async def _model(prompt: str) -> str:
    # The normal Aqua provider chain is used by default. A legitimate
    # user-authenticated Puter bridge can be selected for Claude-class models.
    if config.PUTER_CODING_ENDPOINT:
        import httpx
        async with httpx.AsyncClient(timeout=config.CODING_JOB_TIMEOUT) as client:
            r=await client.post(config.PUTER_CODING_ENDPOINT, json={"prompt":prompt})
            r.raise_for_status()
            data=r.json()
            return str(data.get("text") or data.get("content") or data.get("response") or "")
    return await ask(prompt)


async def _ensure_queue():
    global _QUEUE, _WORKERS
    async with _QUEUE_LOCK:
        if _QUEUE is None:
            import heapq
            class _PriorityQueue:
                def __init__(self): self.items=[]; self.counter=0; self.event=asyncio.Event()
                async def put(self, priority, coro):
                    self.counter += 1; fut=asyncio.get_running_loop().create_future()
                    heapq.heappush(self.items,(priority,self.counter,coro,fut)); self.event.set(); return fut
                async def get(self):
                    while not self.items: self.event.clear(); await self.event.wait()
                    return heapq.heappop(self.items)
            _QUEUE=_PriorityQueue()
            for _ in range(max(1,int(config.CODING_MAX_CONCURRENT))):
                _WORKERS.append(asyncio.create_task(_queue_worker()))
    return _QUEUE

async def _queue_worker():
    while True:
        item=await _QUEUE.get()
        _,_,coro,fut=item
        try: fut.set_result(await coro)
        except Exception as exc:
            if not fut.done(): fut.set_exception(exc)

async def submit_job(prompt: str, zip_path: str | None, *, job_id: str, priority: int = 10):
    queue=await _ensure_queue()
    fut=await queue.put(priority, build_or_edit(prompt, zip_path, job_id=job_id))
    return await fut

async def build_or_edit(prompt: str, zip_path: str | None = None, *, job_id: str) -> tuple[str, str]:
    if not config.CODING_AGENT_ENABLED: raise RuntimeError("Coding agent is disabled")
    root=WORK_ROOT / job_id
    if root.exists(): shutil.rmtree(root)
    root.mkdir(parents=True)
    if zip_path:
        with zipfile.ZipFile(zip_path) as z:
            members=z.infolist()
            if len(members)>config.CODING_MAX_FILES: raise ValueError("Repository has too many files")
            for m in members:
                target=_safe_path(root,m.filename)
                if m.is_dir(): target.mkdir(parents=True,exist_ok=True); continue
                if m.file_size > config.CODING_MAX_FILE_MB*1024*1024: raise ValueError(f"File too large: {m.filename}")
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(m) as src, target.open("wb") as dst: shutil.copyfileobj(src,dst)
    inventory=_inventory(root)
    context=_read_text_files(root, config.CODING_AI_MAX_INPUT)
    prompt_text=f'''You are the coding agent for AquaVibe. Work only on the repository described below.\n\nUSER TASK:\n{prompt[:12000]}\n\nFILE INVENTORY:\n{inventory}\n\nRELEVANT FILE CONTENT:\n{context}\n\nReturn ONLY JSON with this shape:\n{{"summary":"...","operations":[{{"action":"write|delete|mkdir","path":"relative/path","content":"full file content for write"}}],"tests":["python -m compileall AquaVibe"]}}\nRules: preserve unrelated functionality; never write secrets; use relative paths; for edits return complete file contents; make the smallest safe change; include dependency/docs changes when required.'''
    result=await asyncio.wait_for(_model(prompt_text), timeout=config.CODING_JOB_TIMEOUT)
    plan=_extract_json(result); _validate_plan(plan)
    for op in plan.get("operations",[]):
        target=_safe_path(root,op["path"]); action=op["action"]
        if action=="mkdir": target.mkdir(parents=True,exist_ok=True)
        elif action=="delete": target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True,exist_ok=True); target.write_text(str(op.get("content","")),encoding="utf-8")
    # Basic syntax validation for Python repos.
    proc=await asyncio.create_subprocess_exec("python","-m","compileall","-q",".",cwd=str(root),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    out,err=await asyncio.wait_for(proc.communicate(),timeout=min(config.CODING_JOB_TIMEOUT,180))
    if proc.returncode:
        raise RuntimeError("Python compile check failed: "+_redact(err.decode(errors="replace"))[:2500])
    out_zip=WORK_ROOT/f"{job_id}.zip"
    with zipfile.ZipFile(out_zip,"w",zipfile.ZIP_DEFLATED) as z:
        for p in root.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                z.write(p,p.relative_to(root).as_posix())
    return str(out_zip), str(plan.get("summary") or "Coding job completed")


def cleanup(job_id: str):
    shutil.rmtree(WORK_ROOT/job_id,ignore_errors=True)
    try: (WORK_ROOT/f"{job_id}.zip").unlink()
    except OSError: pass
