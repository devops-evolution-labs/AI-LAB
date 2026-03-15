# AI-LAB

AI-LAB é um servidor local multimodal de IA, com roteamento inteligente de modelos, agentes especializados e integração com Open WebUI. Ele executa tudo localmente via Docker, focado em desempenho e controle.

## Features

- Servidor local de IA com roteamento por tarefa
- Arquitetura multi-modelo (chat, código, visão, agentes, raciocínio, rápido, vetores)
- Orquestração de agentes via FastAPI
- Análise de imagens e geração de UI
- Suporte a RAG (placeholder leve)
- Ferramentas MCP para execução de comandos e integração externa
- Open WebUI integrado como interface de chat

## Architecture

Fluxo principal:

User  
↓  
Open WebUI  
↓  
Agent Runner (FastAPI)  
↓  
Model Router  
↓  
llama-router (llama.cpp)

Responsabilidades:

- Open WebUI: interface de chat e interação do usuário.
- Agent Runner: orquestração de agentes e pipeline de UI.
- Model Router: seleção do modelo mais adequado por tipo de tarefa.
- llama-router: execução local de modelos GGUF com aceleração GPU.

## Project Structure

```text
AI-LAB/
├─ docker-compose.yml
├─ llama/
│  ├─ router.json
│  └─ models/
│     ├─ chat/
│     ├─ codigo/
│     ├─ visual/
│     ├─ agentes/
│     ├─ raciocinio/
│     ├─ rapido/
│     └─ vetores/
├─ workspace/
│  ├─ agent.py
│  ├─ llm_client.py
│  ├─ model_router.py
│  ├─ models_registry.py
│  ├─ task_classifier.py
│  └─ ui_agent/
│     ├─ vision.py
│     ├─ planner_agent.py
│     ├─ codegen.py
│     └─ router_logic.py
└─ rag/
   └─ ingest.py
```

## Models

Os modelos são separados por capacidade para reduzir custo e melhorar precisão:

- `chat`: conversa geral e assistência
- `codigo`: geração e análise de código
- `visual`: análise de imagens e UI
- `agentes`: planejamento e orquestração
- `raciocinio`: tarefas complexas de raciocínio
- `rapido`: respostas rápidas e simples
- `vetores`: embeddings para RAG

## How It Works

Pipeline de roteamento:

1. O usuário envia uma mensagem no Open WebUI.
2. O Agent Runner classifica a tarefa.
3. O Model Router escolhe o modelo ideal.
4. O llama-router executa o modelo e retorna a resposta.

Pipeline do UI Agent:

1. Imagem (screenshot) é enviada.
2. Modelo de visão descreve a UI.
3. Planner cria a árvore de componentes.
4. Codegen gera o código de interface.

## Running the Project

```bash
git clone <seu-repo>
cd AI-LAB
make up
```

Ambiente de desenvolvimento com hot reload no `agent-runner`:

```bash
make up-dev
```

Portas principais:

- `11434`: llama-router (API OpenAI compatível)
- `3100`: Open WebUI
- `3300`: Agent Runner (FastAPI)
- `3402`: MCP Shell
- `3403`: MCP Git
- `3404`: MCP Web Fetch

## Example Use Cases

- Gerar UI a partir de screenshot
- Assistente local de programação
- Chat local com modelos especializados
- Busca semântica em documentos (RAG)

## Future Improvements

- CI/CD e validações automatizadas
- Observabilidade e métricas
- Deploy em Kubernetes
- Gestão avançada de modelos
- Orquestração multi-agente distribuída

## License

TODO: definir licença.
