from typing import Any, Dict, List, Protocol, Tuple


class RoutingServiceProtocol(Protocol):
    """Boundary contract for geocoding and real road-network routing engines (Target: F061-F070)."""

    def geocode_address(self, address: str) -> Tuple[float, float]: ...

    def calculate_route(self, waypoints: List[Tuple[float, float]]) -> Dict[str, Any]: ...
