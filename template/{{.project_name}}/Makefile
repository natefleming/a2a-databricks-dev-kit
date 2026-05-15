UV := uv
SYNC := $(UV) sync
PYTEST := $(UV) run pytest -v -s --timeout=120 --timeout-method=thread

.PHONY: install unit deploy run clean

install:
	$(SYNC)

unit:
	$(PYTEST) -m unit tests

run:
	$(UV) run uvicorn app.main:app --reload --port 8080

deploy:
	databricks bundle deploy -t dev
	databricks bundle run a2a_agent_app -t dev

clean:
	rm -rf .pytest_cache .ruff_cache dist build
