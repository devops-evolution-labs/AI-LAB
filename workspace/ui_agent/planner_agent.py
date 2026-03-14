from llm_client import call_llm_messages, extract_text
from models_registry import MODELS


def create_ui_plan(layout_description):

    prompt = f"""
You are an AI system planner.

Your job is to convert UI descriptions into a structured build plan.

Return JSON only.

Layout description:
{layout_description}

Output format example:

{{
 "components": ["navbar", "sidebar", "cards"],
 "structure": [
   "create layout grid",
   "create navigation",
   "create main dashboard area",
   "add components"
 ]
}}
"""

    messages = [
        {"role": "user", "content": prompt}
    ]

    response = call_llm_messages(
        MODELS["agentes"]["name"],
        messages
    )

    return extract_text(response)
