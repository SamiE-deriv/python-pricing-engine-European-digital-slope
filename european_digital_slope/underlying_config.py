from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class UnderlyingConfig:
    """Configuration for underlying instruments."""

    market: str
    submarket: str
    pip_size: float
    spot_spread_size: Optional[float] = 50.0

    @classmethod
    def by_symbol(cls, symbol: str) -> "UnderlyingConfig":
        """Get underlying configuration by symbol."""
        # This would need to be implemented with actual market data
        # For now returning standard forex config
        if symbol.startswith("frx"):
            return cls(
                market="forex", submarket="", pip_size=0.0001, spot_spread_size=50.0
            )
        return cls(market="indices", submarket="", pip_size=0.01, spot_spread_size=50.0)
