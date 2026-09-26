FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg ca-certificates curl unzip git gcc g++ make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN test -f /app/config.py || (echo "ERROR: config.py missing from repository root" && exit 1)

RUN test -f /app/requirements.txt \
    && python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt

RUN python -c 'import yt_dlp; print("generic media extractor module OK")'

RUN python -m compileall -q AquaVibe strings config.py \
    && python -c "import pyrogram; from pyrogram.errors import GroupcallForbidden; from pyrogram.types import LabeledPrice; from pytgcalls import PyTgCalls; print('Telegram voice stack import OK')" \
    && echo "Full Python compile OK"


RUN find . -type d -name __pycache__ -prune -exec rm -rf {} + \
    && find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete \
    && mkdir -p downloads cache couples AquaVibeBackup

CMD ["bash", "start"]
