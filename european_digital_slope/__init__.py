"""
European Digital Slope Option Pricing Engine

This package provides a sophisticated pricing engine for European Digital Slope options,
implementing the Black-Scholes framework with various adjustments for risk markup
and volatility surface handling.

Main Components:
- EuropeanDigitalSlope: Main pricing engine class
- PricingParameters: Configuration class for option parameters
- ContractType: Enum for supported contract types (CALL, PUT, EXPIRYMISS, EXPIRYRANGE)
- PricingCurrency: Enum for pricing currency types (BASE, NUMERAIRE, QUANTO)
- MarkupParameters: Configuration for risk markup calculations
"""

from .constants import ContractType, PricingCurrency
from .pricing_engine import EuropeanDigitalSlope, PricingParameters
from .risk_markup import RiskMarkup, MarkupParameters

__version__ = "1.0.0"

__all__ = [
    "ContractType",
    "PricingCurrency",
    "EuropeanDigitalSlope",
    "PricingParameters",
    "RiskMarkup",
    "MarkupParameters",
]
