import base64

from llm_client import call_llm_messages
from models_registry import MODELS

def analyze_image(image_path):

    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode()

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text",
                 "text": "Analyze this UI layout and describe components as JSON."},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
            ]
        }
    ]

    return call_llm_messages(
        MODELS["visual"]["name"],
        messages
    )
