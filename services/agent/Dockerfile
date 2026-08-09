FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update     && apt-get install -y --no-install-recommends ffmpeg curl     && rm -rf /var/lib/apt/lists/*

COPY services/agent/requirements.txt /tmp/agent-requirements.txt
COPY services/espresso_mcp/requirements.txt /tmp/espresso-mcp-requirements.txt
RUN pip install --upgrade pip     && pip install -r /tmp/agent-requirements.txt     && pip install -r /tmp/espresso-mcp-requirements.txt     && addgroup --gid 10001 app     && adduser --uid 10001 --gid 10001 --disabled-password --gecos "" --no-create-home app

COPY services ./services
COPY modeling ./modeling
COPY data/labels ./data/labels

RUN mkdir -p data/uploads data/frames     && chown -R app:app /app

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3     CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "services.agent.app:app", "--host", "0.0.0.0", "--port", "8000"]
