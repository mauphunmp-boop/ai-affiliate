from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, Any, Awaitable

# Types for provider operation functions
# Each function is async and accepts (req, db) and returns Any (dict)
OpFunc = Callable[[Any, Any], Awaitable[Any]]


@dataclass
class ProviderOps:
    campaigns_sync: OpFunc
    promotions: OpFunc
    top_products: OpFunc
    datafeeds_all: OpFunc
    products: OpFunc


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, ProviderOps] = {}

    def register(self, name: str, ops: ProviderOps) -> None:
        self._providers[name.lower()] = ops

    def get(self, name: str) -> ProviderOps | None:
        return self._providers.get((name or "").lower())

    def ensure(self, name: str) -> ProviderOps:
        ops = self.get(name)
        if not ops:
            raise ValueError(f"Provider '{name}' chưa được hỗ trợ")
        return ops
