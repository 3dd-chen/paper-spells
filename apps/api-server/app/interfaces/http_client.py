from abc import ABC, abstractmethod
import json

class HttpClientInterface(ABC):
    @abstractmethod
    async def post_json(self, url: str, headers: dict, payload: dict) -> dict:
        pass
    
    @abstractmethod
    async def fetch_text(self, url: str, options: dict) -> tuple[int, str]:
        pass

class JsFetchClient(HttpClientInterface):
    async def post_json(self, url: str, headers: dict, payload: dict) -> dict:
        from js import JSON, fetch
        options = JSON.parse(json.dumps({
            "method": "POST",
            "headers": headers,
            "body": json.dumps(payload)
        }))
        response = await fetch(url, options)
        if response.status != 200:
            err_text = await response.text()
            raise Exception(f"HTTP {response.status}: {err_text}")
        res_js = await response.json()
        return res_js.to_py() if hasattr(res_js, "to_py") else res_js

    async def fetch_text(self, url: str, options: dict) -> tuple[int, str]:
        from js import JSON, fetch
        js_options = JSON.parse(json.dumps(options))
        response = await fetch(url, js_options)
        text = await response.text()
        return response.status, text
