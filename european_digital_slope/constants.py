from enum import Enum
from typing import List, Dict, Union, Optional

# Constants
POTENTIAL_ARBITRAGE_DURATION = 18060  # 5 hours and 1 minute in seconds


class ContractType(Enum):
    CALL = "CALL"
    PUT = "PUT"
    EXPIRYMISS = "EXPIRYMISS"
    EXPIRYRANGE = "EXPIRYRANGE"


class PricingCurrency(Enum):
    BASE = "base"
    NUMERAIRE = "numeraire"
    QUANTO = "quanto"


# Type hints
Number = Union[int, float]
VolSurface = Dict[int, Dict[str, Dict[int, float]]]
MarketData = Dict[str, Dict[int, Dict[str, Dict[int, float]]]]
