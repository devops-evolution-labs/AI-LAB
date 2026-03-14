from models_registry import MODELS


def route_task(task: str):
    if task in ("chat",):
        return MODELS["chat"]

    if task in ("codigo", "code_generation"):
        return MODELS["codigo"]

    if task in ("visao", "vision_analysis"):
        return MODELS["visual"]

    if task in ("agentes", "agent_planning"):
        return MODELS["agentes"]

    if task in ("raciocinio", "complex_reasoning"):
        return MODELS["raciocinio"]

    if task in ("rapido", "simple_task"):
        return MODELS["rapido"]

    if task in ("vetores", "embeddings", "rag_embeddings"):
        return MODELS["vetores"]

    return MODELS["chat"]
