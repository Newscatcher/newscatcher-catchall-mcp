import gzip
import zlib
import contextvars
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_http_request

# API configuration
API_BASE_URL = "https://catchall.newscatcherapi.com"

# Context variable to store the API key for the current request
current_api_key: contextvars.ContextVar[str] = contextvars.ContextVar("current_api_key", default="")


class ApiKeyMiddleware(Middleware):
    """Middleware to extract API key from query parameters before each tool call."""

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Extract API key from HTTP request query params before tool execution."""
        try:
            request = get_http_request()
            api_key = request.query_params.get("apiKey", "")
            if api_key:
                current_api_key.set(api_key)
        except Exception:
            pass
        return await call_next(context)


def decode_response_content(response: httpx.Response) -> str:
    """Safely decode response content, handling compression if needed."""
    content = response.content

    # Try to decompress if it looks like compressed data
    if content and len(content) > 2:
        # Check for gzip magic bytes (1f 8b)
        if content[:2] == b'\x1f\x8b':
            try:
                content = gzip.decompress(content)
            except Exception:
                pass
        # Check for zlib/deflate
        elif content[0] == 0x78:
            try:
                content = zlib.decompress(content)
            except Exception:
                pass

    # Decode to string
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        # If UTF-8 fails, try latin-1 which accepts any byte
        try:
            return content.decode('latin-1')
        except Exception:
            return f"[Binary response: {len(content)} bytes]"


def extract_error_message(response: httpx.Response) -> str:
    """Extract a clear error message from an HTTP error response."""
    text = decode_response_content(response)

    # Try to parse as JSON for structured error messages
    try:
        import json
        data = json.loads(text)
        if isinstance(data, dict):
            # Common error response formats
            if "detail" in data:
                return str(data["detail"])
            if "error" in data:
                return str(data["error"])
            if "message" in data:
                return str(data["message"])
        return text
    except (json.JSONDecodeError, ValueError):
        return text if text else f"HTTP {response.status_code}"


async def make_api_request(
    method: str,
    path: str,
    json_data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an API request with proper error handling."""
    api_key = current_api_key.get("")
    if not api_key:
        raise ValueError("API key not provided. Include it in the MCP URL as ?apiKey=YOUR_KEY")

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=60.0) as client:
        response = await client.request(
            method=method,
            url=path,
            headers=headers,
            json=json_data,
            params=params,
        )

        if response.status_code >= 400:
            error_msg = extract_error_message(response)
            raise ValueError(f"API Error ({response.status_code}): {error_msg}")

        # Decode successful response
        text = decode_response_content(response)
        try:
            import json
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return {"result": text}


# Create the MCP server
mcp = FastMCP(name="Newscatcher CatchAll API")

# Add middleware to extract API key from query parameters
mcp.add_middleware(ApiKeyMiddleware())


@mcp.tool()
async def submit_url(
    url: str,
    webhook_url: str | None = None,
    extraction_type: str = "article",
) -> dict[str, Any]:
    """
    Submit a URL for content extraction.

    Args:
        url: The URL to extract content from
        webhook_url: Optional webhook URL to receive results
        extraction_type: Type of extraction (article, html, text). Default: article

    Returns:
        Job ID and status information
    """
    data = {"url": url, "extraction_type": extraction_type}
    if webhook_url:
        data["webhook"] = {"url": webhook_url}

    return await make_api_request("POST", "/catchAll/submit", json_data=data)


@mcp.tool()
async def get_job_status(job_id: str) -> dict[str, Any]:
    """
    Get the status of a submitted job.

    Args:
        job_id: The job ID returned from submit_url

    Returns:
        Job status information
    """
    return await make_api_request("GET", f"/catchAll/status/{job_id}")


@mcp.tool()
async def pull_job_results(job_id: str) -> dict[str, Any]:
    """
    Pull the results of a completed job.

    Args:
        job_id: The job ID returned from submit_url

    Returns:
        Extracted content from the URL
    """
    return await make_api_request("GET", f"/catchAll/pull/{job_id}")


@mcp.tool()
async def list_user_jobs(
    status: str | None = None,
    limit: int = 10,
    offset: int = 0,
) -> dict[str, Any]:
    """
    List jobs submitted by the user.

    Args:
        status: Filter by status (pending, processing, completed, failed)
        limit: Maximum number of jobs to return (default: 10)
        offset: Number of jobs to skip (default: 0)

    Returns:
        List of user jobs
    """
    params = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status

    return await make_api_request("GET", "/catchAll/jobs/user", params=params)


@mcp.tool()
async def continue_job(job_id: str) -> dict[str, Any]:
    """
    Continue a job that has more results to fetch (pagination).

    Args:
        job_id: The job ID to continue

    Returns:
        Next page of results
    """
    return await make_api_request("POST", "/catchAll/continue", json_data={"job_id": job_id})


@mcp.tool()
async def create_monitor(
    url: str,
    name: str | None = None,
    schedule: str = "daily",
) -> dict[str, Any]:
    """
    Create a monitor to periodically extract content from a URL.

    Args:
        url: The URL to monitor
        name: Optional name for the monitor
        schedule: Monitoring schedule (hourly, daily, weekly). Default: daily

    Returns:
        Monitor ID and configuration
    """
    data = {"url": url, "schedule": schedule}
    if name:
        data["name"] = name

    return await make_api_request("POST", "/catchAll/monitors/create", json_data=data)


@mcp.tool()
async def list_monitors() -> dict[str, Any]:
    """
    List all monitors for the user.

    Returns:
        List of monitors
    """
    return await make_api_request("GET", "/catchAll/monitors/")


@mcp.tool()
async def get_monitor_jobs(monitor_id: str) -> dict[str, Any]:
    """
    Get jobs created by a specific monitor.

    Args:
        monitor_id: The monitor ID

    Returns:
        List of jobs for the monitor
    """
    return await make_api_request("GET", f"/catchAll/monitors/{monitor_id}/jobs")


@mcp.tool()
async def pull_monitor_results(monitor_id: str) -> dict[str, Any]:
    """
    Pull the latest results from a monitor.

    Args:
        monitor_id: The monitor ID

    Returns:
        Latest extracted content
    """
    return await make_api_request("GET", f"/catchAll/monitors/pull/{monitor_id}")


@mcp.tool()
async def enable_monitor(monitor_id: str) -> dict[str, Any]:
    """
    Enable a disabled monitor.

    Args:
        monitor_id: The monitor ID to enable

    Returns:
        Updated monitor status
    """
    return await make_api_request("POST", f"/catchAll/monitors/{monitor_id}/enable")


@mcp.tool()
async def disable_monitor(monitor_id: str) -> dict[str, Any]:
    """
    Disable an active monitor.

    Args:
        monitor_id: The monitor ID to disable

    Returns:
        Updated monitor status
    """
    return await make_api_request("POST", f"/catchAll/monitors/{monitor_id}/disable")


@mcp.tool()
async def update_monitor(
    monitor_id: str,
    name: str | None = None,
    schedule: str | None = None,
) -> dict[str, Any]:
    """
    Update a monitor's configuration.

    Args:
        monitor_id: The monitor ID to update
        name: New name for the monitor
        schedule: New schedule (hourly, daily, weekly)

    Returns:
        Updated monitor configuration
    """
    data = {}
    if name:
        data["name"] = name
    if schedule:
        data["schedule"] = schedule

    if not data:
        raise ValueError("At least one of 'name' or 'schedule' must be provided")

    return await make_api_request("PATCH", f"/catchAll/monitors/{monitor_id}", json_data=data)


if __name__ == "__main__":
    mcp.run()
