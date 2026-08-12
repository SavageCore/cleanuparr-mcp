# cleanuparr-mcp

Part of the [arr-mcps](https://github.com/SavageCore/arr-mcps) collection.
An MCP server exposing [Cleanuparr](https://github.com/Cleanuparr/Cleanuparr)'s
REST API as tools for inspecting status, history, statistics, jobs, and
configuration.

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

**8 resource-scoped tools**, each covering multiple Cleanuparr REST endpoints
(84 total) via an `operation` parameter. Call a tool with `operation` set to
one of its listed operations and an `arguments` dict matching that
operation's parameters — the tool's own description (visible to your MCP
client) lists every operation, its signature, and a one-line doc. This keeps
the full API surface available while costing a fraction of the context
budget of registering all 84 endpoints as separate tools.

| Tool | Operations | Covers |
|---|---|---|
| `cleanuparr_cleaner_config` | 19 | Queue/download cleaners, dead torrents, orphaned/unlinked files, seeding rules |
| `cleanuparr_events` | 18 | Events, manual events, strikes, timelines, stats |
| `cleanuparr_arr_download_clients` | 15 | General config, *arr instances, download clients |
| `cleanuparr_health_status` | 8 | Health, readiness, system/*arr/download-client status |
| `cleanuparr_stats` | 7 | Seeker search events, custom-format scores |
| `cleanuparr_notifications` | 6 | Notification providers |
| `cleanuparr_feature_configs` | 6 | Malware blocker, Seeker, blacklist sync |
| `cleanuparr_jobs` | 5 | List, inspect, trigger, start, schedule jobs |

Example: `cleanuparr_jobs(operation="cleanuparr_trigger_job", arguments={"job_type": "QueueCleaner"})`.
Endpoint-level naming (`cleanuparr_<verb>_<resource>`) is preserved as the
`operation` value, so the full endpoint list is still discoverable from each
group tool's description at runtime.

Destructive operations are noted in their operation-line doc. Cleanuparr
returns `503` when its configuration database is busy; this server does not
retry and instead returns the upstream error to the MCP client.

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
