import json
import base64
import time
import logging

from app.core.config import Settings
from app.interfaces.http_client import HttpClientInterface

logger = logging.getLogger(__name__)

try:
    from js import crypto, Uint8Array
    from pyodide.ffi import to_js
except ImportError:
    pass

def _b64url_encode(data: bytes) -> str:
    """Base64Url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

async def get_access_token(settings: Settings, http_client: HttpClientInterface, token_store: dict = None) -> str:
    now = int(time.time())
    
    if token_store and token_store.get("token") and now < token_store.get("expiry", 0) - 60:
        return token_store["token"]

    creds_json_str = settings.gcp_service_account
    if not creds_json_str:
        try:
            with open("gcp-credentials.json", "r") as f:
                creds_json_str = f.read()
        except Exception as e:
            pass
            
    if not creds_json_str:
        logger.error("GCP_SERVICE_ACCOUNT is empty")
        raise ValueError("GCP_SERVICE_ACCOUNT is empty")
        
    creds = json.loads(creds_json_str)
    private_key_pem = creds["private_key"]
    client_email = creds["client_email"]
    
    header = {
        "alg": "RS256",
        "typ": "JWT"
    }
    
    payload = {
        "iss": client_email,
        "scope": "https://www.googleapis.com/auth/cloud-platform",
        "aud": "https://oauth2.googleapis.com/token",
        "exp": now + 3600,
        "iat": now
    }
    
    header_b64 = _b64url_encode(json.dumps(header).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}"
    
    pem_body = private_key_pem.replace("-----BEGIN PRIVATE KEY-----", "")\
                              .replace("-----END PRIVATE KEY-----", "")\
                              .replace("\n", "")\
                              .replace("\r", "")
    
    der_bytes = base64.b64decode(pem_body)
    der_js_array = Uint8Array.new(to_js(der_bytes))
    
    algorithm = {"name": "RSASSA-PKCS1-v1_5", "hash": {"name": "SHA-256"}}
    
    try:
        from js import JSON
        algo_js = JSON.parse(json.dumps(algorithm))
        
        crypto_key = await crypto.subtle.importKey(
            "pkcs8",
            der_js_array,
            algo_js,
            False,
            to_js(["sign"])
        )
    except Exception as e:
        logger.error(f"Failed to import private key via Web Crypto: {e}")
        raise
    
    signing_input_bytes = signing_input.encode("utf-8")
    signing_input_js_array = Uint8Array.new(to_js(signing_input_bytes))
    
    try:
        signature_buffer = await crypto.subtle.sign(
            "RSASSA-PKCS1-v1_5",
            crypto_key,
            signing_input_js_array
        )
    except Exception as e:
        logger.error(f"Failed to sign JWT: {e}")
        raise
    
    signature_js_array = Uint8Array.new(signature_buffer)
    signature_bytes = bytes(signature_js_array)
    
    signature_b64 = _b64url_encode(signature_bytes)
    jwt_token = f"{signing_input}.{signature_b64}"
    
    token_url = "https://oauth2.googleapis.com/token"
    
    headers = {
        "Content-Type": "application/json"
    }
    payload_body = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token
    }
    
    res_json = await http_client.post_json(token_url, headers, payload_body)
    
    if "access_token" not in res_json:
        logger.error(f"Unexpected token response: {res_json}")
        raise Exception(f"Unexpected token response: {res_json}")
        
    access_token = res_json["access_token"]
    if token_store is not None:
        token_store["token"] = access_token
        token_store["expiry"] = now + int(res_json.get("expires_in", 3600))
        
    logger.info("Successfully fetched new Google Cloud OAuth 2.0 access token via Web Crypto API")
    return access_token