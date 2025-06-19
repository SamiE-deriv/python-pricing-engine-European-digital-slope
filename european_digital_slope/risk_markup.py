from dataclasses import dataclass
from typing import Dict, Optional, Any
from datetime import datetime
from .constants import POTENTIAL_ARBITRAGE_DURATION
from .utils import is_intraday


@dataclass
class MarkupParameters:
    """Parameters for markup calculations."""

    spot_spread_size: float = 50.0
    pip_size: float = 0.0001
    vol_spread: float = 0.01
    equal_tie_amount: float = 0.01
    model_arbitrage_amount: float = 0.05
    smile_uncertainty_amount: float = 0.05
    hour_end_markup_parameters: Optional[Dict[str, Any]] = None


class HourEndMarkup:
    """Calculate hour end markup."""

    def __init__(
        self,
        hour_end_markup_parameters: Dict[str, Any],
        spot_min: float,
        spot_max: float,
    ):
        self.params = hour_end_markup_parameters
        self.spot_min = spot_min
        self.spot_max = spot_max

    def calculate_markup(self) -> float:
        """Calculate hour end markup amount."""
        # Implementation would depend on specific requirements
        # This is a placeholder that would need to be implemented based on exact needs
        return 0.0


class EqualTieMarkup:
    """Calculate equal tie markup."""

    def __init__(self, underlying_symbol: str, time_to_expiry: float):
        self.underlying_symbol = underlying_symbol
        self.time_to_expiry = time_to_expiry

    def calculate_markup(self) -> float:
        """Calculate equal tie markup amount."""
        # Implementation would depend on specific requirements
        # This is a placeholder that would need to be implemented based on exact needs
        return 0.01


class ModelArbitrageMarkup:
    """Calculate model arbitrage markup."""

    def calculate_markup(self) -> float:
        """Calculate model arbitrage markup amount."""
        return 0.05


class RiskMarkup:
    """Calculate various risk markups for option pricing."""

    def __init__(
        self,
        is_atm: bool,
        is_forward_starting: bool,
        time_to_expiry: float,
        market_type: str,
        for_sale: bool = True,
        parameters: Optional[MarkupParameters] = None,
    ):
        self.is_atm = is_atm
        self.is_forward_starting = is_forward_starting
        self.time_to_expiry = time_to_expiry
        self.market_type = market_type.lower()
        self.for_sale = for_sale
        self.params = parameters or MarkupParameters()
        self.debug_info = {}

    def calculate_total_markup(self, delta: float, vega: float) -> float:
        """Calculate total risk markup."""
        markup = 0.0

        # Base markups for traded markets
        if self._apply_traded_market_markup():
            # Hour end markup
            if self.params.hour_end_markup_parameters:
                params = self.params.hour_end_markup_parameters
                current_spot = params.get("current_spot", 0)
                min_spot = min(current_spot, params.get("high_low", {}).get("low", 0))
                max_spot = max(current_spot, params.get("high_low", {}).get("high", 0))

                hour_end_markup = HourEndMarkup(
                    hour_end_markup_parameters=params,
                    spot_min=min_spot,
                    spot_max=max_spot,
                ).calculate_markup()
                markup += hour_end_markup
                self.debug_info["hour_end_markup"] = hour_end_markup

            # Skip most markups for forward starting contracts
            if not (self.is_forward_starting and not self._apply_equal_tie_markup()):
                # Volatility spread markup for non-ATM contracts
                if not self.is_atm:
                    vol_markup = min(self.params.vol_spread * abs(vega), 0.7)
                    markup += vol_markup
                    self.debug_info["vol_spread_markup"] = vol_markup

                # Spot spread markup for non-intraday trades
                if not is_intraday(self.time_to_expiry):
                    spot_spread_base = (
                        self.params.spot_spread_size * self.params.pip_size
                    )
                    spot_markup = max(0, min(spot_spread_base * abs(delta), 0.01))
                    markup += spot_markup
                    self.debug_info["spot_spread_markup"] = spot_markup

                # Smile uncertainty markup for short-term index options
                if self._apply_smile_uncertainty_markup():
                    smile_markup = self.params.smile_uncertainty_amount
                    markup += smile_markup
                    self.debug_info["smile_uncertainty_markup"] = smile_markup

            # Equal tie markup
            if self._apply_equal_tie_markup():
                equal_tie_markup = EqualTieMarkup(
                    underlying_symbol="",  # Would need to be passed in
                    time_to_expiry=self.time_to_expiry,
                ).calculate_markup()
                markup += equal_tie_markup
                self.debug_info["equal_tie_markup"] = equal_tie_markup

        # Model arbitrage markup for short duration contracts
        if (
            not self.for_sale
            and self.time_to_expiry * 365 * 24 * 3600 <= POTENTIAL_ARBITRAGE_DURATION
        ):
            model_arb_markup = ModelArbitrageMarkup().calculate_markup()
            markup += model_arb_markup
            self.debug_info["model_arbitrage_markup"] = model_arb_markup

        # Risk markup divided equally on both sides
        markup /= 2
        self.debug_info["total_markup"] = markup

        return markup

    def _apply_traded_market_markup(self) -> bool:
        """Check if traded market markup should be applied."""
        return self.market_type in [
            "forex",
            "commodities",
            "indices",
        ] or self.market_type.endswith(("_basket", "forex_basket", "commodity_basket"))

    def _apply_smile_uncertainty_markup(self) -> bool:
        """Check if smile uncertainty markup should be applied."""
        return (
            self.market_type == "indices"
            and self.time_to_expiry < 7 / 365
            and not self.is_atm
        )

    def _apply_equal_tie_markup(self) -> bool:
        """Check if equal tie markup should be applied."""
        return True
