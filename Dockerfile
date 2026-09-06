FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY ishworkzero ./ishworkzero
RUN pip install --no-cache-dir . && useradd --create-home --uid 10001 ishworkzero
RUN mkdir -p /data && chown -R ishworkzero:ishworkzero /app /data
USER ishworkzero
ENV ISHWORKZERO_DB=/data/ishworkzero.db
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health',timeout=3)"
CMD ["uvicorn","ishworkzero.main:app","--host","0.0.0.0","--port","8000"]
