TOP_DIR := .
SRC_DIR := $(TOP_DIR)/src
TEST_DIR := $(TOP_DIR)/tests
DIST_DIR := $(TOP_DIR)/dist

UV := uv
SYNC := $(UV) sync
BUILD := $(UV) build
PYTHON := $(UV) run python
PYTEST := $(UV) run pytest -v -s --timeout=120 --timeout-method=thread
RUFF_CHECK := $(UV) run ruff check --fix --ignore E501
RUFF_FORMAT := $(UV) run ruff format
UVICORN := $(UV) run uvicorn

APP_MODULE := app.main:app
LOCAL_PORT := 8080

.PHONY: all install dist depends check format test unit integration clean help run export-reqs

all: dist

install: ## Install all dependencies via uv sync
	$(SYNC)

dist: install ## Build the wheel
	$(BUILD)

depends: ## Refresh dependency lock
	@$(SYNC)

check: ## Run ruff lint (autofix)
	$(RUFF_CHECK) $(SRC_DIR) $(TEST_DIR)

format: check ## Run ruff format
	$(RUFF_FORMAT) $(SRC_DIR) $(TEST_DIR)

test: ## Run all tests
	$(PYTEST) -ra --tb=short $(TEST_DIR)

unit: ## Run unit tests only
	$(PYTEST) -ra --tb=short -m unit $(TEST_DIR)

integration: ## Run integration tests (requires live workspace)
	$(PYTEST) -ra --tb=short -m integration $(TEST_DIR)

run: ## Run the agent locally on $(LOCAL_PORT)
	$(UVICORN) $(APP_MODULE) --reload --host 0.0.0.0 --port $(LOCAL_PORT)

export-reqs: ## Export requirements.txt from uv.lock for Databricks Apps runtime
	$(UV) export --format requirements-txt --no-hashes --no-dev -o requirements.txt

clean: ## Remove build artifacts
	rm -rf $(DIST_DIR) .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
