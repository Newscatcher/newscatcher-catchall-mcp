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
                    "description": auth_field.get("description", "Basic auth credentials [username, password]"),
                }

        # Fix url field - simplify anyOf to simple string with uri format
        if "url" in properties:
            url_field = properties["url"]
            if "anyOf" in url_field:
                properties["url"] = {
                    "type": "string",
                    "format": "uri",
                    "title": url_field.get("title", "Url"),
                    "description": url_field.get("description", "The URL where the request will be sent"),
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

if __name__ == "__main__":
    mcp.run()
