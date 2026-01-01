"""
Swagger UI route handler for apflow API documentation

Provides interactive API documentation using Swagger UI (CDN-hosted).
"""

from typing import Dict, Any
from starlette.responses import HTMLResponse, JSONResponse


def get_swagger_ui_html(
    openapi_url: str = "/openapi.json",
    title: str = "apflow API Documentation",
    swagger_js_url: str = "https://unpkg.com/swagger-ui-dist@5.17.14/swagger-ui-bundle.js",
    swagger_css_url: str = "https://unpkg.com/swagger-ui-dist@5.17.14/swagger-ui.css",
) -> str:
    """
    Generate Swagger UI HTML page
    
    Args:
        openapi_url: URL to OpenAPI schema JSON
        title: Page title
        swagger_js_url: Swagger UI JavaScript bundle URL (CDN)
        swagger_css_url: Swagger UI CSS URL (CDN)
        
    Returns:
        HTML string for Swagger UI
    """
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" type="text/css" href="{swagger_css_url}" />
    <style>
        html {{
            box-sizing: border-box;
            overflow: -moz-scrollbars-vertical;
            overflow-y: scroll;
        }}
        *, *:before, *:after {{
            box-sizing: inherit;
        }}
        body {{
            margin: 0;
            background: #fafafa;
        }}
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="{swagger_js_url}"></script>
    <script>
        window.onload = function() {{
            window.ui = SwaggerUIBundle({{
                url: "{openapi_url}",
                dom_id: "#swagger-ui",
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.presets.standalone
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                tryItOutEnabled: true,
                requestInterceptor: function(request) {{
                    // Add any custom request interceptors here
                    return request;
                }},
                responseInterceptor: function(response) {{
                    // Add any custom response interceptors here
                    return response;
                }}
            }});
        }};
    </script>
</body>
</html>
"""
    return html


def get_swagger_ui_route_handler(openapi_schema: Dict[str, Any]) -> HTMLResponse:
    """
    Create route handler for Swagger UI
    
    Args:
        openapi_schema: OpenAPI schema dictionary
        
    Returns:
        HTMLResponse with Swagger UI page
    """
    html = get_swagger_ui_html()
    return HTMLResponse(content=html)


def get_openapi_json_route_handler(openapi_schema: Dict[str, Any]) -> JSONResponse:
    """
    Create route handler for OpenAPI JSON schema
    
    Args:
        openapi_schema: OpenAPI schema dictionary
        
    Returns:
        JSONResponse with OpenAPI schema
    """
    return JSONResponse(content=openapi_schema)

