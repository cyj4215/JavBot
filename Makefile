.PHONY: run test test-unit lint format clean

run:
	python -m app.main

test:
	pytest tests/ -v --no-header

test-unit:
	pytest tests/unit/ -v --no-header

lint:
	ruff check app/ && mypy app/

format:
	ruff format app/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
