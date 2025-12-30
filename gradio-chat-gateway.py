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
from gradio_client.client import Job

app = FastAPI()
security = HTTPBearer()

# --- 配置文件 ---

CONFIG_FILE = "models.json"

def load_model_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"CRITICAL ERROR: Configuration file '{CONFIG_FILE}' not found.")
        exit(1)
        
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            
        if not config:
            raise ValueError("Configuration is empty.")
            
        print(f"INFO:     Loaded configuration for {len(config)} models.")
        return config
        
    except json.JSONDecodeError as e:
        print(f"CRITICAL ERROR: Failed to parse '{CONFIG_FILE}'. Invalid JSON format.\nError: {e}")
        exit(1)
    except Exception as e:
        print(f"CRITICAL ERROR: An unexpected error occurred while loading config.\nError: {e}")
        exit(1)

# 初始化配置 (失败即退出)
MODEL_CONFIG = load_model_config()

# 监听配置
LISTEN = os.getenv("LISTEN", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# 使用HTTP(s)/Socks5代理
#USE_PROXY = False
USE_PROXY = os.getenv("USE_PROXY", "False")
PROXY_URL = os.getenv("PROXY_URL", "socks5://user:pass@ip:port")

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
    reasoning_effort: Optional[str] = "default"

def real_streaming(job, model_name):
    """
    处理 Gradio 的真流式 Job，计算增量并转换为 OpenAI 格式
    """
    chat_id = f"chatcmpl-{uuid.uuid4()}"
    created_time = int(time.time())
    previous_text = ""
    
    try:
        for response in job:
            current_text = str(response)
            if len(current_text) > len(previous_text):
                delta = current_text[len(previous_text):]
                previous_text = current_text
                    
                chunk = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": model_name,
                    "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}]
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        if not previous_text:
            # 尝试获取 job 的最终状态或报错信息
            try:
                _ = job.result()
            except Exception as job_error:
                raise Exception(f"[API Error]  {str(job_error)}")

        yield f"data: {json.dumps({'id': chat_id, 'object': 'chat.completion.chunk', 'created': created_time, 'model': model_name, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        #print(f"Stream Error: {e}")
        error_msg = f"**{str(e)}**" 
        error_chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model_name,
            "choices": [{"index": 0, "delta": {"content": error_msg}, "finish_reason": "stop"}]
        }
        yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

async def simulate_streaming(full_text: str, model_name: str, reasoning: str):
    chat_id = f"chatcmpl-{uuid.uuid4()}"
    created_time = int(time.time())
    
    # 1. 解析思维链和正文
    if reasoning is not None:
        content = full_text
    else:
        reasoning, content = parse_reasoning(full_text)

    # 2. 发送思维链部分
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
    return {
        "object": "list",
        "data": [{"id": m_id, "object": "model", "created": int(time.time())} for m_id in MODEL_CONFIG.keys()]
    }

@app.post("/v1/chat/completions")
async def create_chat_completion(
    request: ChatCompletionRequest, 
    hf_token: str = Depends(get_hf_token)
):

    if request.model not in MODEL_CONFIG:
        raise HTTPException(status_code=400, detail=f"Model '{request.model}' is not configured.")
    
    model_conf = MODEL_CONFIG[request.model]
    
    system_prompt = "You are a helpful assistant."
    user_input = ""

    for msg in request.messages:
        if msg.role == "system":
            system_prompt = msg.content
            break

    if model_conf.get("enable_history", False):
        for msg in request.messages:
            if msg.role == "user":
                user_input += f"User: {msg.content}\n"
            elif msg.role == "assistant":
                user_input += f"Assistant: {msg.content}\n"
    else:
        last_user_msg = next((m for m in reversed(request.messages) if m.role == "user"), None)
        user_input = last_user_msg.content

    # 处理 reasoning_effort 并拼接至 system_prompt
    if request.reasoning_effort:
        system_prompt += f"], [Reasoning:{request.reasoning_effort}"

    async def do_predict(token: Optional[str]):
        client = get_gradio_client(request.model, token)
        
        api_name = model_conf.get("api_name", "/chat")
        payload = {"api_name": api_name}
        
        enable_sys = model_conf.get("enable_system_prompt", False)
        if not enable_sys:
            final_user_input = f"[[system:{system_prompt}], [{user_input}]]"
        else:
            final_user_input = user_input
        
        input_type = model_conf.get("input_payload_type", "str")
        
        if input_type == "dict":
            input_data = {
                "text": final_user_input, 
                "files": [] 
            }
        else:
            input_data = final_user_input
        
        user_key = model_conf.get("user_param_name", "message")

        payload[user_key] = input_data
        
        sys_key = model_conf.get("system_param_name")
        if enable_sys and sys_key:
            payload[sys_key] = system_prompt
        
        request_params = {
            "max_new_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "top_k": request.top_k,
            "repetition_penalty": request.repetition_penalty,
            "reasoning_effort": request.reasoning_effort,
        }
        
        allowlist = model_conf.get("parameter_allowlist", [])
        for param in allowlist:
            if param in request_params:
                payload[param] = request_params[param]
        
        #print(f"\n[Debug] Model: {request.model} | Space: {model_conf.get('space')}")
        #print(f"[Debug] Payload:\n{json.dumps(payload, default=str, ensure_ascii=False, indent=2)}")
        #print("-" * 50)
        
        should_stream = request.stream and model_conf.get("enable_streaming", False)
        
        if should_stream:
            return client.submit(**payload)
        else:
            return await anyio.to_thread.run_sync(partial(client.predict, **payload))


    # 带 Token 尝试 -> 失败则匿名尝试
    try:
        try:
            full_response = await do_predict(hf_token)
        except Exception as e:
            error_msg = str(e).lower()
            #print(f"Token error detected, falling back to anonymous: {e}")
            # 如果提供了 Token 且报错包含 401(无效)、429(超限) 或 token 相关关键字
            if hf_token and any(x in error_msg for x in ["401", "429", "token", "limit", "quota"]):
                print("Error detected, Retrying...")
                full_response = await do_predict(None)
            else:
                raise e
        
        if isinstance(full_response, Job):
            return StreamingResponse(
                real_streaming(full_response, request.model), 
                media_type="text/event-stream"
            )
        
        reasoning = None
        
        if isinstance(full_response, (tuple, list)):
            reasoning, *rest = full_response
            reasoning = str(reasoning)
            full_response = str(rest[0]) if rest else str(full_response)
        
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
