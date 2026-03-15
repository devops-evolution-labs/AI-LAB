COMPOSE=docker compose -f docker-compose.yml
COMPOSE_DEV=docker compose -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: up down logs ps up-dev down-dev logs-dev ps-dev watch-dev

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200

ps:
	$(COMPOSE) ps

up-dev:
	$(COMPOSE_DEV) up --build -d

watch-dev:
	$(COMPOSE_DEV) up --build -d
	$(COMPOSE_DEV) watch agent-runner

down-dev:
	$(COMPOSE_DEV) down

logs-dev:
	$(COMPOSE_DEV) logs -f --tail=200

ps-dev:
	$(COMPOSE_DEV) ps
