from typing import Any, Dict, Protocol


class ExternalProviderAdapterProtocol(Protocol):
    """Boundary contract for external third-party service provider adapters."""

    def execute_lookup(self, query_parameter: str) -> Dict[str, Any]: ...
