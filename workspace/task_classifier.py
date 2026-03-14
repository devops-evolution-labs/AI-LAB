def classify_task(prompt: str, has_image: bool = False) -> str:
    p = (prompt or "").lower()

    if has_image or "image" in p or "screenshot" in p or "ui" in p or "layout" in p:
        return "visao"

    if "embedding" in p or "vetor" in p or "vector" in p or "rag" in p:
        return "vetores"

    if "react" in p or "code" in p or "function" in p or "api" in p:
        return "codigo"

    if "plan" in p or "steps" in p or "planejar" in p or "planejamento" in p:
        return "agentes"

    if "raciocinio" in p or "prove" in p or "deriv" in p or "otimiz" in p or "complex" in p:
        return "raciocinio"

    if len(p) < 160:
        return "rapido"

    return "chat"
