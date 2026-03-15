from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, StreamingResponse
import os
import tempfile
import json
import requests

from llm_client import call_llm_messages, extract_text
from task_classifier import classify_task
from model_router import route_task
from ui_agent.vision import analyze_image
from ui_agent.planner_agent import create_ui_plan
from ui_agent.codegen import generate_code
from ui_agent.router_logic import choose_framework

app = FastAPI()

LLAMA_BASE_URL = "http://llama-router:11434/v1"
LLAMA_CHAT_URL = f"{LLAMA_BASE_URL}/chat/completions"
LLAMA_MODELS_URL = f"{LLAMA_BASE_URL}/models"

REQUEST_TIMEOUT = 180


def _proxy_stream(json_body: dict):
    try:
        with requests.post(
            LLAMA_CHAT_URL,
            json=json_body,
            stream=True,
            timeout=(10, REQUEST_TIMEOUT)
        ) as r:
            r.raise_for_status()
            for chunk in r.iter_lines():
                if chunk:
                    yield chunk + b"\n"
    except Exception as exc:
        err = {
            "error": {
                "message": f"Gateway error: {exc}",
                "type": "gateway_error"
            }
        }
        yield f"data: {json.dumps(err)}\n\n".encode("utf-8")
        yield b"data: [DONE]\n\n"
 
def _has_image(messages: list) -> bool:
    for msg in messages or []:
        content = msg.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "image_url":
                    return True
    return False


def _last_user_text(messages: list) -> str:
    if not messages:
        return ""
    last = messages[-1].get("content", "")
    if isinstance(last, str):
        return last
    if isinstance(last, list):
        texts = []
        for item in last:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
        return "\n".join(texts)
    return str(last)


# =========================
# CHAT ENDPOINT
# =========================

@app.post("/chat")
async def chat(data: dict):

    messages = data.get("messages", [])
    prompt = _last_user_text(messages)
    task = classify_task(prompt, has_image=_has_image(messages))
    model = route_task(task)["name"]

    return call_llm_messages(model, messages)


@app.get("/v1/models")
async def v1_models():
    try:
        r = requests.get(LLAMA_MODELS_URL, timeout=10)
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception as exc:
        return JSONResponse(
            {"error": {"message": f"Gateway error: {exc}", "type": "gateway_error"}},
            status_code=502
        )


@app.post("/v1/chat/completions")
async def v1_chat_completions(request: Request):
    body = await request.json()
    stream = bool(body.get("stream"))

    if stream:
        return StreamingResponse(
            _proxy_stream(body),
            media_type="text/event-stream"
        )

    try:
        r = requests.post(LLAMA_CHAT_URL, json=body, timeout=REQUEST_TIMEOUT)
        return JSONResponse(r.json(), status_code=r.status_code)
    except requests.Timeout:
        return JSONResponse(
            {"error": {"message": "Timeout ao gerar resposta.", "type": "timeout"}},
            status_code=504
        )
    except Exception as exc:
        return JSONResponse(
            {"error": {"message": f"Gateway error: {exc}", "type": "gateway_error"}},
            status_code=502
        )


# =========================
# UI AGENT
# =========================

@app.post("/ui-agent")
async def ui_agent(
    prompt: str = Form(...),
    file: UploadFile = File(...)
):
    prompt_text = prompt or ""
    layout_description = prompt_text
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            temp_path = tmp.name
            tmp.write(await file.read())

        vision_result = analyze_image(temp_path)
        layout_description = extract_text(vision_result)

        plan_text = create_ui_plan(layout_description)

        framework = choose_framework(prompt_text)
        if framework == "ask-user":
            return {
                "question":
                "Qual framework deseja usar?\n1 React + Tailwind\n2 Next.js\n3 Vue\n4 HTML puro"
            }

        code_result = generate_code(plan_text, framework)

        return {
            "framework": framework,
            "result": code_result
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass
