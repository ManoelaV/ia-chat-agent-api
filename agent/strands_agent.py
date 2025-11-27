"""Adapter to use Strands Agents SDK if available, with a fallback.

This module exposes `StrandsAgent` which attempts to use the Strands
Agents SDK if it's installed. If the SDK is not available, it falls back to
an internal lightweight agent implementation compatible with the rest of the
project (so the API remains usable).

Note: the Strands Agents SDK API surface may differ; this adapter attempts a
best-effort integration. If you have the official SDK, update this file to
use the correct SDK classes and registration calls.
"""
from typing import Any, Dict, List, Optional
import os
import json
import logging

logger = logging.getLogger(__name__)

import importlib

# Allow selecting the SDK package name via env var `STRANDS_SDK_PACKAGE`.
# If not set, try a list of common candidate package names. If none are
# present, we fall back to the internal `Agent` implementation.
_SDK_CANDIDATES = [
    os.environ.get("STRANDS_SDK_PACKAGE", ""),
    "strands_agents_sdk",
    "strands",
    "strands_agents",
]

sas = None
_HAS_SAS = False
for pkg in _SDK_CANDIDATES:
    if not pkg:
        continue
    try:
        sas = importlib.import_module(pkg)
        _HAS_SAS = True
        logger.info("Imported Strands SDK module: %s", pkg)
        break
    except Exception:
        sas = None
        _HAS_SAS = False
        continue

from .agent import Agent as SimpleAgent  # fallback agent implemented earlier


class StrandsAgent:
    def __init__(self, ollama_url: Optional[str] = None, model: Optional[str] = None):
        self.ollama_url = ollama_url or os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.model = model or os.environ.get("OLLAMA_MODEL", "mistral")

        # Allow opting out of the Strands SDK even if installed. This is
        # useful for local testing with Ollama or when you prefer the
        # internal fallback agent. Set `STRANDS_USE_SDK=1` to force SDK usage.
        use_sdk_flag = os.environ.get("STRANDS_USE_SDK", "false").lower()
        if use_sdk_flag not in ("1", "true", "yes"):
            _HAS_SAS = False

        if _HAS_SAS and sas is not None:
            logger.info("Strands Agents SDK detected — attempting to initialize")
            # Try some common initialization patterns for SDKs. Real SDKs vary
            # widely; the best approach is to set `STRANDS_SDK_PACKAGE` to the
            # correct package name and adjust initialization here if needed.
            try:
                # Prefer the canonical Agent class if present (as in `from strands import Agent`).
                if hasattr(sas, "Agent"):
                    AgentCls = getattr(sas, "Agent")
                    try:
                        self.sdk = AgentCls(model=self.model)
                    except TypeError:
                        self.sdk = AgentCls()
                    self.available = True
                # Some distributions expose a Client object instead
                elif hasattr(sas, "Client"):
                    Client = getattr(sas, "Client")
                    try:
                        self.sdk = Client(base_url=self.ollama_url, model=self.model)
                    except TypeError:
                        # constructor signature differs; try without args
                        self.sdk = Client()
                    self.available = True
                else:
                    # unknown SDK surface — keep module but mark available so
                    # advanced users can access `StrandsAgent.sdk` directly.
                    self.sdk = sas
                    self.available = True
            except Exception as e:
                logger.exception("Failed to initialize Strands SDK client, falling back: %s", e)
                self.sdk = None
                self.available = False
        else:
            logger.info("Strands Agents SDK not installed — using fallback agent")
            self.sdk = None
            self.available = False

        # fallback to simple agent logic
        self._fallback = SimpleAgent(self.ollama_url, self.model)

    async def run(self, message: str) -> Dict[str, Any]:
        """Run the agent on a user message. Returns dict {ok: bool, response/error}.

        If the Strands SDK is available, this should delegate to the SDK agent
        orchestration. Otherwise it falls back to the simple agent logic.
        """
        # If MOCK_AGENT is requested, prefer the local fallback regardless
        mock_flag = os.environ.get("MOCK_AGENT", "false").lower()
        if mock_flag in ("1", "true", "yes"):
            return await self._fallback.run(message)

        if self.available and self.sdk is not None:
            try:
                # Try several common SDK invocation patterns in order of preference.
                # 1) If SDK exposes a `run_chat` method
                if hasattr(self.sdk, "run_chat"):
                    resp = self.sdk.run_chat([{"role": "user", "content": message}])
                # 2) If SDK Agent is callable: agent(query)
                elif callable(self.sdk):
                    resp = self.sdk(message)
                # 3) If SDK exposes a generic `run` method
                elif hasattr(self.sdk, "run"):
                    resp = self.sdk.run(message)
                else:
                    # unknown surface, try stringifying sdk or delegate to fallback
                    logger.warning("Unknown Strands SDK surface, delegating to fallback or returning str(sdk)")
                    try:
                        return {"ok": True, "response": str(self.sdk)}
                    except Exception:
                        return await self._fallback.run(message)

                # Normalize response
                if isinstance(resp, dict) and "response" in resp:
                    return {"ok": True, "response": resp["response"]}
                # If sdk returned something awaitable or async-like, attempt to await
                if hasattr(resp, "__await__"):
                    # run in event loop - if it's a coroutine
                    import asyncio
                    resolved = asyncio.get_event_loop().run_until_complete(resp)
                    resp = resolved
                return {"ok": True, "response": str(resp)}
            except Exception as e:
                logger.exception("Strands SDK agent run failed")
                return {"ok": False, "error": str(e)}

        # fallback
        return await self._fallback.run(message)
