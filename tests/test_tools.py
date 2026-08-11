"""Offline contract tests for the Cleanuparr MCP tools."""

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


async def call(server, name, **kwargs):
    async with Client(server) as client:
        return await client.call_tool(name, kwargs)


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
        ("cleanuparr_update_general_config", {"config": {"dryRun": True}}, "PUT", "/api/configuration/general", {"dryRun": True}),
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
