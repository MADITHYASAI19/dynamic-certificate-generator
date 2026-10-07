# Bulk Certificate Generator

Production-ready API for generating PDF certificates in bulk.

## Quick Start

1. Copy environment example:
   ```bash
   cp .env.example .env
   ```

2. Run with Docker Compose:
   ```bash
   make up
   ```
   or
   ```bash
   docker compose up -d --build
   ```

3. Verify health check:
   ```bash
   curl http://localhost:8000/health
   ```

## Development

- `make test` - Run tests
- `make lint` - Run ruff and mypy
- `make format` - Format code with ruff and black
- `make migrate` - Apply DB migrations
