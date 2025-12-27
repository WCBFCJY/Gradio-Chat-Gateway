import os
import re
import time
import uuid
import json
import anyio
from functools import partial
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from gradio_client import Client

app = FastAPI()
security = HTTPBearer()

# --- 配置文件 ---

# 监听配置
LISTEN = os.getenv("LISTEN", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# 使用HTTP(s)/Socks5代理
USE_PROXY = os.getenv("USE_PROXY", "False")
PROXY_URL = os.getenv("PROXY_URL", "socks5://user:pass@ip:port")

# 模型高级配置
# 下方预置的模型均测试过，可以正常使用，无需调整。

MODEL_CONFIG = {
    "gpt-oss-20b": {"space": "merterbak/gpt-oss-20b-demo", "flags": "11"},
    "gpt-oss-20b-safe": {"space": "openai/gpt-oss-safeguard-20b", "flags": "52", "api_name": "/generate"},
    "gemma-3-12b": {"space": "huggingface-projects/gemma-3-12b-it", "flags": "22"},
    "gemma-2-9b": {"space": "huggingface-projects/gemma-2-9b-it", "flags": "41"},
    "gemma-2-2b": {"space": "huggingface-projects/gemma-2-2b-it", "flags": "41"},
    "qwen2.5-3b": {"space": "Kingoteam/Qwen2.5-vl-3B-demo", "flags": "30"},
    "gemma-3-270m": {"space": "daniel-dona/gemma-3-270m", "flags": "00"}
}




# --- 核心逻辑 ---

if USE_PROXY:
    os.environ["HTTP_PROXY"] = PROXY_URL
    os.environ["HTTPS_PROXY"] = PROXY_URL
    os.environ["ALL_PROXY"] = PROXY_URL
  # os.environ["verify"] = "False"  # 忽略证书验证

clients_cache: Dict[tuple, Client] = {}

def get_hf_token(auth: HTTPAuthorizationCredentials = Security(security)):
    """直接从 Authorization Header 获取 Token"""
    if not auth.credentials:
        raise HTTPException(status_code=401, detail="Missing Hugging Face Token in Authorization header")
    return auth.credentials

def parse_reasoning(text: str):
    """
    解析 Gradio 返回的字符串
    提取 <details> 中的思维链 和 剩余的正文
    """
    reasoning = ""
    content = text
    
    # 使用正则匹配 <details>...</details> 之后的所有内容
    pattern = r"<details.*?>(.*?)</details>(.*)"
    match = re.search(pattern, text, re.DOTALL)
    
    if match:
        # 提取思维链内容（去掉 <summary> 部分）
        raw_reasoning = match.group(1)
        reasoning = re.sub(r"<summary>.*?</summary>", "", raw_reasoning, flags=re.DOTALL).strip()
        # 提取正文内容
        content = match.group(2).strip()
        
    return reasoning, content

def get_gradio_client(model_id: str, hf_token: str) -> Client:
    if model_id not in MODEL_CONFIG:
        raise HTTPException(status_code=400, detail=f"Model '{model_id}' not found.")
    
    space_id = MODEL_CONFIG[model_id]["space"]
    cache_key = (model_id, hf_token)
    if cache_key not in clients_cache:
        try:
            clients_cache[cache_key] = Client(
                space_id, 
                token=hf_token
            )
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Failed to connect to HF with provided token: {str(e)}")
    return clients_cache[cache_key]

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    max_tokens: Optional[int] = 2000
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    top_k: Optional[int] = 50
    repetition_penalty: Optional[float] = 1.0
    stream: Optional[bool] = False
    reasoning_effort: Optional[str] = "low"

async def simulate_streaming(full_text: str, model_name: str, reasoning: str):
    chat_id = f"chatcmpl-{uuid.uuid4()}"
    created_time = int(time.time())
    
    # 1. 解析思维链和正文
    if reasoning is not None:
        content = full_text
    else:
        reasoning, content = parse_reasoning(full_text)

    # 2. 发送思维链部分 (使用 reasoning_content 字段)
    if reasoning:
        yield f"data: {json.dumps({'id': chat_id, 'object': 'chat.completion.chunk', 'created': created_time, 'model': model_name, 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'reasoning_content': reasoning}, 'finish_reason': None}]}, ensure_ascii=False)}\n\n"

    # 3. 发送正文部分
    yield f"data: {json.dumps({'id': chat_id, 'object': 'chat.completion.chunk', 'created': created_time, 'model': model_name, 'choices': [{'index': 0, 'delta': {'content': content}, 'finish_reason': None}]}, ensure_ascii=False)}\n\n"

    # 4. 发送结束标志
    yield f"data: {json.dumps({'id': chat_id, 'object': 'chat.completion.chunk', 'created': created_time, 'model': model_name, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"

# --- API接口 ---
@app.get("/v1/models")
async def list_models():
    """模型列表接口（不需要 Token 即可查看支持列表）"""
    return {
        "object": "list",
        "data": [{"id": m_id, "object": "model", "created": int(time.time())} for m_id in MODEL_CONFIG.keys()]
    }

@app.post("/v1/chat/completions")
async def create_chat_completion(
    request: ChatCompletionRequest, 
    hf_token: str = Depends(get_hf_token) # 这里注入权限检查
):

    system_prompt = "You are a helpful assistant."
    user_input = ""
    for msg in request.messages:
        if msg.role == "system":
            system_prompt = msg.content
        elif msg.role == "user":
            user_input = msg.content

    # 3. 处理 reasoning_effort 并拼接至 system_prompt
    if request.reasoning_effort:
        # 确保拼接格式自然，如果原 prompt 结尾没句号则补一个
        if not system_prompt.rstrip().endswith(('.', '!', '?')):
            system_prompt = system_prompt.strip() + "."
        system_prompt += f" Reasoning: {request.reasoning_effort}"

    async def do_predict(token: Optional[str]):
        client = get_gradio_client(request.model, token)
        config = MODEL_CONFIG[request.model]
        flags = config.get("flags", "00")
        
        # 构建基础参数
        target_api = config.get("api_name", "/chat")
        payload = {"api_name": target_api}
        
        # 第一位标识：输入模式
        if flags[0] == "1":
            payload["input_data"] = user_input
            payload["system_prompt"] = system_prompt
        elif flags[0] == "2":
            payload["message"] = {
                "text": f"{user_input}", 
                "files": [] 
            }
            payload["system_prompt"] = system_prompt
        elif flags[0] == "3":
            payload["message"] = {
                "text": f"{system_prompt}\n{user_input}", 
                "files": [] 
            }
        elif flags[0] == "4":
            payload["message"] = f"{system_prompt}\n{user_input}"
        elif flags[0] == "5":
            payload["prompt"] = user_input
            payload["policy"] = system_prompt
        else:
            payload["message"] = user_input
            payload["system_message"] = system_prompt
            
        # 第二位标识：额外参数
        if flags[1] == "1":
            payload.update({
                "max_new_tokens": request.max_tokens,
                "temperature": request.temperature,
                "top_p": request.top_p,
                "top_k": request.top_k,
                "repetition_penalty": request.repetition_penalty,
            })
        elif flags[1] == "2":
            payload["max_new_tokens"] = request.max_tokens
        
        # 使用关键字参数调用
        return await anyio.to_thread.run_sync(partial(client.predict, **payload))


    # 3. 核心调用逻辑：带 Token 尝试 -> 失败则匿名尝试
    try:
        try:
            full_response = await do_predict(hf_token)
        except Exception as e:
            error_msg = str(e).lower()
            # 如果提供了 Token 且报错包含 401(无效)、429(超限) 或 token 相关关键字
            if hf_token and any(x in error_msg for x in ["401", "429", "token", "limit", "quota"]):
                #print(f"Token error detected, falling back to anonymous: {e}")
                print("Error detected, Retrying...")
                full_response = await do_predict(None)
            else:
                raise e
        
        reasoning = None
        
        if isinstance(full_response, (tuple, list)):
            reasoning, *rest = full_response
            reasoning = str(reasoning)
            full_response = str(rest[0]) if rest else str(full_response)
        
        # 4. 返回响应
        if request.stream:
            return StreamingResponse(simulate_streaming(full_response, request.model, reasoning), media_type="text/event-stream")
        else:
            if reasoning is not None:
                content = full_response
            else:
                reasoning, content = parse_reasoning(full_response)
            
            message_obj = {"role": "assistant", "content": content}
            
            # 只有当模型确实输出了思维链时才包含该字段
            if reasoning:
                message_obj["reasoning_content"] = reasoning
                
            return {
                "id": f"chatcmpl-{uuid.uuid4()}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.model,
                "choices": [{
                    "index": 0,
                    "message": message_obj,
                    "finish_reason": "stop"
                }]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=LISTEN, port=PORT)
