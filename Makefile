.PHONY: help build up down restart logs logs-f health status backup clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build the Docker image
	docker-compose build

up: ## Start the container
	docker-compose up -d
	@echo "Container started. Check logs with: make logs-f"

down: ## Stop and remove the container
	docker-compose down

restart: ## Restart the container
	docker-compose restart
	@echo "Container restarted"

rebuild: ## Rebuild and restart the container
	docker-compose up -d --build
	@echo "Container rebuilt and restarted"

logs: ## Show container logs (last 100 lines)
	docker-compose logs --tail=100 nps-ivr

logs-f: ## Follow container logs in real-time
	docker-compose logs -f nps-ivr

health: ## Check container health
	@curl -s http://localhost:8000/health | jq || echo "Service not responding"

status: ## Show container status
	docker-compose ps
	@echo ""
	@echo "Health Status:"
	@docker inspect --format='{{.State.Health.Status}}' nps-ivr 2>/dev/null || echo "Container not running"

stats: ## Show container resource usage
	docker stats nps-ivr --no-stream

backup: ## Backup the database
	@mkdir -p ./backups
	@cp ./data/nps_ivr.db ./backups/nps_ivr.db.backup.$$(date +%Y%m%d_%H%M%S)
	@echo "Database backed up to ./backups/"

clean: ## Stop container and remove volumes (WARNING: deletes database!)
	@read -p "This will delete the database. Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v; \
		echo "Container and volumes removed"; \
	fi

shell: ## Open a shell in the running container
	docker-compose exec nps-ivr /bin/bash

db-shell: ## Open SQLite shell for database
	docker-compose exec nps-ivr sqlite3 /data/nps_ivr.db

test-local: ## Test locally before deployment
	@echo "Testing health endpoint..."
	@curl -s http://localhost:8000/health
	@echo ""
	@echo "Testing with ngrok (run 'ngrok http 8000' in another terminal first)"

errors: ## Show recent errors from logs
	docker-compose logs nps-ivr | grep ERROR | tail -20

api-logs: ## Show NPA API call logs
	docker-compose logs nps-ivr | grep "NPA API" | tail -20

leads: ## Show successful lead submissions
	docker-compose logs nps-ivr | grep "Successfully created" | tail -10
