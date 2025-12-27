# Gradio-Chat-Gateway

## 项目简介

**Gradio-Chat-Gateway** 是一个将 Hugging Face Spaces 上基于 Gradio API 部署的开源 AI 模型转换为 OpenAI 兼容 API 的网关服务，允许用户使用标准的 OpenAI Chat Completion 格式与多个 Hugging Face Spaces 模型进行交互，极大简化了模型调用流程。

## 核心功能

### 1. **OpenAI API 兼容**
- 完整支持 `/v1/chat/completions` 和 `/v1/models` 接口
- 兼容 OpenAI 的请求/响应格式
- 兼容 OpenAI 请求常用的参数
- 支持伪流式（stream）和非流式响应

### 2. **多模型接入**
内置以下模型（开箱即用）：
- `gpt-oss-20b` - OpenAI开源模型
- `gemma-3-12b` / `gemma-2-9b` / `gemma-2-2b` / `gemma-3-270m` - Google Gemma 系列
- `qwen2.5-3b` - 阿里通义千问系列

同时允许手动添加新的模型

### 3. **认证机制**
- 直接认证：使用 Hugging Face Token 进行 Spaces 认证
- 智能降级：Token 不可用时自动切换到匿名访问
- 自动重试：识别 401/429 状态码并重试

### 4. **网络优化**
- 内置 HTTP/HTTPS/SOCKS5 代理支持
- 客户端连接池缓存，避免重复初始化

## 部署指南

### 1. 安装依赖
```bash
pip install fastapi uvicorn gradio_client pydantic anyio httpx[socks]
```

### 2. 运行服务
```bash
python Gradio-Chat-Gateway.py
```

### 3. Docker 部署（推荐）
```
git clone https://github.com/WCBFCJY/Gradio-Chat-Gateway.git
cd Gradio-Chat-Gateway
nano docker-compose.yml
docker-compose up -d
```

## 环境变量

| 变量名  | 类型    | 默认值                       | 说明                                        |
| ----------- | ------- | ---------------------------- | ------------------------------------------- |
| `LISTEN`    | String  | `0.0.0.0`                    | 服务监听的 IP 地址。                        |
| `PORT`      | Integer | `8000`                       | 服务监听的端口号                            |
| `USE_PROXY` | Boolean | `False`                      | 是否启用代理。支持的值：`True`/`False`      |
| `PROXY_URL` | String  | `socks5://user:pass@ip:port` | 代理服务器地址。支持 HTTP(S) 和 SOCKS5 |

## 手动添加模型

### 添加新模型

```python
MODEL_CONFIG = {
    "your-model-name": {
        "space": "username/space-name",  # Hugging Face Space ID
        "flags": "11"                     # 根据模型 API 文档配置
    }
}
```

**配置步骤：**

1. 在 Hugging Face Spaces 找到目标模型
2. 查看其 API 文档，确定输入格式和参数支持
3. 根据文档选择合适的 flags 组合
4. 测试验证

### Flags 配置

每个模型使用两位 `flags` 参数标识 API 调用特性：

**第一位（输入格式）：**
- `0`: `message` + `system_message` 分离
- `1`: `input_data` + `system_prompt`
- `2`: `message` 对象（含 text/files）+ `system_prompt`
- `3`: `message` 对象（拼接 system 和 user）
- `4`: `message` 字符串（拼接）

**第二位（参数支持）：**
- `0`: 不附加高级参数
- `1`: 完整参数（temperature, top_p, top_k, repetition_penalty）
- `2`: 仅 max_tokens

示例配置：
```python
"gemma-2-9b": {"space": "huggingface-projects/gemma-2-9b-it", "flags": "01"}
# flags="01" 表示：使用 message+system_message 格式 + 完整参数
```

## API 接口文档

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

## 使用示例

### Python 客户端
```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="hf_your_token"
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

## 常见错误码

- `401` - Token 无效或缺失（会自动尝试匿名访问）
- `429` - ZERO GPU配额超限（免费用户5min/24h，匿名用户1min/24h）
- `400` - 模型不存在或请求参数错误
- `500` - 模型推理失败

## 注意事项

1. **Token 安全**：生产环境建议使用环境变量管理 Token
2. **速率限制**：Hugging Face Spaces 有请求频率限制
3. **模型可用性**：部分 Space 可能因维护而暂时不可用
4. **Flags 配置**：错误的 flags 会导致请求失败，需参考模型文档
5. **代理性能**：使用代理会增加延迟，建议生产环境优化网络路径
5. **伪流式输出**：上游不支持流式输出，故采用伪流式输出

## 许可证

本项目遵循 MIT 许可证


---
