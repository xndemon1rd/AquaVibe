#!/usr/bin/env python3
"""AquaVibe static build preflight; no network or secrets required."""
from __future__ import annotations
import ast, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent
PKG = ROOT / "AquaVibe"
errors: list[str] = []

if not PKG.is_dir():
    errors.append("AquaVibe package is missing")
if not (ROOT / "config.py").is_file():
    errors.append("root config.py is missing")
if not (ROOT / "strings" / "__init__.py").is_file():
    errors.append("root strings package is missing")
if not (ROOT / "requirements.txt").is_file():
    errors.append("requirements.txt is missing")
if not (ROOT / "Dockerfile").is_file():
    errors.append("Dockerfile is missing")

for path in ROOT.rglob("*.py"):
    if "__pycache__" in path.parts:
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        errors.append(f"syntax error: {path}: {exc}")

# Provider systems intentionally excluded from this build.
for path in PKG.rglob("*.py"):
    text = path.read_text(encoding="utf-8", errors="ignore")
    if re.search(r'\b(?:jiosaavn|jio\s+saavn)\b', text, re.I):
        errors.append(f"JioSaavn reference in {path}")
    if re.search(r'\b(?:ress[o0]|internetarchive|archive\.org|freetouse)\b', text, re.I):
        errors.append(f"Removed provider reference in {path}")


# The active alternative-provider backend must remain present.
if not (PKG / "platforms" / "AlternativeMedia.py").is_file():
    errors.append("AlternativeMedia provider is missing")

req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
for bad in ("youtube-search-python", "kurigram"):
    if re.search(rf"^{re.escape(bad)}\b", req, re.M | re.I):
        errors.append(f"obsolete dependency remains: {bad}")
if not re.search(r"^py-tgcalls==2\.3\.3\s*$", req, re.M):
    errors.append("py-tgcalls==2.3.3 missing")
if not re.search(r"^ntgcalls==2\.2\.5\s*$", req, re.M):
    errors.append("ntgcalls==2.2.5 missing")
if re.search(r"^TgCrypto\s*$", req, re.M | re.I):
    errors.append("TgCrypto should not be required for this build")

if errors:
    print("AQUAVIBE PREFLIGHT: FAILED")
    for e in errors: print(" -", e)
    raise SystemExit(1)

print("AQUAVIBE PREFLIGHT: PASS")
