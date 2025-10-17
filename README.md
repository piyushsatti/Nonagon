# Nonagon

Nonagon is a multi-guild Discord automation platform that streamlines quest scheduling, player sign-ups, summaries, and engagement analytics. It bundles a Discord bot with a FastAPI service so community teams can monitor activity and keep adventures moving.

## Tech Stack

- Python 3.11+
- FastAPI & Uvicorn
- discord.py
- MongoDB (Atlas or compatible)
- Docker & Docker Compose

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Configuration

1. Copy the sample environment file (if present) or create a new `.env` at the repository root.
2. Populate the following variables (mirrors `docker-compose.dev.yml`):

| Variable | Required | Notes |
|----------|----------|-------|
| `ATLAS_URI` | Yes | MongoDB connection string used by both API and bot containers. |
| `DB_NAME` | Yes | Logical database name for the API service (e.g., `nonagon`). |
| `BOT_TOKEN` | Yes | Discord bot token for authenticating the gateway connection. |
| `BOT_CLIENT_ID` | Yes | Discord application client ID used when generating invite links. |

> **Action Item:** The current compose file wires `MONGODB_URI` for the API service and `MONGO_URI` for the bot service. Standardize on a single variable name (e.g., `MONGO_URI`) across `docker-compose.dev.yml` and the FastAPI code under `src/app/api` to avoid configuration drift.

### Running the Application

```bash
docker compose -f docker-compose.dev.yml up --build -d
```

This builds the images, starts the API on port `8000`, and launches the Discord bot.

### Running Tests

Placeholder:

```bash
docker compose exec api pytest
```

Adjust the command once the test harness is finalized (e.g., split domain vs. integration suites).

## Project Structure

- `src/app/api` — FastAPI application exposing REST endpoints, demo dashboards, and background tasks.
- `src/app/bot` — Discord bot entrypoint, cogs, services, and infrastructure adapters.
- `docs/` — Architecture notes, product requirements, API/command references.

## API Documentation

- FastAPI auto-generated docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Contributing

Contributions are welcome! Please open an issue or submit a pull request once contribution guidelines are defined.

## License

This project is licensed under the MIT License.
