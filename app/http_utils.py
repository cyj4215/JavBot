import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def build_retry_session(proxy_addr: str = "") -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    if proxy_addr:
        session.proxies.update({"http": proxy_addr, "https": proxy_addr})
    return session
