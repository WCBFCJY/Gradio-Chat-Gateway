FROM python:3.10-slim as builder

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --prefix=/install --no-cache-dir --no-warn-script-location -r requirements.txt

FROM python:3.10-slim

ARG TARGETARCH

WORKDIR /app

COPY --from=builder /install /usr/local

COPY gradio-chat-gateway.py .

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["python", "-u", "gradio-chat-gateway.py"]
