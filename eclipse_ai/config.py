from __future__ import annotations
from typing import Any, Dict, Iterable, Tuple
import os, json

try:
    import yaml  # optional
except Exception:
    yaml = None

def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def _load_one(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    # Try YAML first if available, else JSON
    if yaml is not None:
        try:
            d = yaml.safe_load(text)
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    try:
        d = json.loads(text)
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return {}

def load_configs(paths: Iterable[str] | None) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    for p in (paths or []):
        cfg = _deep_merge(cfg, _load_one(p))
    return cfg

def env_overrides(prefix: str = "ECLIPSE_AI__") -> Dict[str, Any]:
    # Nested via double underscores: ECLIPSE_AI__PLANNER__SIMS=512
    out: Dict[str, Any] = {}
    for k, v in os.environ.items():
        if not k.startswith(prefix):
            continue
        parts = k[len(prefix):].split("__")
        cur = out
        for i, part in enumerate(parts):
            key = part.lower()
            if i == len(parts) - 1:
                # try int/float/bool
                val = _coerce(v)
                cur[key] = val
            else:
                cur = cur.setdefault(key, {})
    return out

def _coerce(s: str) -> Any:
    t = s.strip().lower()
    if t in ("true", "false"):
        return t == "true"
    try:
        if "." in t:
            return float(t)
        return int(t)
    except Exception:
        return s

def apply_cli_overrides(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    return _deep_merge(base, overrides or {})

__all__ = ["load_configs", "env_overrides", "apply_cli_overrides", "_deep_merge"]
