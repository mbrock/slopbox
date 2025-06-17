# Slopbox Development Makefile

.PHONY: help videosync slopbox install lint format test clean

help:  ## Show this help message
	@echo "Slopbox Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make videosync          # Start video sync tool"
	@echo "  make slopbox            # Start full slopbox app"
	@echo "  make videosync PORT=3000 # Video sync on custom port"

videosync:  ## Start video sync development server
	@./dev videosync $(if $(PORT),--port $(PORT)) $(if $(HOST),--host $(HOST))

slopbox:  ## Start slopbox development server
	@./dev slopbox $(if $(PORT),--port $(PORT)) $(if $(HOST),--host $(HOST))

install:  ## Install dependencies
	uv sync

lint:  ## Run linting
	uv run ruff check src/ tests/

format:  ## Format code
	uv run ruff format src/ tests/

test:  ## Run tests
	uv run python -m pytest tests/ -v

clean:  ## Clean up temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +

# Default target
.DEFAULT_GOAL := help