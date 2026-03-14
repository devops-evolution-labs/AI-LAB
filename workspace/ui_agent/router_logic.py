def choose_framework(prompt, project_context=""):

    prompt = prompt.lower()
    project_context = project_context.lower()

    if "next" in project_context:
        return "nextjs"

    if "react" in project_context:
        return "react"

    if "vue" in project_context:
        return "vue"

    if "dashboard" in prompt or "complex ui" in prompt:
        return "react"

    if "landing" in prompt or "simple page" in prompt:
        return "html"

    return "ask-user"