.PHONY: install dev backend frontend up down reset demo

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && uvicorn main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

dev:
	@echo "Start backend in one terminal: make backend"
	@echo "Start frontend in another:    make frontend"

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

reset:
	curl -s -X POST http://localhost:8000/simulate/reset | python -m json.tool

start:
	curl -s -X POST http://localhost:8000/simulate/start | python -m json.tool

demo:
	@echo "==> Starting simulation..."
	curl -s -X POST http://localhost:8000/simulate/start
	@echo ""
	@echo "==> Setting scenario: bad_deployment"
	curl -s -X POST http://localhost:8000/simulate/scenario -H "Content-Type: application/json" -d '{"scenario":"bad_deployment"}' | python -m json.tool

cascade:
	curl -s -X POST http://localhost:8000/simulate/scenario -H "Content-Type: application/json" -d '{"scenario":"cascading_failure"}' | python -m json.tool

normal:
	curl -s -X POST http://localhost:8000/simulate/scenario -H "Content-Type: application/json" -d '{"scenario":"normal"}' | python -m json.tool

status:
	curl -s http://localhost:8000/simulate/status | python -m json.tool

incidents:
	curl -s http://localhost:8000/incidents | python -m json.tool

health:
	curl -s http://localhost:8000/summary/system | python -m json.tool
