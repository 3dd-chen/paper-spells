import json
import logging
from starlette.types import ASGIApp, Scope, Receive, Send

logger = logging.getLogger("paper_spells.middleware.logging")

# Keys whose values must never reach the logs (credentials, JWTs, API keys).
_SENSITIVE_KEYS = {
    "password", "new_password", "old_password", "token", "access_token",
    "refresh_token", "id_token", "authorization", "secret", "api_key",
    "jwt", "private_key",
}
_REDACTED = "<redacted>"


def _redact(value):
    """Recursively replace sensitive values in parsed JSON before logging."""
    if isinstance(value, dict):
        return {
            k: (_REDACTED if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _raw_looks_sensitive(text: str) -> bool:
    lowered = text.lower()
    return any(k in lowered for k in _SENSITIVE_KEYS)

class LoggingASGIMiddleware:
    """ASGI Middleware to log requests and responses and block vulnerability scanners."""
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]

        # Block common vulnerability scanners (/.env, /.git, /wp-admin, etc.)
        path_lower = path.lower()
        scanner_keywords = {
            ".env", ".git", "wp-admin", "wordpress", "phpmyadmin",
            "xmlrpc", "cgi-bin", "config.php", "setup.php", "backup"
        }
        if any(kw in path_lower for kw in scanner_keywords):
            logger.warning(f"Blocked scanner request: {method} {path}")
            await send({
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                ]
            })
            await send({
                "type": "http.response.body",
                "body": b'{"detail":"Access denied"}'
            })
            return

        query = scope["query_string"].decode("utf-8")
        query_str = f"?{query}" if query else ""

        # 1. Capture request body safely
        body_chunks = []
        async def receive_wrapper():
            message = await receive()
            if message["type"] == "http.request":
                body_chunks.append(message.get("body", b""))
            return message

        # 2. Capture response body safely
        response_chunks = []
        status_code = [200]
        content_type = [""]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code[0] = message["status"]
                for name, val in message.get("headers", []):
                    if name.lower() == b"content-type":
                        content_type[0] = val.decode("utf-8")
                        break
            elif message["type"] == "http.response.body":
                response_chunks.append(message.get("body", b""))
            await send(message)

        # Call next ASGI handler
        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        except Exception as e:
            logger.error(f"Request failed: {method} {path}{query_str}: {e}")
            raise e

        # 3. Log request and response post-execution
        request_body = b"".join(body_chunks)
        response_body = b"".join(response_chunks)

        body_summary = ""
        if request_body:
            try:
                body_json = json.loads(request_body.decode("utf-8"))
                if isinstance(body_json, dict):
                    logged_body = _redact(body_json)
                    if "image_data" in logged_body:
                        img_len = len(str(logged_body["image_data"]))
                        logged_body["image_data"] = f"<Base64 Image: {img_len} chars>"
                    body_summary = f" body={json.dumps(logged_body)}"
                else:
                    body_summary = f" body={json.dumps(_redact(body_json))}"
            except Exception:
                raw = request_body.decode("utf-8", errors="ignore")
                if len(request_body) > 1000 or _raw_looks_sensitive(raw):
                    body_summary = f" body=<{len(request_body)} bytes>"
                else:
                    body_summary = f" body={raw}"

        logger.info(f"--> {method} {path}{query_str}{body_summary}")

        resp_summary = ""
        if response_body and ("application/json" in content_type[0] or "text/" in content_type[0]):
            try:
                resp_json = json.loads(response_body.decode("utf-8"))
                resp_summary = f" body={json.dumps(_redact(resp_json))}"
            except Exception:
                raw_resp = response_body.decode("utf-8", errors="ignore")
                if len(response_body) < 500 and not _raw_looks_sensitive(raw_resp):
                    resp_summary = f" body={raw_resp}"
                else:
                    resp_summary = f" body=<{len(response_body)} bytes>"
        else:
            resp_summary = f" content_type={content_type[0]}"

        logger.info(f"<-- {status_code[0]} {method} {path} {resp_summary}")
