<div align="center">

# Gradio-Chat-Gateway

<p align="center">
  <strong>English</strong> | 
  <a href="./README_CN.md">中文</a>
</p>

</div>

## Project Overview

**Gradio-Chat-Gateway** is a gateway service that transforms open-source AI models deployed via Gradio API into OpenAI-compatible APIs. It allows users to interact with multiple Hugging Face Spaces models using the standard OpenAI Chat Completion format, greatly simplifying the model invocation process.

## Core Features

### 1. **OpenAI API Compatibility**
- Full support for `/v1/chat/completions` and `/v1/models` endpoints
- Compatible with OpenAI request/response formats
- Supports common OpenAI request parameters
- Supports pseudo-streaming and non-streaming responses

### 2. **Multi-Model Access**
Built-in models:
- `gpt-oss-20b` - OpenAI open-source model
- `gemma-3-12b` / `gemma-2-9b` / `gemma-2-2b` - Google Gemma series
- `qwen2.5-3b` - Alibaba Qwen series
- `llama-3.2-1b`

Also allows manual addition of new models

### 3. **Authentication Mechanism**
- Direct authentication: Uses the provided Token for model API authentication
- Smart fallback: Automatically switches to anonymous access when token is unavailable
- Auto-retry: Recognizes 401/429 status codes and retries

### 4. **Network Optimization**
- Built-in HTTP/HTTPS/SOCKS5 proxy support
- Client connection pool caching to avoid repeated initialization

## Deployment Guide

### 1. Install Dependencies
```bash
pip install fastapi uvicorn gradio_client pydantic anyio httpx[socks]
```

### 2. Run Service
```bash
python gradio-chat-gateway.py
```

### 3. Docker Compose (Recommended)
```
git clone https://github.com/WCBFCJY/Gradio-Chat-Gateway.git
cd Gradio-Chat-Gateway
nano docker-compose.yml
docker-compose up -d
```

## Environment Variables

| Variable Name  | 	Type    | 	Default Value                       | Description                                        |
| ----------- | ------- | ---------------------------- | ------------------------------------------- |
| `LISTEN`    | String  | `0.0.0.0`                    | 	The IP address the service listens on.                        |
| `PORT`      | Integer | `8000`                       | 	The port number the service listens on.                            |
| `USE_PROXY` | Boolean | `False`                      | 	Whether to enable proxy. Supported values: `True`/`False`      |
| `PROXY_URL` | String  | `socks5://user:pass@ip:port` | Proxy server URL. Supports HTTP(S) and SOCKS5 protocols. |

## API Documentation

### 1. Get Model List
```http
GET /v1/models
```

### 2. Chat Completion

```http
POST /v1/chat/completions
Authorization: Bearer <YOUR_HUGGINGFACE_TOKEN>
Content-Type: application/json
```

**Request Body:**

```json
{
  "model": "gemma-2-9b",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello"}
  ],
  "max_tokens": 2000,
  "temperature": 0.7,
  "top_p": 0.9,
  "top_k": 50,
  "repetition_penalty": 1.0,
  "stream": false,
  "reasoning_effort": "medium"
}
```

## Usage Examples

### Python Client
```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your_huggingface_token"
)

response = client.chat.completions.create(
    model="gemma-2-9b",
    messages=[
        {"role": "user", "content": "Hello"}
    ],
    stream=True
)

for chunk in response:
    print(chunk.choices[0].delta.content, end="")
```

### cURL
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer hf_xxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss-20b",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": false
  }'
```

## Common Error Codes

- `401` - Invalid or missing token (will automatically attempt anonymous access)
- `429` - ZERO GPU quota exceeded (free users: 5min/24h, anonymous users: 1min/24h)
- `400` - Model does not exist or invalid request parameters
- `500` - Model inference failure

## Important Notes

1. **Token Security**: Use environment variables to manage tokens in production
2. **Rate Limiting**: Hugging Face Spaces has request frequency limits
3. **Model Availability**: Some Spaces may be temporarily unavailable due to maintenance
4. **Flags Configuration**: Incorrect flags will cause request failures; refer to model documentation
5. **Proxy Performance**: Using proxies increases latency; optimize network paths in production
6. **Pseudo-Streaming Output**: Since upstream doesn't support streaming, pseudo-streaming output is used

## License

MIT License
