# Build context is final-devops-project/application.
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    NOTES_DATA_PATH=/data/notes.json
WORKDIR /srv
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels \
    && useradd --system --uid 10001 --create-home appuser \
    && install -d -o 10001 -g 10001 /data
# The templates live inside the package, which is where Flask looks for them:
# the app is created as Flask(__name__) from notes/app.py, so its root path is
# the notes package, not the working directory.
COPY notes ./notes
USER 10001
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"
# Two workers is enough for a demo and keeps the memory request honest.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "notes.app:app"]
