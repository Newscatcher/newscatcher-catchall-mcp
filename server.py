import os
import httpx
from fastmcp import FastMCP

# API configuration
API_BASE_URL = "https://catchall.newscatcherapi.com"
OPENAPI_SPEC_URL = f"{API_BASE_URL}/openapi.json"

# Get API key from environment variable
API_KEY = os.environ.get("NEWSCATCHER_API_KEY", "")

# Create an HTTP client with authentication
client = httpx.AsyncClient(
    base_url=API_BASE_URL,
    headers={"x-api-key": API_KEY},
    timeout=60.0,
)

# Load the OpenAPI specification
openapi_spec = httpx.get(OPENAPI_SPEC_URL).json()

# Create the MCP server from OpenAPI spec
mcp = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=client,
    name="Newscatcher CatchAll API",
)

if __name__ == "__main__":
    mcp.run()
