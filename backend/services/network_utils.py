import logging
import json
import subprocess
import shutil
import time
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Find bash for curl fallback — Git bash's curl has the TLS features
# needed to pass CDN fingerprint checks (brotli, zstd, libpsl)
_BASH_PATH = shutil.which("bash") or "bash"

# Cache domains where requests fails — skip straight to curl for 5 minutes
_domain_fail_cache: dict[str, float] = {}
_DOMAIN_FAIL_TTL = 300  # 5 minutes

# Per-domain rate-limit cooldown: domain -> unix time when it's OK to hit again.
# Populated when a host returns 429 (or sends Retry-After). Callers should check
# is_host_paused() before issuing a request to avoid re-hammering a throttled host.
_domain_pause: dict[str, float] = {}
_429_DEFAULT_PAUSE = 30  # seconds; used when the server sends no Retry-After


def is_host_paused(url: str) -> bool:
    """Return True if a host is currently rate-limiting us and should be skipped."""
    domain = urlparse(url).netloc
    until = _domain_pause.get(domain)
    if until and time.time() < until:
        return True
    if until:
        # Pause expired — clean up
        _domain_pause.pop(domain, None)
    return False


def _pause_host(url: str, response):
    """Record a rate-limit pause based on a 429 / Retry-After response."""
    domain = urlparse(url).netloc
    retry_after = response.headers.get("Retry-After") if getattr(response, "headers", None) else None
    try:
        pause = int(retry_after) if retry_after else _429_DEFAULT_PAUSE
    except (ValueError, TypeError):
        pause = _429_DEFAULT_PAUSE
    _domain_pause[domain] = time.time() + pause
    logger.warning(f"Host {domain} rate-limited (429) — pausing for {pause}s")

class _DummyResponse:
    """Minimal response object matching requests.Response interface."""
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text
        self.content = text.encode('utf-8', errors='replace')
        # curl fallback doesn't capture response headers; Retry-After is parsed
        # only for the requests-based path. Keeping an empty dict keeps callers safe.
        self.headers = {}

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}: {self.text[:100]}")


def fetch_with_curl(url, method="GET", json_data=None, timeout=15, headers=None):
    """Wrapper to bypass aggressive local firewall that blocks Python but permits curl.

    Falls back to running curl through Git bash, which has the TLS features
    (brotli, zstd, libpsl) needed to pass CDN fingerprint checks that block
    both Python requests and the barebones Windows system curl.
    """
    default_headers = {
        "User-Agent": "ShadowBroker-OSINT/1.0 (live-risk-dashboard)",
    }
    if headers:
        default_headers.update(headers)

    domain = urlparse(url).netloc

    # Check if this domain recently failed with requests — skip straight to curl
    _use_requests = True
    if domain in _domain_fail_cache and (time.time() - _domain_fail_cache[domain]) < _DOMAIN_FAIL_TTL:
        _use_requests = False

    if _use_requests:
        try:
            import requests
            if method == "POST":
                res = requests.post(url, json=json_data, timeout=timeout, headers=default_headers)
            else:
                res = requests.get(url, timeout=timeout, headers=default_headers)
            if res.status_code == 429:
                _pause_host(url, res)
            res.raise_for_status()
            # Clear failure cache on success
            _domain_fail_cache.pop(domain, None)
            return res
        except Exception as e:
            logger.warning(f"Python requests failed for {url} ({e}), falling back to bash curl...")
            _domain_fail_cache[domain] = time.time()

    # Build curl command string for bash execution
    header_flags = " ".join(f'-H "{k}: {v}"' for k, v in default_headers.items())
    if method == "POST" and json_data:
        payload = json.dumps(json_data).replace('"', '\\"')
        curl_cmd = f'curl -s -w "\\n%{{http_code}}" {header_flags} -X POST -H "Content-Type: application/json" -d "{payload}" "{url}"'
    else:
        curl_cmd = f'curl -s -w "\\n%{{http_code}}" {header_flags} "{url}"'

    try:
        res = subprocess.run(
            [_BASH_PATH, "-c", curl_cmd],
            capture_output=True, text=True, timeout=timeout + 5
        )
        if res.returncode == 0 and res.stdout.strip():
            # Parse HTTP status code from -w output (last line)
            lines = res.stdout.rstrip().rsplit("\n", 1)
            body = lines[0] if len(lines) > 1 else res.stdout
            http_code = int(lines[-1]) if len(lines) > 1 and lines[-1].strip().isdigit() else 200
            resp = _DummyResponse(http_code, body)
            if http_code == 429:
                _pause_host(url, resp)
            return resp
        else:
            logger.error(f"bash curl fallback failed: exit={res.returncode} stderr={res.stderr[:200]}")
            return _DummyResponse(500, "")
    except Exception as curl_e:
        logger.error(f"bash curl fallback exception: {curl_e}")
        return _DummyResponse(500, "")
