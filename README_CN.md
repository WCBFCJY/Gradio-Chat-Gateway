<div align="center">

# Gradio-Chat-Gateway

<p align="center">
  <strong>中文</strong> | 
  <a href="./README.md">English</a>
</p>

</div>

## 项目简介

**Gradio-Chat-Gateway** 是一个轻量的高性能 API 网关，支持多种模型，能够将 Gradio API 转换为标准的 OpenAI 兼容 API 。允许用户使用标准的 `OpenAI Chat Completion` 格式与 Hugging Face Spaces 上基于 Gradio API 托管的各类 LLM 开源模型进行交互，极大简化了模型调用流程。

## ✨ 核心功能

### 1. **OpenAI API 兼容**
- 完整支持 `/v1/chat/completions` 和 `/v1/models` 接口
- 兼容 OpenAI 的请求/响应格式
- 兼容 OpenAI 请求常用的参数
- 支持思维链解析(CoT)
- 支持流式（stream）、伪流式和非流式响应

### 2. **多模型聚合**
通过 `models.json` 配置文件管理多个 API 来源，支持一键切换不同模型
提供单HTML可视化配置编辑器 `model-config-editor.html`，用于管理模型
内置的 `models.json` 适配以下模型（开箱即用）：

- `gpt-oss-20b` - OpenAI开源模型
- `gemma-3-12b` / `gemma-2-9b` / `gemma-2-2b` - Google Gemma 系列
- `qwen2.5-3b` - 阿里通义千问系列

### 3. **认证机制**
- 直接认证：使用传入的 Token 进行模型 API 认证
- 智能降级：Token 不可用时自动切换到匿名访问
- 自动重试：识别 401/429 状态码并重试

### 4. **网络优化**
- 内置 HTTP/HTTPS/SOCKS5 代理支持
- 客户端连接池缓存，避免重复初始化

## 🛠️ 快速开始

### 1. 安装依赖
```bash
git clone https://github.com/WCBFCJY/Gradio-Chat-Gateway.git
cd Gradio-Chat-Gateway
pip install -r requirements.txt
```

### 2. 运行服务
```bash
python gradio-chat-gateway.py
```

### 3. Docker 部署
```
docker run -d \
  --name gradio-chat-gateway \
  -p 8000:8000 \
  -v ./models.json:/app/models.json \
  -e PORT=8000 \
  ghcr.io/wcbfcjy/gradio-chat-gateway:latest
```

### 4. Docker Compose（推荐）
```
git clone https://github.com/WCBFCJY/Gradio-Chat-Gateway.git
cd Gradio-Chat-Gateway
nano docker-compose.yml
docker-compose up -d
```

## ⚙️ 支持的环境变量

| 变量名  | 类型    | 默认值                       | 说明                                        |
| ----------- | ------- | ---------------------------- | ------------------------------------------- |
| `LISTEN`    | String  | `0.0.0.0`                    | 服务监听的 IP 地址。                        |
| `PORT`      | Integer | `8000`                       | 服务监听的端口号                            |
| `USE_PROXY` | Boolean | `False`                      | 是否启用代理。支持的值：`True`/`False`      |
| `PROXY_URL` | String  | `socks5://user:pass@ip:port` | 代理服务器地址。支持 HTTP(S) 和 SOCKS5 |

## 🧩 模型管理
本项目提供HTML单文件配置编辑器 `model-config-editor.html`
使用 `model-config-editor` 可视化管理模型，无需手动修改 JSON

1.  在浏览器中直接打开 `model-config-editor.html`
2.  点击 Import 导入现有的 `models.json`
3.  在图形界面中配置模型。
4.  点击 Export 导出并覆盖默认的 `models.json`

**不同的模型支持的参数不同，请使用配置编辑器仔细对照模型的 API 文档进行配置**

## 🔌 API 接口文档

### 1. 获取模型列表
```http
GET /v1/models
```

### 2. 聊天补全

```http
POST /v1/chat/completions
Authorization: Bearer <YOUR_HUGGINGFACE_TOKEN>
Content-Type: application/json
```

**请求体：**

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

## 🖥️ 使用示例

### Python 客户端
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

## ⚠️ 常见错误码

- `401` - Token 无效或缺失（会自动尝试匿名访问）
- `429` - ZERO GPU 配额超限（免费用户5min/24h，匿名用户1min/24h）
- `400` - 模型不存在或请求参数错误
- `500` - 模型推理失败

## 🔎 注意事项

1. **Token 安全**：生产环境建议使用环境变量管理 Token
2. **速率限制**：Hugging Face Spaces 有请求频率限制
3. **模型可用性**：部分 Space 可能因维护或者兼容性问题而暂时不可用
4. **模型配置**：错误的配置会导致请求失败，需参考模型文档

## 📄 许可证

本项目遵循 MIT 许可证


---




