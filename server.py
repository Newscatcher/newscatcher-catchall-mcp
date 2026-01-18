import contextvars
import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request

# API configuration
API_BASE_URL = "https://catchall.newscatcherapi.com"
OPENAPI_SPEC_URL = f"{API_BASE_URL}/openapi.json"

# Context variable to store the API key for the current request
current_api_key: contextvars.ContextVar[str] = contextvars.ContextVar("current_api_key", default="")


def get_api_key_from_request() -> str:
    """Extract API key from the current request's query parameters."""
    try:
        request = get_http_request()
        return request.query_params.get("apiKey", "")
    except Exception:
        return current_api_key.get("")


async def inject_api_key(request: httpx.Request) -> httpx.Request:
    """Event hook to inject the API key header into outgoing requests."""
    api_key = current_api_key.get("")
    if api_key:
        request.headers["x-api-key"] = api_key
    return request


# Create an HTTP client with dynamic API key injection
client = httpx.AsyncClient(
    base_url=API_BASE_URL,
    timeout=60.0,
    event_hooks={"request": [inject_api_key]},
)

# Load the OpenAPI specification
openapi_spec = httpx.get(OPENAPI_SPEC_URL).json()


def fix_openapi_spec(spec: dict) -> dict:
    """Fix OpenAPI spec compatibility issues for FastMCP's legacy parser.

    The WebhookDTO schema has issues that the legacy parser can't handle:
    1. Tuple-style 'auth' field using OpenAPI 3.1 prefixItems syntax
    2. 'url' field using anyOf with multiple string types

    This normalizes these fields to simpler types.
    """
    schemas = spec.get("components", {}).get("schemas", {})

    if "WebhookDTO" in schemas:
        webhook_dto = schemas["WebhookDTO"]
        properties = webhook_dto.get("properties", {})

        # Fix auth field - convert tuple-style array to simple string array
        if "auth" in properties:
            auth_field = properties["auth"]
            if isinstance(auth_field.get("items"), list):
                properties["auth"] = {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 2,
                    "title": auth_field.get("title", "Auth"),
                    "description": auth_field.get(
                        "description", "Basic auth credentials [username, password]"
                    ),
                }

        # Fix url field - simplify anyOf to simple string with uri format
        if "url" in properties:
            url_field = properties["url"]
            if "anyOf" in url_field:
                properties["url"] = {
                    "type": "string",
                    "format": "uri",
                    "title": url_field.get("title", "Url"),
                    "description": url_field.get(
                        "description", "The URL where the request will be sent"
                    ),
                }

    return spec


# Fix compatibility issues in the OpenAPI spec
openapi_spec = fix_openapi_spec(openapi_spec)

# Create the MCP server from OpenAPI spec
mcp = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=client,
    name="Newscatcher CatchAll API",
)


@mcp.tool
async def set_api_key() -> str:
    """Initialize the API key from the connection URL query parameter.

    This tool is called automatically when needed. Users should pass their
    CatchAll API key in the connection URL: ?apiKey=YOUR_API_KEY
    """
    api_key = get_api_key_from_request()
    if api_key:
        current_api_key.set(api_key)
        return "API key configured successfully"
    return "No API key found in query parameters. Please add ?apiKey=YOUR_API_KEY to the connection URL."


# Override the tool call to inject API key before each call
original_call_tool = mcp.call_tool


async def call_tool_with_api_key(name: str, arguments: dict):
    """Wrapper to inject API key before each tool call."""
    api_key = get_api_key_from_request()
    if api_key:
        current_api_key.set(api_key)
    return await original_call_tool(name, arguments)


mcp.call_tool = call_tool_with_api_key

if __name__ == "__main__":
    mcp.run()
