"""Simple disk cache for expensive RPC results in notebooks."""

import hashlib
import json
from pathlib import Path


CACHE_DIR = Path("data")


def _cache_key(name: str, params: dict) -> str:
    """Generate a deterministic filename from name + params."""
    param_str = json.dumps(params, sort_keys=True, default=str)
    h = hashlib.md5(param_str.encode()).hexdigest()[:8]
    return f"{name}_{h}.json"


def load_cache(name: str, params: dict | None = None) -> list | dict | None:
    """Load cached result if it exists and params match. Returns None on miss."""
    if params is None:
        params = {}
    path = CACHE_DIR / _cache_key(name, params)
    if not path.exists():
        return None
    with open(path) as f:
        cached = json.load(f)
    # Verify params match
    if cached.get("_params") != params:
        return None
    print(f"  Cache hit: {path.name}")
    return cached["data"]


def save_cache(name: str, data: list | dict, params: dict | None = None) -> None:
    """Save result to disk cache."""
    if params is None:
        params = {}
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / _cache_key(name, params)
    with open(path, "w") as f:
        json.dump({"_params": params, "data": data}, f)
    print(f"  Cached: {path.name}")
