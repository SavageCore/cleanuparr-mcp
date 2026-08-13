"""Offline contract tests for the Cleanuparr MCP tools."""

import inspect
import json

import httpx
import pytest
import pytest_asyncio
from fastmcp import Client
from fastmcp.exceptions import ToolError

import cleanuparr_mcp


class Recorder:
    def __init__(self):
        self.method = None
        self.url = None
        self.headers = None
        self.json = None
        self.response = httpx.Response(200, json={"ok": True})

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.method = request.method
        self.url = request.url
        self.headers = request.headers
        self.json = json.loads(request.content) if request.content else None
        return self.response


@pytest.fixture
def recorder():
    return Recorder()


@pytest_asyncio.fixture
async def server(recorder, monkeypatch):
    client = cleanuparr_mcp.build_client(
        "https://cleanuparr.example.com", "test-key",
        transport=httpx.MockTransport(recorder.handler),
    )
    monkeypatch.setattr(cleanuparr_mcp, "_client", client)
    yield cleanuparr_mcp.mcp
    await client.aclose()


_OP_GROUP = {op: group for group, ops in cleanuparr_mcp._GROUPS.items() for op in ops}


async def call(server, name, **kwargs):
    """Call `name` (an operation name) through the portmanteau group tool
    that now hosts it, so every existing per-operation test keeps working
    unmodified aside from this helper."""
    async with Client(server) as client:
        return await client.call_tool(_OP_GROUP[name], {"operation": name, "arguments": kwargs})


@pytest.mark.parametrize(
    ("name", "kwargs", "method", "path"),
    [
        ("cleanuparr_health", {}, "GET", "/api/health"),
        ("cleanuparr_health_ready", {}, "GET", "/api/health/ready"),
        ("cleanuparr_get_status", {}, "GET", "/api/Status"),
        ("cleanuparr_get_arr_status", {}, "GET", "/api/Status/arrs"),
        ("cleanuparr_list_jobs", {}, "GET", "/api/Jobs"),
        ("cleanuparr_get_job", {"job_type": "QueueCleaner"}, "GET", "/api/Jobs/QueueCleaner"),
        ("cleanuparr_trigger_job", {"job_type": "QueueCleaner"}, "POST", "/api/Jobs/QueueCleaner/trigger"),
        ("cleanuparr_list_event_types", {}, "GET", "/api/Events/types"),
        ("cleanuparr_get_event", {"event_id": "abc"}, "GET", "/api/Events/abc"),
        ("cleanuparr_list_manual_events", {"page": 2}, "GET", "/api/ManualEvents"),
        ("cleanuparr_resolve_all_manual_events", {}, "POST", "/api/ManualEvents/resolve_all"),
        ("cleanuparr_list_strikes", {"strike_type": "Stalled"}, "GET", "/api/Strikes"),
        ("cleanuparr_delete_strikes", {"download_item_id": "abc"}, "DELETE", "/api/Strikes/abc"),
        ("cleanuparr_get_stats", {"hours": 24}, "GET", "/api/v2/stats"),
        ("cleanuparr_get_search_summary", {}, "GET", "/api/seeker/search-stats/summary"),
        ("cleanuparr_list_cf_scores", {}, "GET", "/api/seeker/cf-scores"),
        ("cleanuparr_get_general_config", {}, "GET", "/api/configuration/general"),
        ("cleanuparr_purge_strikes", {}, "POST", "/api/configuration/strikes/purge"),
        ("cleanuparr_get_arr_config", {"arr_type": "radarr"}, "GET", "/api/configuration/radarr"),
        ("cleanuparr_list_download_clients", {}, "GET", "/api/configuration/download_client"),
        ("cleanuparr_get_queue_cleaner_config", {}, "GET", "/api/configuration/queue_cleaner"),
        ("cleanuparr_list_queue_rules", {"kind": "stall"}, "GET", "/api/queue-rules/stall"),
        ("cleanuparr_get_download_cleaner_config", {}, "GET", "/api/configuration/download_cleaner"),
        ("cleanuparr_get_dead_torrent_config", {"download_client_id": "client id"}, "GET", "/api/dead-torrent-config/client%20id"),
        ("cleanuparr_list_seeding_rules", {"download_client_id": "client"}, "GET", "/api/seeding-rules/client"),
        ("cleanuparr_get_malware_blocker_config", {}, "GET", "/api/configuration/malware_blocker"),
        ("cleanuparr_get_seeker_config", {}, "GET", "/api/configuration/seeker"),
        ("cleanuparr_get_blacklist_sync_config", {}, "GET", "/api/configuration/blacklist_sync"),
        ("cleanuparr_list_notification_providers", {}, "GET", "/api/configuration/notification_providers"),
        ("cleanuparr_get_apprise_cli_status", {}, "GET", "/api/configuration/notification_providers/apprise/cli-status"),
    ],
)
async def test_endpoint_routes(server, recorder, name, kwargs, method, path):
    await call(server, name, **kwargs)
    assert recorder.method == method
    assert recorder.url.raw_path.split(b"?")[0].decode() == path


@pytest.mark.parametrize(
    ("name", "kwargs", "method", "path", "body"),
    [
        ("cleanuparr_start_job", {"job_type": "QueueCleaner", "schedule": {"cron": "x"}}, "POST", "/api/Jobs/QueueCleaner/start", {"schedule": {"cron": "x"}}),
        ("cleanuparr_create_download_client", {"client": {"name": "qbit"}}, "POST", "/api/configuration/download_client", {"name": "qbit"}),
        ("cleanuparr_update_queue_cleaner_config", {"config": {"enabled": False}}, "PUT", "/api/configuration/queue_cleaner", {"enabled": False}),
        ("cleanuparr_update_dead_torrent_config", {"download_client_id": "x", "config": {"enabled": True}}, "PUT", "/api/dead-torrent-config/x", {"enabled": True}),
        ("cleanuparr_reorder_seeding_rules", {"download_client_id": "x", "ordered_ids": ["a"]}, "PUT", "/api/seeding-rules/x/reorder", {"orderedIds": ["a"]}),
        ("cleanuparr_create_notification_provider", {"provider_type": "discord", "provider": {"name": "alerts"}}, "POST", "/api/configuration/notification_providers/discord", {"name": "alerts"}),
    ],
)
async def test_request_bodies(server, recorder, name, kwargs, method, path, body):
    await call(server, name, **kwargs)
    assert recorder.method == method
    assert recorder.url.path == path
    assert recorder.json == body


async def test_query_parameters(server, recorder):
    await call(server, "cleanuparr_list_events", page=2, page_size=10, severity="Warning")
    assert recorder.url.params["page"] == "2"
    assert recorder.url.params["pageSize"] == "10"
    assert recorder.url.params["severity"] == "Warning"


async def test_update_general_config_merges_not_replaces(server, recorder):
    """A raw PUT /configuration/general resets unspecified fields to defaults
    (that's how displaySupportBanner/auth got clobbered in production). The
    tool must do a read-modify-write: GET current, deep-merge the caller's
    fields, PUT the full config."""
    current = {
        "dryRun": True,
        "displaySupportBanner": False,
        "auth": {
            "disableAuthForLocalAddresses": True,
            "trustForwardedHeaders": True,
        },
    }
    recorder.response = httpx.Response(200, json=current)
    await call(server, "cleanuparr_update_general_config", config={"dryRun": False})
    assert recorder.method == "PUT"
    assert recorder.url.path == "/api/configuration/general"
    assert recorder.json == {
        "dryRun": False,
        "displaySupportBanner": False,
        "auth": {
            "disableAuthForLocalAddresses": True,
            "trustForwardedHeaders": True,
        },
    }


async def test_api_key_header(server, recorder):
    await call(server, "cleanuparr_health")
    assert recorder.headers["x-api-key"] == "test-key"


async def test_no_api_key_header(recorder, monkeypatch):
    client = cleanuparr_mcp.build_client(
        "https://cleanuparr.example.com", None,
        transport=httpx.MockTransport(recorder.handler),
    )
    monkeypatch.setattr(cleanuparr_mcp, "_client", client)
    await call(cleanuparr_mcp.mcp, "cleanuparr_health")
    assert "x-api-key" not in recorder.headers
    await client.aclose()


async def test_list_returning_tools(server, recorder):
    recorder.response = httpx.Response(200, json=[{"id": "a"}, {"id": "b"}])
    result = await call(server, "cleanuparr_list_seeding_rules", download_client_id="client")
    assert result.structured_content == {"result": [{"id": "a"}, {"id": "b"}]}
    assert result.data is not None


async def test_error_message(server, recorder):
    recorder.response = httpx.Response(503, json={"message": "Database is busy"})
    with pytest.raises(ToolError, match="503.*Database is busy"):
        await call(server, "cleanuparr_get_status")


async def test_non_json_error(server, recorder):
    recorder.response = httpx.Response(502, text="<html>Bad Gateway</html>")
    with pytest.raises(ToolError, match="502"):
        await call(server, "cleanuparr_get_status")


def test_main_requires_url(monkeypatch):
    monkeypatch.delenv("CLEANUPARR_URL", raising=False)
    with pytest.raises(SystemExit):
        cleanuparr_mcp.main()


# --- full-surface smoke coverage ------------------------------------------------
#
# Only 38/84 tools had a precise request-shape assertion above (see AGENTS.md
# history). Rather than guess at DTO shapes for the other 46 by hand, this
# exercises every tool's actual URL-templating/body-marshaling code path via
# introspection: real execution coverage without asserting values this repo
# can't independently verify against Cleanuparr's DTOs. This is the baseline
# that must stay green across the portmanteau consolidation.

ALL_TOOL_NAMES = sorted(
    n
    for n in dir(cleanuparr_mcp)
    if n.startswith("cleanuparr_") and inspect.iscoroutinefunction(getattr(cleanuparr_mcp, n))
)


def _sample_value(param: inspect.Parameter):
    ann = str(param.annotation)
    if "dict" in ann:
        return {}
    if "list" in ann:
        return []
    if "bool" in ann:
        return True
    if "int" in ann:
        return 1
    return "x"


@pytest.mark.parametrize("name", ALL_TOOL_NAMES)
async def test_every_tool_is_callable(server, recorder, name):
    fn = getattr(cleanuparr_mcp, name)
    kwargs = {
        p.name: _sample_value(p)
        for p in inspect.signature(fn).parameters.values()
        if p.default is inspect.Parameter.empty
    }
    await call(server, name, **kwargs)
    assert recorder.method in ("GET", "POST", "PUT", "DELETE", "PATCH")
    assert recorder.url.path.startswith("/")


# --- portmanteau grouping safety net --------------------------------------------

def test_all_tools_grouped():
    """Every tool function must land in exactly one portmanteau group - this
    is the safety net for the group-tool consolidation."""
    grouped_names = [n for names in cleanuparr_mcp._GROUPS.values() for n in names]
    assert sorted(grouped_names) == sorted(ALL_TOOL_NAMES)
    assert len(grouped_names) == len(set(grouped_names))


async def test_group_tools_are_the_only_registered_tools(server):
    async with Client(server) as c:
        tools = await c.list_tools()
    assert {t.name for t in tools} == set(cleanuparr_mcp._GROUPS)


async def test_unknown_operation_rejected_by_schema(server):
    # The Literal[...] enum on `operation` means an invalid value never
    # reaches _register_group's dispatch body - pydantic rejects it first.
    with pytest.raises(ToolError, match="validation error"):
        async with Client(server) as c:
            await c.call_tool("cleanuparr_jobs", {"operation": "not_a_real_operation"})
