"""
MCP Server for Newscatcher CatchAll API

This server provides tools to interact with the Newscatcher CatchAll API.
Users must provide their own API key with each request.
"""

import json
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

Workflow:
1. Use submit_query to submit your news search query
2. Use get_job_status to check if processing is complete
3. Use pull_results to retrieve the clustered news articles

Always pass your api_key with each tool call.""",
)


async def make_api_request(
    api_key: str,
    method: str,
    path: str,
    json_data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an API request to Newscatcher CatchAll API."""
    if not api_key:
        raise ValueError("API key is required. Please provide your Newscatcher API key.")

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
async def submit_query(api_key: str, query: str) -> str:
    """
    Submit a natural language query to search for news articles.

    The system will fetch, validate, cluster, and summarize relevant articles.
    Returns a job_id that you'll use to check status and retrieve results.

    Args:
        api_key: Your Newscatcher API key (get one at https://www.newscatcherapi.com/)
        query: Natural language query to search for news (e.g., 'Find all M&A deals in tech sector last 7 days')

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
async def get_job_status(api_key: str, job_id: str) -> str:
    """
    Check the status of a submitted job.

    Call this after submit_query to see if your job is ready.
    Status progression: submitted -> analyzing -> fetching -> clustering -> enriching -> completed

    Args:
        api_key: Your Newscatcher API key
        job_id: The job ID returned from submit_query

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
async def pull_results(api_key: str, job_id: str, page: int = 1, page_size: int = 100) -> str:
    """
    Retrieve the results of a completed job.

    Only call this after get_job_status shows the job is complete.
    Returns clustered and summarized news articles.

    Args:
        api_key: Your Newscatcher API key
        job_id: The job ID returned from submit_query
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
async def list_user_jobs(api_key: str) -> str:
    """
    List all jobs submitted by you.

    Returns your job history with IDs, queries, statuses, and timestamps.

    Args:
        api_key: Your Newscatcher API key

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
async def continue_job(api_key: str, job_id: str) -> str:
    """
    Continue processing a job that needs more data.

    Use this when a job requires additional article fetching.

    Args:
        api_key: Your Newscatcher API key
        job_id: The job ID to continue processing

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
