FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    KIRIKU_MODELS_DIR=/models \
    HF_HOME=/models/hf

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl libsndfile1 build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.5.1 torchaudio==2.5.1
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY settings.py prepare.py engines.py server.py ./

EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60m --retries=3 \
    CMD curl -fsS http://127.0.0.1:9000/health || exit 1

CMD ["sh", "-c", "python prepare.py && exec uvicorn server:app --host 0.0.0.0 --port 9000"]
