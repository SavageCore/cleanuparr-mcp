"""MCP tools for the Cleanuparr REST API.

Cleanuparr uses an API key in ``X-Api-Key``. Request bodies intentionally remain
plain JSON dictionaries so this server follows Cleanuparr's versioned DTOs
without duplicating validation. For updates, Cleanuparr accepts its placeholder
secret value to preserve an existing secret; do not expose real secrets in chat.
"""

import os
import sys
from typing import Any
from urllib.parse import quote

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

JSONObj = dict[str, Any]
JSONVal = JSONObj | list[Any]
READONLY = ToolAnnotations(readOnlyHint=True)
DESTRUCTIVE = ToolAnnotations(destructiveHint=True)

mcp = FastMCP("cleanuparr-mcp")
_client: httpx.AsyncClient | None = None


def build_client(
    base_url: str,
    api_key: str | None,
    transport: httpx.BaseTransport | None = None,
) -> httpx.AsyncClient:
    headers = {"X-Api-Key": api_key} if api_key else {}
    return httpx.AsyncClient(
        base_url=f"{base_url.rstrip('/')}/api", headers=headers, transport=transport
    )


def _path(value: str) -> str:
    return quote(value, safe="")


async def _req(
    method: str,
    path: str,
    json: Any = None,
    params: dict[str, Any] | None = None,
) -> JSONVal:
    assert _client is not None, "client not configured"
    response = await _client.request(method, path, json=json, params=params)
    if response.status_code >= 400:
        try:
            body = response.json()
            message = body.get("message", body) if isinstance(body, dict) else body
        except ValueError:
            message = response.text
        raise ToolError(f"Cleanuparr API {response.status_code}: {message}")
    if not response.content:
        return {}
    return response.json()


def _params(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


# Health and status -----------------------------------------------------------

@mcp.tool(annotations=READONLY)
async def cleanuparr_health() -> JSONObj:
    """Check anonymous liveness at /health."""
    return await _req("GET", "/health")


@mcp.tool(annotations=READONLY)
async def cleanuparr_health_ready() -> JSONObj:
    """Check anonymous readiness at /health/ready."""
    return await _req("GET", "/health/ready")


@mcp.tool(annotations=READONLY)
async def cleanuparr_health_detailed() -> JSONObj:
    """Get the authenticated detailed health report."""
    return await _req("GET", "/health/detailed")


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_status() -> JSONObj:
    """Get Cleanuparr version, uptime, resource, and instance status."""
    return await _req("GET", "/Status")


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_download_client_status() -> JSONObj:
    """Check all configured download-client connections."""
    return await _req("GET", "/Status/download-client")


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_arr_status() -> JSONObj:
    """Check all configured Sonarr/Radarr/Lidarr-style connections."""
    return await _req("GET", "/Status/arrs")


@mcp.tool(annotations=READONLY)
async def cleanuparr_health_checks() -> JSONObj:
    """List configured health checks."""
    return await _req("GET", "/health")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_run_health_check(check_id: str | None = None) -> JSONObj:
    """Run all health checks, or one check by GUID when check_id is supplied."""
    path = "/health/check" if check_id is None else f"/health/check/{_path(check_id)}"
    return await _req("POST", path)


# Jobs ------------------------------------------------------------------------

@mcp.tool(annotations=READONLY)
async def cleanuparr_list_jobs() -> JSONObj:
    """List scheduled jobs and their current status."""
    return await _req("GET", "/Jobs")


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_job(job_type: str) -> JSONObj:
    """Get one job. Values include QueueCleaner, MalwareBlocker, DownloadCleaner,
    BlacklistSynchronizer, Seeker, and CustomFormatScoreSyncer."""
    return await _req("GET", f"/Jobs/{_path(job_type)}")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_trigger_job(job_type: str) -> JSONObj:
    """Run a one-time job now. Seeker cannot be manually triggered."""
    return await _req("POST", f"/Jobs/{_path(job_type)}/trigger")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_start_job(job_type: str, schedule: dict) -> JSONObj:
    """Start a job with a schedule object containing the JobSchedule DTO."""
    return await _req("POST", f"/Jobs/{_path(job_type)}/start", {"schedule": schedule})


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_job_schedule(job_type: str, schedule: dict) -> JSONObj:
    """Replace a job schedule using the JobSchedule DTO."""
    return await _req("PUT", f"/Jobs/{_path(job_type)}/schedule", {"schedule": schedule})


# Events, manual events, strikes, and stats ----------------------------------

@mcp.tool(annotations=READONLY)
async def cleanuparr_list_events(
    page: int = 1, page_size: int = 50, severity: str | None = None,
    event_type: str | None = None, from_date: str | None = None,
    to_date: str | None = None, search: str | None = None,
    job_run_id: str | None = None,
) -> JSONObj:
    """List events. Dates are ISO-8601 strings; page_size is capped by the API at 500."""
    return await _req("GET", "/Events", params=_params(
        page=page, pageSize=page_size, severity=severity, eventType=event_type,
        fromDate=from_date, toDate=to_date, search=search, jobRunId=job_run_id,
    ))


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_event(event_id: str) -> JSONObj:
    """Get one event by GUID."""
    return await _req("GET", f"/Events/{_path(event_id)}")


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_events_by_tracking(tracking_id: str) -> JSONObj:
    """Get events associated with a tracking GUID."""
    return await _req("GET", f"/Events/tracking/{_path(tracking_id)}")


@mcp.tool(annotations=READONLY)
async def cleanuparr_list_event_types() -> JSONObj:
    """List event type enum values."""
    return await _req("GET", "/Events/types")


@mcp.tool(annotations=READONLY)
async def cleanuparr_list_event_severities() -> JSONObj:
    """List event severity enum values."""
    return await _req("GET", "/Events/severities")


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_event_timeline(hours: int = 720) -> JSONObj:
    """Get event timeline buckets for the requested number of hours."""
    return await _req("GET", "/Events/timeline", params={"hours": hours})


@mcp.tool(annotations=READONLY)
async def cleanuparr_list_manual_events(
    page: int = 1, page_size: int = 50, is_resolved: bool | None = None,
    severity: str | None = None, from_date: str | None = None,
    to_date: str | None = None, search: str | None = None,
) -> JSONObj:
    """List manual events with pagination and optional filters."""
    return await _req("GET", "/ManualEvents", params=_params(
        page=page, pageSize=page_size, isResolved=is_resolved, severity=severity,
        fromDate=from_date, toDate=to_date, search=search,
    ))


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_manual_event(event_id: str) -> JSONObj:
    """Get one manual event by GUID."""
    return await _req("GET", f"/ManualEvents/{_path(event_id)}")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_resolve_manual_event(event_id: str) -> JSONObj:
    """Mark one manual event resolved."""
    return await _req("POST", f"/ManualEvents/{_path(event_id)}/resolve")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_resolve_all_manual_events() -> JSONObj:
    """Mark all unresolved manual events resolved."""
    return await _req("POST", "/ManualEvents/resolve_all")


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_manual_event_stats() -> JSONObj:
    """Get manual-event counts by severity and resolution."""
    return await _req("GET", "/ManualEvents/stats")


@mcp.tool(annotations=READONLY)
async def cleanuparr_list_manual_event_severities() -> JSONObj:
    """List manual-event severity enum values."""
    return await _req("GET", "/ManualEvents/severities")


@mcp.tool(annotations=READONLY)
async def cleanuparr_list_strikes(
    page: int = 1, page_size: int = 50, search: str | None = None,
    strike_type: str | None = None,
) -> JSONObj:
    """List strike-bearing download items."""
    return await _req("GET", "/Strikes", params=_params(
        page=page, pageSize=page_size, search=search, type=strike_type,
    ))


@mcp.tool(annotations=READONLY)
async def cleanuparr_list_recent_strikes(count: int = 5) -> JSONObj:
    """List recent strikes; count is capped by the API at 50."""
    return await _req("GET", "/Strikes/recent", params={"count": count})


@mcp.tool(annotations=READONLY)
async def cleanuparr_list_strike_types() -> JSONObj:
    """List strike type enum values."""
    return await _req("GET", "/Strikes/types")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_delete_strikes(download_item_id: str) -> JSONObj:
    """Delete all strikes for a download-item GUID."""
    return await _req("DELETE", f"/Strikes/{_path(download_item_id)}")


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_stats(hours: int = 168, include_dry_run: bool = False) -> JSONObj:
    """Get v2 aggregate statistics. The deprecated v1 stats endpoint is not exposed."""
    return await _req("GET", "/v2/stats", params={"hours": hours, "includeDryRun": include_dry_run})


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_stats_timeline(
    metric: str = "events", hours: int = 720, bucket: str | None = None,
    include_dry_run: bool = False,
) -> JSONObj:
    """Get v2 metric timeline. Metrics include events, strikesIssued, recovered,
    removed, and malwareBlocked; buckets include hour, day, week, and month."""
    return await _req("GET", "/v2/stats/timeline", params=_params(
        metric=metric, hours=hours, bucket=bucket, includeDryRun=include_dry_run,
    ))


# Seeker and custom-format score reporting ----------------------------------

@mcp.tool(annotations=READONLY)
async def cleanuparr_get_search_summary() -> JSONObj:
    """Get Seeker search totals and per-instance summary."""
    return await _req("GET", "/seeker/search-stats/summary")


@mcp.tool(annotations=READONLY)
async def cleanuparr_list_search_events(
    page: int = 1, page_size: int = 50, instance_id: str | None = None,
    cycle_id: str | None = None, search: str | None = None,
    sort_by: str = "Timestamp", sort_direction: str = "Desc",
    search_status: list[str] | None = None, search_type: str | None = None,
    search_reason: str | None = None, grabbed: bool | None = None,
) -> JSONObj:
    """List Seeker search events. search_status can contain repeated enum filters."""
    params = _params(page=page, pageSize=page_size, instanceId=instance_id,
                     cycleId=cycle_id, search=search, sortBy=sort_by,
                     sortDirection=sort_direction, searchType=search_type,
                     searchReason=search_reason, grabbed=grabbed)
    if search_status:
        params["searchStatus"] = search_status
    return await _req("GET", "/seeker/search-stats/events", params=params)


@mcp.tool(annotations=READONLY)
async def cleanuparr_list_cf_scores(
    page: int = 1, page_size: int = 50, instance_id: str | None = None,
    search: str | None = None, sort_by: str = "Title",
    sort_direction: str | None = None, quality_profile: str | None = None,
    item_type: str | None = None, cutoff_filter: str = "All",
    monitored_filter: str = "All",
) -> JSONObj:
    """List current custom-format scores with cutoff and monitored filters."""
    return await _req("GET", "/seeker/cf-scores", params=_params(
        page=page, pageSize=page_size, instanceId=instance_id, search=search,
        sortBy=sort_by, sortDirection=sort_direction, qualityProfile=quality_profile,
        itemType=item_type, cutoffFilter=cutoff_filter, monitoredFilter=monitored_filter,
    ))


@mcp.tool(annotations=READONLY)
async def cleanuparr_list_cf_upgrades(
    page: int = 1, page_size: int = 50, instance_id: str | None = None,
    days: int = 30, search: str | None = None, sort_by: str = "UpgradedAt",
    sort_direction: str | None = None,
) -> JSONObj:
    """List recent custom-format score upgrades."""
    return await _req("GET", "/seeker/cf-scores/upgrades", params=_params(
        page=page, pageSize=page_size, instanceId=instance_id, days=days,
        search=search, sortBy=sort_by, sortDirection=sort_direction,
    ))


@mcp.tool(annotations=READONLY)
async def cleanuparr_list_cf_instances() -> JSONObj:
    """List instances and quality profiles with tracked scores."""
    return await _req("GET", "/seeker/cf-scores/instances")


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_cf_stats() -> JSONObj:
    """Get custom-format score tracking statistics."""
    return await _req("GET", "/seeker/cf-scores/stats")


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_cf_item_history(instance_id: str, item_id: int, episode_id: int = 0) -> JSONObj:
    """Get score history for an item; episode_id is used for Sonarr episode history."""
    return await _req("GET", f"/seeker/cf-scores/{_path(instance_id)}/{item_id}/history",
                      params={"episodeId": episode_id})


# Configuration ---------------------------------------------------------------

ARR_TYPES = "sonarr, radarr, lidarr, readarr, whisparr"
PROVIDERS = "notifiarr, apprise, ntfy, telegram, discord, pushover, gotify"


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_general_config() -> JSONObj:
    """Get general configuration, including dry-run and auth settings."""
    return await _req("GET", "/configuration/general")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_general_config(config: dict) -> JSONObj:
    """Replace general config. Fields include dryRun, retry/timeout settings,
    ignoredDownloads, connectivity, retention, log, and auth objects."""
    return await _req("PUT", "/configuration/general", config)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_purge_strikes() -> JSONObj:
    """Purge all stored strikes. This is irreversible."""
    return await _req("POST", "/configuration/strikes/purge")


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_arr_config(arr_type: str) -> JSONObj:
    """Get one *arr config. arr_type must be one of: """ + ARR_TYPES
    return await _req("GET", f"/configuration/{_path(arr_type)}")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_arr_config(arr_type: str, config: dict) -> JSONObj:
    """Replace one *arr config, normally containing failedImportMaxStrikes."""
    return await _req("PUT", f"/configuration/{_path(arr_type)}", config)


@mcp.tool(annotations=READONLY)
async def cleanuparr_list_arr_instances(arr_type: str) -> JSONObj:
    """List instances for arr_type: """ + ARR_TYPES
    return await _req("GET", f"/configuration/{_path(arr_type)}")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_create_arr_instance(arr_type: str, instance: dict) -> JSONObj:
    """Create an *arr instance. DTO fields: enabled, name, url, apiKey, version, externalUrl."""
    return await _req("POST", f"/configuration/{_path(arr_type)}/instances", instance)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_arr_instance(arr_type: str, instance_id: str, instance: dict) -> JSONObj:
    """Replace an *arr instance. Use Cleanuparr's secret placeholder for apiKey."""
    return await _req("PUT", f"/configuration/{_path(arr_type)}/instances/{_path(instance_id)}", instance)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_delete_arr_instance(arr_type: str, instance_id: str) -> JSONObj:
    """Delete an *arr instance by GUID."""
    return await _req("DELETE", f"/configuration/{_path(arr_type)}/instances/{_path(instance_id)}")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_test_arr_instance(arr_type: str, instance: dict) -> JSONObj:
    """Test an *arr connection. DTO fields: url, apiKey, version, optional instanceId."""
    return await _req("POST", f"/configuration/{_path(arr_type)}/instances/test", instance)


@mcp.tool(annotations=READONLY)
async def cleanuparr_list_download_clients() -> JSONObj:
    """List configured download clients."""
    return await _req("GET", "/configuration/download_client")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_create_download_client(client: dict) -> JSONObj:
    """Create a download client. DTO includes enabled, name, typeName, type,
    host, username, password, urlBase, externalUrl, and directory source/target."""
    return await _req("POST", "/configuration/download_client", client)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_download_client(client_id: str, client: dict) -> JSONObj:
    """Replace a download client. Use the secret placeholder for password."""
    return await _req("PUT", f"/configuration/download_client/{_path(client_id)}", client)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_delete_download_client(client_id: str) -> JSONObj:
    """Delete a download client by GUID."""
    return await _req("DELETE", f"/configuration/download_client/{_path(client_id)}")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_test_download_client(client: dict) -> JSONObj:
    """Test a download client. DTO includes typeName, type, host, credentials,
    urlBase, and optional clientId."""
    return await _req("POST", "/configuration/download_client/test", client)


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_queue_cleaner_config() -> JSONObj:
    """Get queue cleaner configuration."""
    return await _req("GET", "/configuration/queue_cleaner")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_queue_cleaner_config(config: dict) -> JSONObj:
    """Replace queue cleaner config. DTO includes enabled, cronExpression,
    useAdvancedScheduling, failedImport, downloadingMetadataMaxStrikes,
    processNoContentId, and ignoredDownloads."""
    return await _req("PUT", "/configuration/queue_cleaner", config)


async def _queue_rule(method: str, kind: str, rule_id: str | None = None, rule: dict | None = None) -> JSONVal:
    path = f"/queue-rules/{kind}" + (f"/{_path(rule_id)}" if rule_id else "")
    return await _req(method, path, rule)


@mcp.tool(annotations=READONLY)
async def cleanuparr_list_queue_rules(kind: str) -> JSONVal:
    """List stall or slow queue rules."""
    return await _queue_rule("GET", kind)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_create_queue_rule(kind: str, rule: dict) -> JSONObj:
    """Create a stall or slow queue rule. Common DTO fields include name, enabled,
    maxStrikes, privacyType, completion percentages, and changeCategory."""
    return await _queue_rule("POST", kind, rule=rule)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_queue_rule(kind: str, rule_id: str, rule: dict) -> JSONObj:
    """Replace a stall or slow queue rule. Stall fields include minimumProgress;
    slow fields include minSpeed, maxTimeHours, and ignoreAboveSize."""
    return await _queue_rule("PUT", kind, rule_id, rule)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_delete_queue_rule(kind: str, rule_id: str) -> JSONObj:
    """Delete a stall or slow queue rule by GUID."""
    return await _queue_rule("DELETE", kind, rule_id)


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_download_cleaner_config() -> JSONObj:
    """Get download cleaner configuration."""
    return await _req("GET", "/configuration/download_cleaner")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_download_cleaner_config(config: dict) -> JSONObj:
    """Replace download cleaner config: enabled, cronExpression,
    useAdvancedScheduling, and ignoredDownloads."""
    return await _req("PUT", "/configuration/download_cleaner", config)


async def _client_config(path: str, client_id: str, method: str = "GET", config: dict | None = None) -> JSONVal:
    return await _req(method, f"{path}/{_path(client_id)}", config)


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_dead_torrent_config(download_client_id: str) -> JSONObj:
    """Get dead-torrent settings for a download-client GUID."""
    return await _client_config("/dead-torrent-config", download_client_id)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_dead_torrent_config(download_client_id: str, config: dict) -> JSONObj:
    """Replace dead-torrent settings: enabled, targetCategory, useTag, maxStrikes, categories."""
    return await _client_config("/dead-torrent-config", download_client_id, "PUT", config)


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_unlinked_config(download_client_id: str) -> JSONObj:
    """Get unlinked-file settings for a download-client GUID."""
    return await _client_config("/unlinked-config", download_client_id)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_unlinked_config(download_client_id: str, config: dict) -> JSONObj:
    """Replace unlinked settings: enabled, targetCategory, useTag, ignoredRootDirs, categories."""
    return await _client_config("/unlinked-config", download_client_id, "PUT", config)


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_orphaned_files_config(download_client_id: str) -> JSONObj:
    """Get orphaned-file settings for a download-client GUID."""
    return await _client_config("/orphaned-files-config", download_client_id)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_orphaned_files_config(download_client_id: str, config: dict) -> JSONObj:
    """Replace orphaned-file settings: enabled, scanDirectories, orphanedDirectory,
    excludePatterns, minFileAgeHours, and optional purgeAfterHours."""
    return await _client_config("/orphaned-files-config", download_client_id, "PUT", config)


@mcp.tool(annotations=READONLY)
async def cleanuparr_list_seeding_rules(download_client_id: str) -> JSONObj:
    """List seeding rules for a download-client GUID."""
    return await _req("GET", f"/seeding-rules/{_path(download_client_id)}")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_create_seeding_rule(download_client_id: str, rule: dict) -> JSONObj:
    """Create a seeding rule. DTO includes name, categories, trackerPatterns,
    tagsAny/tagsAll, priority, privacyType, ratio/time/seeder limits, and deleteSourceFiles."""
    return await _req("POST", f"/seeding-rules/{_path(download_client_id)}", rule)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_seeding_rule(rule_id: str, rule: dict) -> JSONObj:
    """Replace a seeding rule by GUID. Priority is ignored by the upstream update."""
    return await _req("PUT", f"/seeding-rules/{_path(rule_id)}", rule)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_delete_seeding_rule(rule_id: str) -> JSONObj:
    """Delete a seeding rule by GUID."""
    return await _req("DELETE", f"/seeding-rules/{_path(rule_id)}")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_reorder_seeding_rules(download_client_id: str, ordered_ids: list[str]) -> JSONObj:
    """Reorder rules by sending an orderedIds GUID array."""
    return await _req("PUT", f"/seeding-rules/{_path(download_client_id)}/reorder",
                      {"orderedIds": ordered_ids})


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_malware_blocker_config() -> JSONObj:
    """Get malware blocker configuration."""
    return await _req("GET", "/configuration/malware_blocker")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_malware_blocker_config(config: dict) -> JSONObj:
    """Replace malware blocker config, including per-arr blocklist settings."""
    return await _req("PUT", "/configuration/malware_blocker", config)


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_seeker_config() -> JSONObj:
    """Get Seeker configuration."""
    return await _req("GET", "/configuration/seeker")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_seeker_config(config: dict) -> JSONObj:
    """Replace Seeker config: search toggles, strategy, grace period, and instances."""
    return await _req("PUT", "/configuration/seeker", config)


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_blacklist_sync_config() -> JSONObj:
    """Get blacklist synchronizer configuration."""
    return await _req("GET", "/configuration/blacklist_sync")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_blacklist_sync_config(config: dict) -> JSONObj:
    """Replace blacklist sync config: enabled and optional blacklistPath."""
    return await _req("PUT", "/configuration/blacklist_sync", config)


# Notifications ---------------------------------------------------------------

@mcp.tool(annotations=READONLY)
async def cleanuparr_list_notification_providers() -> JSONObj:
    """List notification providers. Secret fields may be redacted by Cleanuparr."""
    return await _req("GET", "/configuration/notification_providers")


@mcp.tool(annotations=READONLY)
async def cleanuparr_get_apprise_cli_status() -> JSONObj:
    """Get Apprise CLI availability status."""
    return await _req("GET", "/configuration/notification_providers/apprise/cli-status")


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_create_notification_provider(provider_type: str, provider: dict) -> JSONObj:
    """Create a notification provider.

    Types: notifiarr, apprise, ntfy, telegram, discord, pushover, gotify.
    Common fields are name, isEnabled, and event flags; provider-specific fields
    follow the API DTO.
    """
    return await _req("POST", f"/configuration/notification_providers/{_path(provider_type)}", provider)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_update_notification_provider(provider_type: str, provider_id: str, provider: dict) -> JSONObj:
    """Replace a notification provider. Use Cleanuparr placeholders for secrets."""
    return await _req("PUT", f"/configuration/notification_providers/{_path(provider_type)}/{_path(provider_id)}", provider)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_test_notification_provider(provider_type: str, provider: dict) -> JSONObj:
    """Test a notification provider using its provider-specific DTO."""
    return await _req("POST", f"/configuration/notification_providers/{_path(provider_type)}/test", provider)


@mcp.tool(annotations=DESTRUCTIVE)
async def cleanuparr_delete_notification_provider(provider_id: str) -> JSONObj:
    """Delete a notification provider by GUID."""
    return await _req("DELETE", f"/configuration/notification_providers/{_path(provider_id)}")


def main() -> None:
    global _client
    url = os.environ.get("CLEANUPARR_URL")
    if not url:
        print("CLEANUPARR_URL environment variable is required (e.g. https://cleanuparr.example.com)", file=sys.stderr)
        raise SystemExit(1)
    _client = build_client(url, os.environ.get("CLEANUPARR_API_KEY"))
    mcp.run()


if __name__ == "__main__":
    main()
