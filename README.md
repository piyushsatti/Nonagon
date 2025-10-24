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
| `ATLAS_URI` | Yes | MongoDB connection string shared by both services. |
| `MONGO_URI` | Optional | Alias used by the bot; defaults to `ATLAS_URI`. |
| `MONGODB_URI` | Optional | Alias used by the API; defaults to `ATLAS_URI`. |
| `DB_NAME` | Yes | Logical database name for the API service (e.g., `nonagon`). |
| `BOT_TOKEN` | Yes | Discord bot token for authenticating the gateway connection. |

### Running the Application

```bash
docker compose up --build -d
```

This builds the images, starts the API on port `8000`, and launches the Discord bot.

After inviting the bot to a guild, an administrator should run `/setup` once to create the default Quest Manager role, sign-up channel, and log channel. Use `/setup_status` to review the configuration or `/setup_reset` to clear stored settings if you need to start over.

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
