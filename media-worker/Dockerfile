FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=7860
WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY worker.py main.py ./

RUN useradd --create-home --uid 1000 user \
    && chown -R user:user /app
USER user
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:7860/health', timeout=3); assert r.status == 200"
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT} --no-access-log"]
