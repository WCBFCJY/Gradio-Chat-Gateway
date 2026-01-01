FROM python:3.10-slim

ARG TARGETARCH

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --no-warn-script-location -r requirements.txt

RUN pip install --no-cache-dir --no-warn-script-location uvloop

COPY gradio-chat-gateway.py .

COPY models.json .

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["python", "-u", "gradio-chat-gateway.py"]
