# AGENTS.md — cleanuparr-mcp

MCP server exposing Cleanuparr's REST API as tools for inspecting status, history, statistics, jobs, and configuration. Uses FastMCP, `uv` for deps.

Exposed as **8 resource-scoped portmanteau tools**, not one tool per endpoint — see "Portmanteau registration" below. A prior version registered all 84 endpoints individually; that blew the MCP context budget (~84 tools × ~250 tokens ≈ 21k tokens just for this one server) and has been retired.

## Testing
- Offline suite: `make test` (or `uv run pytest`)
- Live integration (needs `CLEANUPARR_URL`/`CLEANUPARR_API_KEY`): `make test-integration`
- `tests/test_tools.py` has two layers: ~40 hand-written assertions on exact request shape (method/path/body/query) for a subset of operations, plus `test_every_tool_is_callable` — a generic, introspection-driven smoke test that calls every operation with type-appropriate dummy args and confirms it makes *some* well-formed HTTP request. The smoke test exists because only ~38/84 endpoints had ever been individually verified; rather than guess at Cleanuparr's DTO shapes for the rest, it gives real execution coverage of the URL-templating/body-marshaling code paths without asserting values this repo can't independently verify.

## Release workflow
Always use the `make bump-*` targets to bump the version (`uv version --bump patch|minor|major`), which updates `pyproject.toml` and `uv.lock` together. Do NOT edit the version by hand.

- Bump: `make bump-patch` (or `bump-minor` / `bump-major`)
- Commit message is **just the version**, e.g. `0.1.2` — nothing else.
- Tag it `v<version>` (e.g. `v0.1.2`).
- Push main and the tag:
  ```
  git push origin main
  git push origin v<version>
  ```
- Then sync the project copy:
  ```
  cd /home/savagecore/Documents/christopfarr/mcp/cleanuparr-mcp
  git fetch origin && git reset --hard origin/main
  ```
- Deploy to the Proxmox host (root SSH key): pull the repo then reinstall the uv tool:
  ```
  ssh root@192.168.50.3 -- 'cd /root/cleanuparr-mcp && git fetch origin && git reset --hard origin/main'
  ssh root@192.168.50.3 -- 'cd /root/cleanuparr-mcp && uv tool install --force .'
  ```
  The host runs it via `uv tool install` → `/root/.local/bin/cleanuparr-mcp` (not from the repo).

## Env note
All tools go through Cleanuparr's REST API keyed on `CLEANUPARR_API_KEY`. Keep API keys out of code, logs, and commit messages. Request bodies intentionally remain plain JSON dictionaries so this server follows Cleanuparr's versioned DTOs without duplicating validation. For updates, Cleanuparr accepts its placeholder secret value to preserve an existing secret — **do not expose real secrets in chat**, and preserve this rule in any grouped config tool's docs.

`cleanuparr_update_general_config` is a deliberate exception to the plain-PUT rule: it does a read-modify-write (GET current config → `_deep_merge` the caller's fields → PUT the full config). Cleanuparr's `/configuration/general` PUT replaces the whole resource, so a raw PUT with a partial body (e.g. only `{"dryRun": false}`) resets every unspecified field — including `displaySupportBanner` and the whole `auth` object — to defaults. Do not revert it to a plain PUT. The other config updates (arr configs, queue/seeding rules, download clients) stay as plain PUTs because their resources are fully replaced intentionally.

## Portmanteau registration — **do not go back to one tool per endpoint**
- `_GROUPS` near the bottom of `cleanuparr_mcp.py` buckets every endpoint function into one of 8 resource groups (`cleanuparr_events`, `cleanuparr_cleaner_config`, `cleanuparr_arr_download_clients`, ...). `_register_tools()` registers exactly one MCP tool per group via `_register_group`, which wraps the group's functions in a single `dispatch(operation, arguments)` closure. The endpoint functions themselves are unchanged — they're plain callables looked up by name via `globals()`, not separately-registered tools.
- `operation` is typed `Literal[<the group's function names>]`, so FastMCP/pydantic validates it against the real operation list before `dispatch` ever runs — an invalid operation never reaches the group tool's body.
- Adding a new endpoint: write the function as before (no decorator), then add its name to exactly one group in `_GROUPS`. `tests/test_tools.py::test_all_tools_grouped` fails if you forget (it checks against `ALL_TOOL_NAMES`, the same introspected list the smoke test uses).
- New resource area big enough to need its own group (rare): add a new `_GROUPS` key. The ceiling that matters is *total groups* (~15), not operations per group — `cleanuparr_cleaner_config` alone carries 19 operations in one tool, which is fine.
- If you're tempted to add a per-endpoint `@mcp.tool` decorator back, don't — every endpoint must be reachable only via its group's `operation` enum. An 84-tool server (one per endpoint) previously cost ~21k tokens of system-prompt budget on every session start; the 8-tool grouped version costs roughly a tenth of that.
- Annotations: a group tool is `readOnlyHint=True` (`READONLY`) only when *every* operation in it was originally read-only (tracked in `_register_tools()`'s `readonly_names` set). Mixed groups carry no hints.