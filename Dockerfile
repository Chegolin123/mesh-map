FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    MESHMAP_PROVIDER=mock \
    MESHMAP_DB=/data/meshmap.db

WORKDIR /app

COPY pyproject.toml README.md ./
COPY meshmap ./meshmap
RUN pip install --no-cache-dir .

RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8765

CMD ["uvicorn", "meshmap.web:create_app", "--factory", "--host", "0.0.0.0", "--port", "8765"]
