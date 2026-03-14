from fastapi import FastAPI
import requests
import redis
import hashlib

app = FastAPI()

# Nota: este servidor local com Redis nao e usado pelo stack atual do Docker Compose.
# Mantido para compatibilidade futura; nao referenciar sem adicionar o servico redis.

LLM_ENDPOINT = "http://llama-router:11434/v1/chat/completions"
r = redis.Redis(host="redis", port=6379, decode_responses=True)

def hash_prompt(prompt):
    return hashlib.sha256(prompt.encode()).hexdigest()

@app.post("/chat")
async def chat(payload: dict):

    prompt = str(payload)

    key = hash_prompt(prompt)

    cached = r.get(key)

    if cached:
        return {"cached": True, "response": cached}

    response = requests.post(
        LLM_ENDPOINT,
        json=payload
    ).json()

    r.set(key, str(response), ex=3600)

    return response
