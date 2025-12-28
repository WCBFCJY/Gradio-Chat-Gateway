<div align="center">

# Gradio-Chat-Gateway

<p align="center">
  <a href="./README_CN.md">中文</a> | 
  <strong>English</strong>
</p>

</div>

## 📖 Introduction

**Gradio-Chat-Gateway** is a lightweight, high-performance API gateway that supports multiple models and converts Gradio APIs into standard OpenAI-compatible APIs. It allows users to interact with various open-source LLMs hosted on Hugging Face Spaces (via Gradio API) using the standard `OpenAI Chat Completion` API format, significantly simplifying the model invocation process.

## ✨ Core Features

### 1. **OpenAI API Compatibility**
- Full support for `/v1/chat/completions` and `/v1/models` endpoints
- Compatible with OpenAI request/response formats
- Supports common OpenAI request parameters
- Supports Chain of Thought  parsing
- Supports streaming, simulated-streaming, and non-streaming responses

### 2. **Multi-Model Aggregation**
- Manage multiple API sources via the `models.json` configuration file, allowing one-click switching between models
- Provides a single-file HTML visual configuration editor `model-config-editor.html` for managing models
- Built-in `models.json` includes models `gpt-oss-20b / gemma-3-12b / gemma-2-9b / gemma-2-2b / qwen2.5-3b`

### 3. **Authentication Mechanism**
- Direct Authentication: Uses the provided Token for model API authentication
- Smart fallback: Automatically switches to anonymous access if the Token is unavailable
- Auto-Retry: Recognizes 401/429 status codes and retries

### 4. **Network Optimization**
- Built-in HTTP/HTTPS/SOCKS5 proxy support
- Client connection pool caching to avoid repeated initialization

## 🛠️ Quick Start

### 1. Install Dependencies
```bash
git clone https://github.com/WCBFCJY/Gradio-Chat-Gateway.git
cd Gradio-Chat-Gateway
pip install -r requirements.txt
```

### 2. Run Service
```bash
python gradio-chat-gateway.py
```

### 3. Docker
```bash
docker run -d \
  --name gradio-chat-gateway \
  -p 8000:8000 \
  -v ./models.json:/app/models.json \
  -e PORT=8000 \
  ghcr.io/wcbfcjy/gradio-chat-gateway:latest
```

### 4. Docker Compose (Recommended)
```bash
git clone https://github.com/WCBFCJY/Gradio-Chat-Gateway.git
cd Gradio-Chat-Gateway
nano docker-compose.yml
docker-compose up -d
```

## ⚙️ Environment Variables

| Variable Name | Type    | Default Value                | Description                                     |
| ------------- | ------- | ---------------------------- | ----------------------------------------------- |
| `LISTEN`      | String  | `0.0.0.0`                    | The IP address the service listens on           |
| `PORT`        | Integer | `8000`                       | The port number the service listens on          |
| `USE_PROXY`   | Boolean | `False`                      | Whether to enable proxy. Values: `True`/`False` |
| `PROXY_URL`   | String  | `socks5://user:pass@ip:port` | Proxy server URL. Supports HTTP(S) and SOCKS5   |

## 🧩 Model Management
This project provides a single-file HTML configuration editor: `model-config-editor.html`
Use `model-config-editor` to visually manage models without manually modifying the JSON file

1.  Open `model-config-editor.html` directly in your browser
2.  Click **Import** to load your existing `models.json`
3.  Configure your models in the graphical interface
4.  Click **Export** to save and overwrite the default `models.json`

**Different models support different parameters. Please use the configuration editor to carefully check against the model's API documentation.**

## 🔌 API Documentation

### 1. Get Model List
```http
GET /v1/models
```

### 2. Chat Completions

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

## 🖥️ Usage Examples

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

## 🔎 Common Error Codes

- `401` - Invalid or missing token (will automatically attempt anonymous access)
- `429` - ZERO GPU quota exceeded (Free users: 5min/24h, Anonymous: 1min/24h)
- `400` - Model does not exist or invalid request parameters
- `500` - Model inference failed

## ⚠️ Notes

1.  **Token Security**: Use environment variables to manage tokens in production
2.  **Rate Limits**: Hugging Face Spaces have request frequency limits
3.  **Model Availability**: Some Spaces may be temporarily unavailable due to maintenance or compatibility issues
4.  **Model Configuration**: Incorrect configuration will lead to request failures, please refer to the model documentation

## 📄 License

MIT License.
