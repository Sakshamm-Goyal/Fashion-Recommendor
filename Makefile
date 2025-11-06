.PHONY: up down logs install seed demo test test-all test-trends test-gaps test-search test-e2e quick-demo

up:
	docker compose up -d

down:
	docker compose down -v

logs:
	docker compose logs -f

install:
	python3 -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -r requirements.txt

seed:
	. .venv/bin/activate && python scripts/seed_products.py

demo:
	. .venv/bin/activate && python scripts/smoke_demo.py

# Testing commands
test:
	. .venv/bin/activate && python scripts/test_pipeline.py --config

test-all:
	. .venv/bin/activate && python scripts/test_pipeline.py --all

test-trends:
	. .venv/bin/activate && python scripts/test_pipeline.py --trends

test-gaps:
	. .venv/bin/activate && python scripts/test_pipeline.py --gaps

test-search:
	. .venv/bin/activate && python scripts/test_pipeline.py --search

test-e2e:
	. .venv/bin/activate && python scripts/test_pipeline.py --e2e

quick-demo:
	. .venv/bin/activate && python scripts/quick_demo.py
