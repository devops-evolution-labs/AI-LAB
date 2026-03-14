import requests

LLM_URL = "http://llama-router:11434/v1/chat/completions"


def call_llm_messages(model_name: str, messages: list):
    payload = {
        "model": model_name,
        "messages": messages
    }

    r = requests.post(LLM_URL, json=payload)
    return r.json()


def call_llm(model_name: str, prompt: str):
    return call_llm_messages(
        model_name,
        [{"role": "user", "content": prompt}]
    )


def extract_text(response_json: dict) -> str:
    try:
        return response_json["choices"][0]["message"]["content"]
    except Exception:
        return str(response_json)
