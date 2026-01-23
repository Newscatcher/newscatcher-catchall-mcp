"""
MCP Server for Newscatcher CatchAll API

This server provides tools to interact with the Newscatcher CatchAll API.
Users can provide their API key via:
1. The api_key parameter in each tool call
2. The NEWSCATCHER_API_KEY environment variable
"""

import json
import os
from typing import Any

import httpx
from fastmcp import FastMCP

# API Configuration
API_BASE_URL = "https://catchall.newscatcherapi.com"

# Create the FastMCP server
mcp = FastMCP(
    "Newscatcher CatchAll API",
    instructions="""This server allows you to search for news articles using natural language queries via the Newscatcher CatchAll API.

IMPORTANT: You need a Newscatcher API key to use these tools. Get one at https://www.newscatcherapi.com/

The API key can be provided in two ways:
1. Pass it directly in the api_key parameter (takes precedence)
2. Set the NEWSCATCHER_API_KEY environment variable

Workflow:
1. Use submit_query to submit your news search query
2. Use get_job_status to check if processing is complete
3. Use pull_results to retrieve the clustered news articles""",
)


def get_api_key(api_key: str = "") -> str:
    """Get API key from parameter or environment variable."""
    key = api_key or os.environ.get("NEWSCATCHER_API_KEY", "")
    if not key:
        raise ValueError(
            "API key is required. Either pass it as the api_key parameter "
            "or set the NEWSCATCHER_API_KEY environment variable."
        )
    return key


async def make_api_request(
    api_key: str,
    method: str,
    path: str,
    json_data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an API request to Newscatcher CatchAll API."""
    key = get_api_key(api_key)

    headers = {
        "x-api-key": key,
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
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    if "detail" in error_data:
                        detail = error_data["detail"]
                        if isinstance(detail, dict) and "detail" in detail:
                            error_msg = detail["detail"]
                        else:
                            error_msg = str(detail)
                    else:
                        error_msg = json.dumps(error_data)
                else:
                    error_msg = str(error_data)
            except Exception:
                error_msg = response.text or f"HTTP {response.status_code}"

            raise ValueError(f"API Error ({response.status_code}): {error_msg}")

        return response.json()


@mcp.tool()
async def submit_query(query: str, api_key: str = "") -> str:
    """
    Submit a natural language query to search for news articles.

    The system will fetch, validate, cluster, and summarize relevant articles.
    Returns a job_id that you'll use to check status and retrieve results.

    Args:
        query: Natural language query to search for news (e.g., 'Find all M&A deals in tech sector last 7 days')
        api_key: Your Newscatcher API key. Optional if NEWSCATCHER_API_KEY env var is set.

    Returns:
        JSON with job_id to use for checking status and getting results
    """
    try:
        result = await make_api_request(
            api_key=api_key,
            method="POST",
            path="/catchAll/submit",
            json_data={"query": query},
        )
        return json.dumps(result, indent=2)
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


@mcp.tool()
async def get_job_status(job_id: str, api_key: str = "") -> str:
    """
    Check the status of a submitted job.

    Call this after submit_query to see if your job is ready.
    Status progression: submitted -> analyzing -> fetching -> clustering -> enriching -> completed

    Args:
        job_id: The job ID returned from submit_query
        api_key: Your Newscatcher API key. Optional if NEWSCATCHER_API_KEY env var is set.

    Returns:
        JSON with current job status and progress information
    """
    try:
        result = await make_api_request(
            api_key=api_key,
            method="GET",
            path=f"/catchAll/status/{job_id}",
        )
        return json.dumps(result, indent=2)
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


@mcp.tool()
async def pull_results(job_id: str, api_key: str = "", page: int = 1, page_size: int = 100) -> str:
    """
    Retrieve the results of a completed job.

    Only call this after get_job_status shows the job is complete.
    Returns clustered and summarized news articles.

    Args:
        job_id: The job ID returned from submit_query
        api_key: Your Newscatcher API key. Optional if NEWSCATCHER_API_KEY env var is set.
        page: Page number for pagination (default: 1)
        page_size: Number of results per page (default: 100, max: 100)

    Returns:
        JSON with clustered news articles, summaries, and metadata
    """
    try:
        result = await make_api_request(
            api_key=api_key,
            method="GET",
            path=f"/catchAll/pull/{job_id}",
            params={"page": page, "page_size": page_size},
        )
        return json.dumps(result, indent=2)
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


@mcp.tool()
async def list_user_jobs(api_key: str = "") -> str:
    """
    List all jobs submitted by you.

    Returns your job history with IDs, queries, statuses, and timestamps.

    Args:
        api_key: Your Newscatcher API key. Optional if NEWSCATCHER_API_KEY env var is set.

    Returns:
        JSON with list of your submitted jobs
    """
    try:
        result = await make_api_request(
            api_key=api_key,
            method="GET",
            path="/catchAll/jobs/user",
        )
        return json.dumps(result, indent=2)
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


@mcp.tool()
async def continue_job(job_id: str, api_key: str = "") -> str:
    """
    Continue processing a job that needs more data.

    Use this when a job requires additional article fetching.

    Args:
        job_id: The job ID to continue processing
        api_key: Your Newscatcher API key. Optional if NEWSCATCHER_API_KEY env var is set.

    Returns:
        JSON confirming the job continuation
    """
    try:
        result = await make_api_request(
            api_key=api_key,
            method="POST",
            path="/catchAll/continue",
            json_data={"job_id": job_id},
        )
        return json.dumps(result, indent=2)
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


if __name__ == "__main__":
    mcp.run()
