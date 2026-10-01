FROM node:22-bookworm-slim AS bgutil

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch 2.0.0 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil-ytdlp-pot-provider
WORKDIR /opt/bgutil-ytdlp-pot-provider/server
RUN npm install --ignore-scripts && npx tsc

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg ca-certificates curl unzip git gcc g++ make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .
COPY --from=bgutil /opt/bgutil-ytdlp-pot-provider /opt/bgutil-ytdlp-pot-provider
COPY --from=bgutil /usr/local/bin/node /usr/local/bin/node
COPY --from=bgutil /usr/local/lib/node_modules /usr/local/lib/node_modules

RUN test -f /app/config.py || (echo "ERROR: config.py missing from repository root" && exit 1)

RUN test -f /app/requirements.txt \
    && python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt

RUN python -c 'import yt_dlp; print("generic media extractor module OK")' \
    && python -c 'import yt_dlp_ejs; print("yt-dlp-ejs (JS challenge solver scripts) OK")' \
    && node --version \
    && node -e "process.exit(Number(process.versions.node.split('.')[0]) >= 22 ? 0 : 1)" \
    && python -c "import importlib.metadata as m; print('bgutil-ytdlp-pot-provider=' + m.version('bgutil-ytdlp-pot-provider'))" \
    && test -f /opt/bgutil-ytdlp-pot-provider/server/build/main.js \
    && test -f /opt/bgutil-ytdlp-pot-provider/server/build/generate_once.js

RUN python -m compileall -q AquaVibe strings config.py \
    && python -c "import importlib.metadata as m; import pyrogram; import ntgcalls; import pytgcalls; assert m.version('py-tgcalls') == '2.3.3', m.version('py-tgcalls'); assert m.version('ntgcalls') == '2.2.5', m.version('ntgcalls'); print('Telegram voice stack import OK: PyTgCalls=' + m.version('py-tgcalls') + ' NtCalls=' + m.version('ntgcalls') + ' Pyrofork=' + m.version('pyrofork'))" \
    && python -m pip show py-tgcalls ntgcalls pyrofork \
    && echo "Full Python compile OK"


RUN find . -type d -name __pycache__ -prune -exec rm -rf {} + \
    && find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete \
    && mkdir -p downloads cache couples AquaVibeBackup

CMD ["bash", "start"]
