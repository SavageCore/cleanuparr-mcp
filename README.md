# cleanuparr-mcp

An MCP server exposing Cleanuparr's REST API as tools for inspecting status,
history, statistics, jobs, and configuration.

## Requirements

- Cleanuparr with its REST API enabled
- An API key from Cleanuparr
- Python 3.11+ and `uv` for source development

## Configuration

| Variable | Required | Description |
| --- | --- | --- |
| `CLEANUPARR_URL` | Yes | Cleanuparr URL, including any reverse-proxy `BASE_PATH`; the server appends `/api`. |
| `CLEANUPARR_API_KEY` | Usually | API key sent as `X-Api-Key`. Health endpoints can be used without it when permitted. |

Install a built wheel and register it with Claude Code:

```bash
uv tool install cleanuparr_mcp-*.whl
claude mcp add cleanuparr \
  --env CLEANUPARR_URL=https://cleanuparr.example.com \
  --env CLEANUPARR_API_KEY=your-api-key \
  -- cleanuparr-mcp
```

For a source checkout:

```bash
uv sync
claude mcp add cleanuparr \
  --env CLEANUPARR_URL=https://cleanuparr.example.com \
  --env CLEANUPARR_API_KEY=your-api-key \
  -- uv run --directory /path/to/cleanuparr-mcp cleanuparr-mcp
```

## Tools

The server exposes the full practical Cleanuparr API surface:

- Health and status: health, readiness, detailed health, health checks, system, *arr, and download-client status.
- Jobs: list, inspect, trigger, start, and schedule jobs.
- History: events, manual events, strikes, timelines, stats, Seeker search events, and custom-format scores.
- Configuration: general, *arr instances, download clients, queue rules, queue/download cleaners, dead torrents, orphaned/unlinked files, seeding rules, malware blocker, Seeker, blacklist sync, and notifications.

Write tools are marked destructive where appropriate. Cleanuparr returns `503`
when its configuration database is busy; this server does not retry and instead
returns the upstream error to the MCP client.

Request bodies are pass-through JSON dictionaries matching the DTOs in the
running Cleanuparr version. Sensitive update fields should use Cleanuparr's
placeholder value to preserve an existing secret. Do not place real API keys,
passwords, or notification tokens in prompts.

## Development

```bash
make sync
make test
make test-integration   # requires CLEANUPARR_URL and optionally CLEANUPARR_API_KEY
make build
```

The offline tests use `httpx.MockTransport`; integration tests are skipped by
default.
