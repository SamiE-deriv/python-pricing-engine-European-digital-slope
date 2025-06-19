import numpy as np
from datetime import datetime
from typing import List, Dict, Optional, Union, Tuple
from dataclasses import dataclass

from .constants import ContractType, PricingCurrency, Number
from .utils import (
    calculate_time_to_expiry,
    get_volatility_from_surface,
    get_spread_from_surface,
    is_forward_starting,
    is_intraday,
)
from .black_scholes import (
    price_binary_option,
    delta_binary_call,
    delta_binary_put,
    vega_binary_call,
    vega_binary_put,
    vega_vanilla_call,
    vega_vanilla_put,
)
from .risk_markup import RiskMarkup, MarkupParameters
from .underlying_config import UnderlyingConfig


@dataclass
class PricingParameters:
    """Parameters required for option pricing."""

    contract_type: ContractType
    spot: float
    strikes: List[float]
    date_start: datetime
    date_pricing: datetime
    date_expiry: datetime
    discount_rate: float
    mu: float
    vol_surface: Dict
    q_rate: float
    r_rate: float
    priced_with: PricingCurrency
    underlying_symbol: str
    market_type: str
    is_atm: bool = False
    for_sale: bool = True
    markup_parameters: Optional[MarkupParameters] = None


class EuropeanDigitalSlope:
    """Main pricing engine for European Digital Slope options."""

    def _validate_parameters(self):
        """Validate input parameters."""
        if self.params.contract_type not in ContractType:
            raise ValueError(f"Unsupported contract type: {self.params.contract_type}")

        if self.params.priced_with not in PricingCurrency:
            raise ValueError(f"Unsupported pricing currency: {self.params.priced_with}")

        if len(self.params.strikes) not in [1, 2]:
            raise ValueError("Must provide either 1 or 2 strike prices")

        if self.params.date_expiry <= self.params.date_start:
            raise ValueError("Expiry date must be after start date")

    def calculate_probability(self) -> float:
        """Calculate the probability of option payoff."""
        base_prob = self._calculate_base_probability()

        # Calculate Greeks for markup
        delta = self._calculate_delta()
        vega = self._calculate_vega()

        # Apply risk markup
        markup = self.risk_markup.calculate_total_markup(delta, vega)

        # Combine and bound the result
        final_prob = base_prob + markup
        return max(0.0, min(1.0, final_prob))

    def _calculate_base_probability(self) -> float:
        """Calculate base probability before markup."""
        if len(self.params.strikes) == 2:
            return self._calculate_two_barrier_probability()

        if self.params.priced_with == PricingCurrency.NUMERAIRE:
            return self._calculate_numeraire_probability()
        elif self.params.priced_with == PricingCurrency.QUANTO:
            return self._calculate_quanto_probability()
        else:  # BASE
            return self._calculate_base_probability_with_vanilla()

    def __init__(self, params: PricingParameters):
        """Initialize the pricing engine with required parameters."""
        self.params = params
        self._validate_parameters()

        # Calculate derived values
        self.time_to_expiry = calculate_time_to_expiry(
            self.params.date_start, self.params.date_expiry
        )

        # Initialize risk markup calculator
        self.risk_markup = RiskMarkup(
            is_atm=self.params.is_atm,
            is_forward_starting=is_forward_starting(
                self.params.date_pricing, self.params.date_start
            ),
            time_to_expiry=self.time_to_expiry,
            market_type=self.params.market_type,
            for_sale=self.params.for_sale,
            parameters=self.params.markup_parameters,
        )

        # Initialize debug info
        self.debug_info = {}

    def _calculate_numeraire_probability(self) -> float:
        """Calculate probability in numeraire terms."""
        prob, debug_info = self._calculate(self.params.contract_type)
        self.debug_info[self.params.contract_type] = debug_info
        return prob

    def _calculate(self, contract_type: ContractType) -> Tuple[float, Dict]:
        """Calculate probability with slope adjustment and debug info."""
        debug_info = {}
        # Get base probability
        strike = self.params.strikes[0]
        vol = get_volatility_from_surface(
            self.params.vol_surface,
            self.params.spot,
            strike,
            self.time_to_expiry,
            self.params.q_rate,
            self.params.r_rate,
        )

        # Get base probability
        bs_formula = price_binary_option
        bs_probability = bs_formula(
            contract_type,
            self.params.spot,
            strike,
            self.time_to_expiry,
            self.params.discount_rate,
            self.params.mu,
            vol,
        )

        debug_info["bs_probability"] = {
            "amount": bs_probability,
            "parameters": {
                "spot": self.params.spot,
                "strike": strike,
                "time": self.time_to_expiry,
                "rate": self.params.discount_rate,
                "div": self.params.mu,
                "vol": vol,
            },
        }

        # Calculate slope adjustment if not forward starting
        slope_adjustment = 0.0
        if not is_forward_starting(self.params.date_pricing, self.params.date_start):
            # Use ATM volatility for Greeks
            vol_args = self._get_vol_expiry()
            atm_vol = self._get_atm_volatility(vol_args)

            # Calculate vanilla vega
            if contract_type == ContractType.CALL:
                vanilla_vega = vega_vanilla_call(
                    self.params.spot,
                    strike,
                    self.time_to_expiry,
                    self.params.discount_rate,
                    self.params.mu,
                    atm_vol,
                )
            else:
                vanilla_vega = vega_vanilla_put(
                    self.params.spot,
                    strike,
                    self.time_to_expiry,
                    self.params.discount_rate,
                    self.params.mu,
                    atm_vol,
                )

            # Get volatility at strike ± pip using underlying config
            underlying_config = self._get_underlying_config()
            pip_size = underlying_config.pip_size
            vol_args = {
                "spot": self.params.spot,
                "q_rate": self.params.q_rate,
                "r_rate": self.params.r_rate,
                **self._get_vol_expiry(),
            }

            vol_args["strike"] = strike - pip_size
            vol_down = get_volatility_from_surface(
                self.params.vol_surface,
                self.params.spot,
                strike - pip_size,
                self.time_to_expiry,
                self.params.q_rate,
                self.params.r_rate,
            )

            vol_args["strike"] = strike + pip_size
            vol_up = get_volatility_from_surface(
                self.params.vol_surface,
                self.params.spot,
                strike + pip_size,
                self.time_to_expiry,
                self.params.q_rate,
                self.params.r_rate,
            )

            # Calculate slope
            slope = (vol_up - vol_down) / (2 * pip_size)

            # Apply slope adjustment with correct sign
            base_amount = -1 if contract_type == ContractType.CALL else 1
            slope_adjustment = base_amount * vanilla_vega * slope

            # Cap adjustment for short-term trades
            if (
                self.time_to_expiry <= 1 / 365
                and self._get_first_tenor_on_surface() > 7
            ):
                slope_adjustment = max(-0.03, min(0.03, slope_adjustment))

            debug_info["slope_adjustment"] = {
                "amount": slope_adjustment,
                "parameters": {
                    "vanilla_vega": {
                        "amount": vanilla_vega,
                        "parameters": {
                            "spot": self.params.spot,
                            "strike": strike,
                            "time": self.time_to_expiry,
                            "rate": self.params.discount_rate,
                            "div": self.params.mu,
                            "vol": atm_vol,
                        },
                    },
                    "slope": slope,
                },
            }

        return bs_probability + slope_adjustment, debug_info

    def _get_vol_expiry(self) -> Dict[str, datetime]:
        """Get volatility expiry parameters."""
        return {
            "from": self.params.date_start,
            "to": self.params.date_expiry,
        }

    def _get_atm_volatility(self, vol_args: Dict) -> float:
        """Get ATM volatility."""
        vol_args = vol_args.copy()
        vol_args["market"] = "ATM"
        return get_volatility_from_surface(
            self.params.vol_surface,
            self.params.spot,
            self.params.strikes[0],
            self.time_to_expiry,
            self.params.q_rate,
            self.params.r_rate,
        )

    def _get_underlying_config(self) -> UnderlyingConfig:
        """Get underlying configuration."""
        return UnderlyingConfig.by_symbol(self.params.underlying_symbol)

    def _calculate_quanto_probability(self) -> float:
        """Calculate probability with quanto adjustment."""
        # For quanto, use r_rate - q_rate as drift
        adjusted_mu = self.params.r_rate - self.params.q_rate

        vol = get_volatility_from_surface(
            self.params.vol_surface,
            self.params.spot,
            self.params.strikes[0],
            self.time_to_expiry,
            self.params.q_rate,
            self.params.r_rate,
        )

        return price_binary_option(
            self.params.contract_type,
            self.params.spot,
            self.params.strikes[0],
            self.time_to_expiry,
            self.params.discount_rate,
            adjusted_mu,
            vol,
        )

    def _calculate_base_probability_with_vanilla(self) -> float:
        """Calculate probability in base currency terms."""
        strike = self.params.strikes[0]
        vol = get_volatility_from_surface(
            self.params.vol_surface,
            self.params.spot,
            strike,
            self.time_to_expiry,
            self.params.q_rate,
            self.params.r_rate,
        )

        # Calculate components based on Castagna's formulas
        numeraire_prob = price_binary_option(
            self.params.contract_type,
            self.params.spot,
            strike,
            self.time_to_expiry,
            self.params.r_rate,  # Use r_rate for numeraire probability
            self.params.r_rate - self.params.q_rate,  # Adjusted drift
            vol,
        )

        # The sign depends on whether it's a call or put
        sign = 1 if self.params.contract_type == ContractType.CALL else -1

        return (
            numeraire_prob * strike + sign * self._calculate_vanilla_component()
        ) / self.params.spot

    def _calculate_vanilla_component(self) -> float:
        """Calculate the vanilla option component for base currency pricing."""
        # Implementation would depend on specific requirements
        # This is a placeholder that would need to be implemented based on exact needs
        return 0.0

    def _calculate_two_barrier_probability(self) -> float:
        """Calculate probability for double barrier options."""
        low_strike, high_strike = sorted(self.params.strikes)

        # Calculate probabilities for both barriers
        if self.params.contract_type == ContractType.EXPIRYMISS:
            return self._calculate_expiry_miss_probability(low_strike, high_strike)
        else:  # EXPIRYRANGE
            return self._calculate_expiry_range_probability(low_strike, high_strike)

    def _calculate_expiry_miss_probability(
        self, low_strike: float, high_strike: float
    ) -> float:
        """Calculate probability for EXPIRYMISS options."""
        # Probability of being below low strike
        low_prob = price_binary_option(
            ContractType.PUT,
            self.params.spot,
            low_strike,
            self.time_to_expiry,
            self.params.discount_rate,
            self.params.mu,
            self._get_volatility_for_strike(low_strike),
        )

        # Probability of being above high strike
        high_prob = price_binary_option(
            ContractType.CALL,
            self.params.spot,
            high_strike,
            self.time_to_expiry,
            self.params.discount_rate,
            self.params.mu,
            self._get_volatility_for_strike(high_strike),
        )

        return low_prob + high_prob

    def _calculate_expiry_range_probability(
        self, low_strike: float, high_strike: float
    ) -> float:
        """Calculate probability for EXPIRYRANGE options."""
        # EXPIRYRANGE is 1 - EXPIRYMISS with discounting
        discount_factor = np.exp(-self.params.discount_rate * self.time_to_expiry)
        expiry_miss_prob = self._calculate_expiry_miss_probability(
            low_strike, high_strike
        )
        return discount_factor * (1 - expiry_miss_prob)

    def _get_volatility_for_strike(self, strike: float) -> float:
        """Get volatility for a specific strike price."""
        return get_volatility_from_surface(
            self.params.vol_surface,
            self.params.spot,
            strike,
            self.time_to_expiry,
            self.params.q_rate,
            self.params.r_rate,
        )

    def _calculate_delta(self) -> float:
        """Calculate option delta for risk markup."""
        if self.params.contract_type == ContractType.CALL:
            return delta_binary_call(
                self.params.spot,
                self.params.strikes[0],
                self.time_to_expiry,
                self.params.discount_rate,
                self.params.mu,
                self._get_volatility_for_strike(self.params.strikes[0]),
            )
        else:
            return delta_binary_put(
                self.params.spot,
                self.params.strikes[0],
                self.time_to_expiry,
                self.params.discount_rate,
                self.params.mu,
                self._get_volatility_for_strike(self.params.strikes[0]),
            )

    def _calculate_vega(self) -> float:
        """Calculate option vega for risk markup."""
        if self.params.contract_type == ContractType.CALL:
            return vega_binary_call(
                self.params.spot,
                self.params.strikes[0],
                self.time_to_expiry,
                self.params.discount_rate,
                self.params.mu,
                self._get_volatility_for_strike(self.params.strikes[0]),
            )
        else:
            return vega_binary_put(
                self.params.spot,
                self.params.strikes[0],
                self.time_to_expiry,
                self.params.discount_rate,
                self.params.mu,
                self._get_volatility_for_strike(self.params.strikes[0]),
            )

    def _get_first_tenor_on_surface(self) -> int:
        """Get the first tenor (in days) from the volatility surface."""
        return min(self.params.vol_surface.keys())
