.PHONY: help install setup check lint format type test test-unit test-integration coverage clean build docs wiki pipeline daily backup

# Default target
help:
	@echo "SONAR · Common commands"
	@echo ""
	@echo "Setup:"
	@echo "  install       Install package + dev dependencies (uses uv)"
	@echo "  setup         First-time setup (install + pre-commit + init-db)"
	@echo "  init-db       Initialize empty database"
	@echo ""
	@echo "Code quality:"
	@echo "  check         Run all checks (lint + type + test-unit)"
	@echo "  lint          Ruff linting"
	@echo "  format        Ruff format (auto-fix)"
	@echo "  type          MyPy type checking"
	@echo ""
	@echo "Testing:"
	@echo "  test          All tests (unit + integration)"
	@echo "  test-unit     Fast unit tests only"
	@echo "  test-integration  Integration tests (requires API keys)"
	@echo "  coverage      Unit tests with coverage report"
	@echo ""
	@echo "Operations:"
	@echo "  pipeline      Run daily pipeline"
	@echo "  daily         Alias for pipeline"
	@echo "  backup        Backup database"
	@echo ""
	@echo "Docs:"
	@echo "  docs          Build documentation (if mkdocs configured)"
	@echo "  wiki          Sync docs/wiki to GitHub Wiki"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean         Remove build artifacts, caches"
	@echo "  clean-data    ⚠️ Remove local database (destructive)"

install:
	uv pip install -e ".[dev]"

setup: install
	pre-commit install
	pre-commit install --hook-type commit-msg
	mkdir -p data logs
	@if [ ! -f .env ]; then cp .env.example .env && echo ".env created — edit with your API keys"; fi
	python scripts/init_db.py || echo "Initialize DB manually once scripts/init_db.py exists"
	@echo ""
	@echo "✅ Setup complete. Edit .env with your API keys, then run:"
	@echo "   make check"

init-db:
	python scripts/init_db.py

check: lint type test-unit
	@echo "✅ All checks passed"

lint:
	ruff check sonar tests

format:
	ruff check --fix sonar tests
	ruff format sonar tests

type:
	mypy sonar

test: test-unit test-integration

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

coverage:
	pytest tests/unit/ --cov=sonar --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "📊 Coverage report: open htmlcov/index.html"

pipeline daily:
	sonar pipeline daily

backup:
	@mkdir -p data/backups
	@BACKUP_FILE="data/backups/sonar-$$(date +%Y-%m-%d-%H%M%S).db" && \
		sqlite3 data/sonar.db ".backup $$BACKUP_FILE" && \
		echo "✅ Backup created: $$BACKUP_FILE"

docs:
	@if [ -f mkdocs.yml ]; then mkdocs build; else echo "mkdocs.yml not yet configured"; fi

wiki:
	@echo "Syncing docs/wiki to GitHub Wiki..."
	@echo "TODO: implement sync script"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build dist *.egg-info htmlcov .coverage coverage.xml

clean-data:
	@echo "⚠️ This will DELETE the local database!"
	@read -p "Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ]
	rm -f data/sonar.db data/sonar.db-journal
	@echo "Database deleted. Run 'make init-db' to recreate."
