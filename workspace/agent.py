from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
import os
import tempfile
import json
import math
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
MAX_CONTEXT_TOKENS = int(os.getenv("AI_LAB_MAX_CONTEXT_TOKENS", "3072"))
TOKEN_SAFETY_MARGIN = int(os.getenv("AI_LAB_CONTEXT_MARGIN", "512"))
CHARS_PER_TOKEN = float(os.getenv("AI_LAB_CHARS_PER_TOKEN", "2.2"))


def _fetch_models():
    r = requests.get(LLAMA_MODELS_URL, timeout=10)
    r.raise_for_status()
    return r.json()


def _models_status_payload(raw_models: dict):
    data = raw_models.get("data", [])
    summary = {"loaded": 0, "loading": 0, "unloaded": 0, "unknown": 0}
    summary_pt = {"ativo": 0, "carregando": 0, "desativado": 0, "desconhecido": 0}
    models = []
    status_map = {
        "loaded": "ativo",
        "loading": "carregando",
        "unloaded": "desativado",
        "unknown": "desconhecido"
    }

    for item in data:
        status = item.get("status", {}).get("value", "unknown")
        if status not in summary:
            status = "unknown"
        summary[status] += 1
        status_pt = status_map[status]
        summary_pt[status_pt] += 1

        status_obj = item.get("status", {}) if isinstance(item.get("status"), dict) else {}
        vram_mb = (
            status_obj.get("vram_mb")
            or status_obj.get("gpu_vram_mb")
            or status_obj.get("memory_vram_mb")
        )

        models.append({
            "id": item.get("id"),
            "status": status,
            "status_pt": status_pt,
            "vram_mb": vram_mb
        })

    return {
        "summary": summary,
        "summary_pt": summary_pt,
        "active_models": [m["id"] for m in models if m["status"] == "loaded"],
        "modelos_ativos": [m["id"] for m in models if m["status"] == "loaded"],
        "models": models
    }


def _estimate_tokens_from_text(value: str) -> int:
    # Heuristica conservadora para reduzir estouro de contexto em prompts de codigo.
    return max(1, math.ceil(len(value) / CHARS_PER_TOKEN))


def _message_token_cost(message: dict) -> int:
    overhead = 12
    content = message.get("content", "")
    if isinstance(content, str):
        return _estimate_tokens_from_text(content) + overhead
    if isinstance(content, list):
        total = 0
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    total += _estimate_tokens_from_text(item.get("text", ""))
                elif item.get("type") == "image_url":
                    total += 120
        return max(1, total + overhead)
    return _estimate_tokens_from_text(str(content)) + overhead


def _trim_messages_for_context(messages: list, max_tokens: int) -> list:
    if not messages:
        return []

    budget = max(256, max_tokens - TOKEN_SAFETY_MARGIN)
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]
    if not non_system:
        return messages

    kept = []
    used = 0

    last_msg = non_system[-1]
    used += _message_token_cost(last_msg)
    kept.append(last_msg)

    for msg in reversed(non_system[:-1]):
        cost = _message_token_cost(msg)
        if used + cost > budget:
            continue
        kept.append(msg)
        used += cost

    kept_system = []
    for sm in system_msgs:
        cost = _message_token_cost(sm)
        if used + cost > budget:
            break
        kept_system.append(sm)
        used += cost

    kept.reverse()
    return kept_system + kept


def _looks_like_context_overflow(response_json: dict) -> bool:
    try:
        text = json.dumps(response_json).lower()
    except Exception:
        text = str(response_json).lower()
    return (
        "exceeds the available context size" in text
        or ("context size" in text and "exceeds" in text)
    )


def _retry_body_with_tighter_context(body: dict) -> dict:
    new_body = dict(body)
    msgs = new_body.get("messages")
    if isinstance(msgs, list):
        tighter_limit = max(768, int(MAX_CONTEXT_TOKENS * 0.65))
        new_body["messages"] = _trim_messages_for_context(msgs, tighter_limit)
    return new_body


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


@app.post("/chat")
async def chat(data: dict):
    messages = data.get("messages", [])
    if isinstance(messages, list):
        messages = _trim_messages_for_context(messages, MAX_CONTEXT_TOKENS)
    prompt = _last_user_text(messages)
    task = classify_task(prompt, has_image=_has_image(messages))
    model = route_task(task)["name"]
    return call_llm_messages(model, messages)


@app.get("/v1/models")
async def v1_models():
    try:
        raw = _fetch_models()
        return JSONResponse(raw, status_code=200)
    except Exception as exc:
        return JSONResponse(
            {"error": {"message": f"Gateway error: {exc}", "type": "gateway_error"}},
            status_code=502
        )


@app.get("/v1/models/status")
async def v1_models_status():
    try:
        raw = _fetch_models()
        return JSONResponse(_models_status_payload(raw), status_code=200)
    except Exception as exc:
        return JSONResponse(
            {"error": {"message": f"Gateway error: {exc}", "type": "gateway_error"}},
            status_code=502
        )


@app.get("/models/dashboard", response_class=HTMLResponse)
async def models_dashboard():
    html = """
<!doctype html>
<html lang=\"pt-BR\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>AI-LAB Models Status</title>
  <style>
    :root { color-scheme: dark; }
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; background: #0b1220; color: #dbe7ff; margin: 0; padding: 24px; }
    .card { max-width: 980px; margin: 0 auto; background: #111a2d; border: 1px solid #253350; border-radius: 12px; padding: 18px; }
    h1 { font-size: 20px; margin: 0 0 14px; }
    .meta { display: flex; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
    .pill { padding: 6px 10px; border-radius: 999px; border: 1px solid #33496e; background: #17233d; font-size: 12px; }
    .alert { margin: 12px 0; padding: 10px 12px; border-radius: 10px; border: 1px solid #6e4f11; background: #3a2a08; color: #ffd27d; display: none; }
    .alert.show { display: block; }
    .linkbar { margin-bottom: 10px; }
    .linkbar a { color: #9ec5ff; text-decoration: none; }
    .linkbar a:hover { text-decoration: underline; }
    table { width: 100%; border-collapse: collapse; margin-top: 8px; }
    th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid #22314d; }
    th { color: #9cb4dd; font-weight: 600; }
    .status { font-size: 12px; padding: 4px 8px; border-radius: 999px; display: inline-block; }
    .loaded { background: #103720; color: #8ff0b0; border: 1px solid #225f3a; }
    .loading { background: #3a2a08; color: #ffd27d; border: 1px solid #6e4f11; }
    .unloaded { background: #2d1a1a; color: #ffb3b3; border: 1px solid #5c2e2e; }
    .unknown { background: #263142; color: #c8d5ef; border: 1px solid #42597f; }
    .muted { color: #89a0c8; font-size: 12px; margin-top: 10px; }
    code { color: #bcd0f7; }
  </style>
</head>
<body>
  <div class=\"card\">
    <h1>AI-LAB - Modelos Ativos</h1>
    <div class=\"linkbar\">
      <a href=\"http://localhost:3100\" target=\"_blank\" rel=\"noreferrer\">Abrir Open WebUI</a>
    </div>
    <div id=\"alert\" class=\"alert\">Nenhum modelo ativo no momento.</div>
    <div class=\"meta\">
      <span class=\"pill\" id=\"ativo\">ativo: 0</span>
      <span class=\"pill\" id=\"carregando\">carregando: 0</span>
      <span class=\"pill\" id=\"desativado\">desativado: 0</span>
      <span class=\"pill\" id=\"active\">modelos ativos: -</span>
    </div>
    <table>
      <thead>
        <tr><th>Modelo</th><th>Status</th><th>VRAM (MB)</th></tr>
      </thead>
      <tbody id=\"rows\"></tbody>
    </table>
    <div class=\"muted\">
      Atualizacao automatica a cada 2s - Fonte: <code>/v1/models/status</code>
    </div>
  </div>
  <script>
    async function refresh() {
      try {
        const r = await fetch('/v1/models/status', { cache: 'no-store' });
        const data = await r.json();
        const s = data.summary_pt || {};
        document.getElementById('ativo').textContent = `ativo: ${s.ativo || 0}`;
        document.getElementById('carregando').textContent = `carregando: ${s.carregando || 0}`;
        document.getElementById('desativado').textContent = `desativado: ${s.desativado || 0}`;
        const active = (data.modelos_ativos || []).join(', ') || '-';
        document.getElementById('active').textContent = `modelos ativos: ${active}`;

        const alert = document.getElementById('alert');
        if ((data.modelos_ativos || []).length === 0) {
          alert.classList.add('show');
        } else {
          alert.classList.remove('show');
        }

        const rows = document.getElementById('rows');
        rows.innerHTML = '';
        for (const m of (data.models || [])) {
          const tr = document.createElement('tr');
          const tdModel = document.createElement('td');
          tdModel.textContent = m.id || '-';
          const tdStatus = document.createElement('td');
          const span = document.createElement('span');
          const cssStatus = (m.status || 'unknown');
          span.className = `status ${cssStatus}`;
          span.textContent = m.status_pt || 'desconhecido';
          tdStatus.appendChild(span);
          const tdVram = document.createElement('td');
          tdVram.textContent = Number.isFinite(m.vram_mb) ? String(m.vram_mb) : 'n/d';
          tr.appendChild(tdModel);
          tr.appendChild(tdStatus);
          tr.appendChild(tdVram);
          rows.appendChild(tr);
        }
      } catch (e) {}
    }
    refresh();
    setInterval(refresh, 2000);
  </script>
</body>
</html>
"""
    return HTMLResponse(html)


@app.post("/v1/chat/completions")
async def v1_chat_completions(request: Request):
    body = await request.json()
    stream = bool(body.get("stream"))

    if isinstance(body.get("messages"), list):
        body["messages"] = _trim_messages_for_context(
            body["messages"],
            MAX_CONTEXT_TOKENS
        )

    if stream:
        return StreamingResponse(
            _proxy_stream(body),
            media_type="text/event-stream"
        )

    try:
        r = requests.post(LLAMA_CHAT_URL, json=body, timeout=REQUEST_TIMEOUT)
        payload = r.json()

        if r.status_code == 400 and _looks_like_context_overflow(payload):
            retry_body = _retry_body_with_tighter_context(body)
            r2 = requests.post(LLAMA_CHAT_URL, json=retry_body, timeout=REQUEST_TIMEOUT)
            return JSONResponse(r2.json(), status_code=r2.status_code)

        return JSONResponse(payload, status_code=r.status_code)
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
                "question": "Qual framework deseja usar?\n1 React + Tailwind\n2 Next.js\n3 Vue\n4 HTML puro"
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

