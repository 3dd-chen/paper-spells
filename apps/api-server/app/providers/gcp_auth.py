import json
import base64
import time
import os
import asyncio
import logging

logger = logging.getLogger(__name__)

# Cloudflare Workers / Pyodide imports
try:
    from js import fetch, crypto, Uint8Array
    from pyodide.ffi import to_js
except ImportError:
    # Fallback for local testing (mock or standard python)
    pass

# Global cache for the token
_cached_token = None
_token_expiry = 0

def _b64url_encode(data: bytes) -> str:
    """Base64Url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

async def get_access_token(env=None) -> str:
    """
    Generate or retrieve a cached Google Cloud OAuth 2.0 access token using Web Crypto API.
    Reads credentials from env.GCP_SERVICE_ACCOUNT (JSON string) or gcp-credentials.json.
    """
    global _cached_token, _token_expiry
    
    now = int(time.time())
    if _cached_token and now < _token_expiry - 60:
        return _cached_token

    # 1. Load service account credentials
    creds_json_str = None
    if env and hasattr(env, "GCP_SERVICE_ACCOUNT"):
        creds_json_str = env.GCP_SERVICE_ACCOUNT
    else:
        try:
            with open("gcp-credentials.json", "r") as f:
                creds_json_str = f.read()
        except Exception as e:
            logger.error(f"Could not load GCP credentials: {e}")
            raise ValueError(f"Could not load GCP credentials: {e}")
            
    if not creds_json_str:
        logger.error("GCP_SERVICE_ACCOUNT is empty")
        raise ValueError("GCP_SERVICE_ACCOUNT is empty")
        
    creds = json.loads(creds_json_str)
    private_key_pem = creds["private_key"]
    client_email = creds["client_email"]
    
    # 2. Build JWT Header and Payload
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
    
    # 3. Parse private key (PEM to DER)
    pem_body = private_key_pem.replace("-----BEGIN PRIVATE KEY-----", "")\
                              .replace("-----END PRIVATE KEY-----", "")\
                              .replace("\n", "")\
                              .replace("\r", "")
    
    der_bytes = base64.b64decode(pem_body)
    
    # Convert Python bytes to JavaScript Uint8Array
    der_js_array = Uint8Array.new(to_js(der_bytes))
    
    # 4. Import the key via Web Crypto API
    # Using python dicts. Pyodide usually proxies them well to JS Web APIs, 
    # but we can wrap in to_js just in case for complex nested structures.
    # Actually, importKey requires an object, to_js creates a Map by default sometimes,
    # but let's pass a native Python dict and let Pyodide's implicit conversion handle it.
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
    
    # 5. Sign the payload
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
    
    # Convert ArrayBuffer signature back to Python bytes
    signature_js_array = Uint8Array.new(signature_buffer)
    signature_bytes = bytes(signature_js_array)
    
    # 6. Complete JWT
    signature_b64 = _b64url_encode(signature_bytes)
    jwt_token = f"{signing_input}.{signature_b64}"
    
    # 7. Exchange JWT for Access Token
    token_url = "https://oauth2.googleapis.com/token"
    body_data = f"grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion={jwt_token}"
    
    from js import JSON
    options = JSON.parse(json.dumps({
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded"
        },
        "body": body_data
    }))
    
    response = await fetch(token_url, options)
    
    if response.status != 200:
        err_text = await response.text()
        logger.error(f"Failed to fetch access token: {response.status} {err_text}")
        raise Exception(f"Failed to fetch access token: {response.status} {err_text}")
        
    res_js = await response.json()
    res_json = res_js.to_py() if hasattr(res_js, "to_py") else res_js
    
    if "access_token" not in res_json:
        logger.error(f"Unexpected token response: {res_json}")
        raise Exception(f"Unexpected token response: {res_json}")
        
    _cached_token = res_json["access_token"]
    _token_expiry = now + int(res_json.get("expires_in", 3600))
    logger.info("Successfully fetched new Google Cloud OAuth 2.0 access token via Web Crypto API")
    return _cached_token
