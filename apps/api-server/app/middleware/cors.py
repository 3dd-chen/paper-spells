from starlette.types import ASGIApp, Scope, Receive, Send

class DynamicCORSMiddleware:
    """Dynamic CORS middleware to handle preflights and CORS headers using ALLOWED_ORIGINS settings from env."""
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {h[0].lower(): h[1] for h in scope.get("headers", [])}
        origin_bytes = headers.get(b"origin", b"")
        origin = origin_bytes.decode("utf-8") if origin_bytes else ""
        method = scope.get("method", "GET")

        # Load allowed origins dynamically from the Worker environment
        env = scope.get("env", None)
        origins_raw = getattr(env, "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:4173,https://gallery.hissnake.com,https://upload.hissnake.com")
        allowed_origins = [o.strip() for o in origins_raw.split(",") if o.strip()]

        is_allowed = False
        if origin:
            is_allowed = origin in allowed_origins or origin.startswith("http://localhost:")

        if method == "OPTIONS" and b"access-control-request-method" in headers:
            # Handle Preflight
            response_headers = [
                (b"content-type", b"text/plain"),
                (b"access-control-allow-methods", b"GET, POST, PUT, PATCH, DELETE, OPTIONS"),
                (b"access-control-allow-headers", b"*"),
                (b"access-control-max-age", b"86400"),
            ]
            if is_allowed:
                response_headers.append((b"access-control-allow-origin", origin.encode("utf-8")))
                response_headers.append((b"access-control-allow-credentials", b"true"))
            
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": response_headers
            })
            await send({
                "type": "http.response.body",
                "body": b""
            })
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start" and is_allowed:
                resp_headers = list(message.get("headers", []))
                # Append CORS headers if not already added
                has_origin = any(h[0].lower() == b"access-control-allow-origin" for h in resp_headers)
                if not has_origin:
                    resp_headers.append((b"access-control-allow-origin", origin.encode("utf-8")))
                    resp_headers.append((b"access-control-allow-credentials", b"true"))
                message["headers"] = resp_headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
