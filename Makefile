.PHONY: run test lint docker-build docker-run clean

run:
	streamlit run app.py

test:
	python -m pytest tests/ -v

lint:
	python -m py_compile app.py
	python -m py_compile src/simulator.py
	python -m py_compile src/charts.py
	python -m py_compile src/analytics.py

docker-build:
	docker build -t debt-payoff-simulator .

docker-run:
	docker run -p 8501:8501 debt-payoff-simulator

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
