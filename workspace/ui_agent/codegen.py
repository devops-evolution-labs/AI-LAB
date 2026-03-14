from llm_client import call_llm_messages
from models_registry import MODELS

def generate_code(layout_description, framework):

    prompt = f"""
You are a frontend engineer.

Framework: {framework}

Generate production ready code based on this plan:

{layout_description}

Return only code.
"""

    messages = [{"role": "user", "content": prompt}]

    return call_llm_messages(
        MODELS["codigo"]["name"],
        messages
    )
