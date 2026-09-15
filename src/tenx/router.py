"""Dynamic Model Capability Router for Tenx subagent dispatch.

Routes tasks to frontier coding/reasoning models via local Bifrost AI Gateway
(http://localhost:8080) and Agent Anti-Gravity (google-antigravity), with resilient
failover to Bifrost free-tier and native harness defaults.

Zero runtime dependencies (Python standard library urllib.request + json).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List, Optional, Tuple

DEFAULT_GATEWAY_URL = "http://localhost:8080"

# Frontier model tiers ranked by coding and reasoning capabilities
TIER_1_REASONING_MODELS = [
    "google-antigravity/claude-opus-4-6-thinking",
    "google-antigravity/claude-sonnet-4-6",
    "google-antigravity/gemini-3.1-pro-high",
    "google-antigravity/gemini-2.5-pro",
    "Cline/google/gemini-2.5-pro",
]

TIER_2_IMPLEMENTATION_MODELS = [
    "google-antigravity/gemini-3.8-flash-high",
    "google-antigravity/gemini-3.7-flash",
    "google-antigravity/gemini-3.6-flash-medium",
    "google-antigravity/gemini-2.5-flash",
    "Cline/google/gemini-2.5-flash",
    "Cline/cohere/north-mini-code:free",
]


@dataclass(frozen=True)
class ModelRoute:
    model: str
    tier: int
    provider: str
    is_live: bool
    source: str  # "bifrost", "env", "explicit", "fallback"
    notes: str


def fetch_bifrost_live_models(gateway_url: str = DEFAULT_GATEWAY_URL, timeout_secs: float = 1.0) -> List[str]:
    """Fetch live available model identifiers from Bifrost AI Gateway."""
    url = f"{gateway_url.rstrip('/')}/v1/models"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "tenx-model-router/1.0", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_secs) as resp:
            if resp.status != 200:
                return []
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("data", [])
            return [m.get("id") for m in models if isinstance(m, dict) and "id" in m]
    except Exception:
        return []


def resolve_model_route(
    requested_model: Optional[str] = None,
    tier: int = 2,
    gateway_url: str = DEFAULT_GATEWAY_URL,
    allow_gateway: bool = True,
) -> ModelRoute:
    """Resolve the optimal model route based on requested tier and Bifrost availability.

    Hierarchy:
    1. Explicit requested model (if provided).
    2. Frontier benchmarked models from Bifrost AI Gateway / Agent Anti-Gravity.
    3. Resilient failover models (Bifrost free tier).
    4. Harness default fallback.
    """
    # 1. Explicit model request
    if requested_model and requested_model.strip():
        req_clean = requested_model.strip()
        provider = req_clean.split("/")[0] if "/" in req_clean else "native"
        return ModelRoute(
            model=req_clean,
            tier=tier,
            provider=provider,
            is_live=True,
            source="explicit",
            notes=f"Explicitly specified model: {req_clean}"
        )

    # 2. Check environment override
    env_model = os.environ.get("TENX_DISPATCH_MODEL")
    if env_model and env_model.strip():
        req_clean = env_model.strip()
        provider = req_clean.split("/")[0] if "/" in req_clean else "native"
        return ModelRoute(
            model=req_clean,
            tier=tier,
            provider=provider,
            is_live=True,
            source="env",
            notes=f"Environment variable override: {req_clean}"
        )

    # 3. Query Bifrost gateway if allowed
    live_models: List[str] = []
    if allow_gateway:
        live_models = fetch_bifrost_live_models(gateway_url)

    candidates = TIER_1_REASONING_MODELS if tier == 1 else TIER_2_IMPLEMENTATION_MODELS

    if live_models:
        for candidate in candidates:
            if candidate in live_models:
                provider = candidate.split("/")[0]
                return ModelRoute(
                    model=candidate,
                    tier=tier,
                    provider=provider,
                    is_live=True,
                    source="bifrost",
                    notes=f"Frontier Tier {tier} model via Bifrost ({provider})"
                )

        # Fallback to any matching antigravity model if preferred candidates didn't match
        antigravity_live = [m for m in live_models if m.startswith("google-antigravity/")]
        if antigravity_live:
            selected = antigravity_live[0]
            return ModelRoute(
                model=selected,
                tier=tier,
                provider="google-antigravity",
                is_live=True,
                source="bifrost",
                notes=f"Available Agent Anti-Gravity fallback: {selected}"
            )

    # 4. Standard default fallback if Bifrost is offline or returns no models
    default_model = "google-antigravity/gemini-3.8-flash-high" if tier == 2 else "google-antigravity/claude-sonnet-4-6"
    return ModelRoute(
        model=default_model,
        tier=tier,
        provider="google-antigravity",
        is_live=False,
        source="fallback",
        notes="Offline fallback selection"
    )
