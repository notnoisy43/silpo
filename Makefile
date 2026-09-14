COMPOSE := docker compose

.PHONY: up down logs migrate seed test fmt

.env:
	@echo "Missing .env - run: cp .env.example .env  (then fill it in)" && exit 1

up: .env
	$(COMPOSE) up -d --build
	@echo "web: http://localhost:5173  api: http://localhost:8000/health"

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200

migrate:
	$(COMPOSE) exec api alembic upgrade head

# SPEC-GAP: seed data is defined in later milestones (demo_history.json, M12).
seed:
	@echo "Nothing to seed yet"

test:
	$(COMPOSE) run --rm --no-deps api pytest -q

fmt:
	$(COMPOSE) run --rm --no-deps api ruff format app tests
	$(COMPOSE) run --rm --no-deps api ruff check --fix app tests
