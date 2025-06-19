import numpy as np
from scipy.stats import norm
from typing import Tuple
from .constants import ContractType, Number


def d1(
    spot: float, strike: float, time: float, rate: float, div: float, vol: float
) -> float:
    """Calculate d1 parameter for Black-Scholes formula."""
    if vol <= 0 or time <= 0:
        return float("inf")
    return (np.log(spot / strike) + (rate - div + 0.5 * vol * vol) * time) / (
        vol * np.sqrt(time)
    )


def d2(d1_value: float, vol: float, time: float) -> float:
    """Calculate d2 parameter for Black-Scholes formula."""
    return d1_value - vol * np.sqrt(time)


def binary_call(
    spot: float, strike: float, time: float, rate: float, div: float, vol: float
) -> float:
    """Price a binary call option."""
    if vol <= 0 or time <= 0:
        return 1.0 if spot > strike else 0.0

    d1_val = d1(spot, strike, time, rate, div, vol)
    d2_val = d2(d1_val, vol, time)
    return np.exp(-rate * time) * norm.cdf(d2_val)


def binary_put(
    spot: float, strike: float, time: float, rate: float, div: float, vol: float
) -> float:
    """Price a binary put option."""
    if vol <= 0 or time <= 0:
        return 1.0 if spot < strike else 0.0

    d1_val = d1(spot, strike, time, rate, div, vol)
    d2_val = d2(d1_val, vol, time)
    return np.exp(-rate * time) * norm.cdf(-d2_val)


def vanilla_call(
    spot: float, strike: float, time: float, rate: float, div: float, vol: float
) -> float:
    """Price a vanilla call option."""
    if vol <= 0 or time <= 0:
        return max(0, spot - strike)

    d1_val = d1(spot, strike, time, rate, div, vol)
    d2_val = d2(d1_val, vol, time)
    return spot * np.exp(-div * time) * norm.cdf(d1_val) - strike * np.exp(
        -rate * time
    ) * norm.cdf(d2_val)


def vanilla_put(
    spot: float, strike: float, time: float, rate: float, div: float, vol: float
) -> float:
    """Price a vanilla put option."""
    if vol <= 0 or time <= 0:
        return max(0, strike - spot)

    d1_val = d1(spot, strike, time, rate, div, vol)
    d2_val = d2(d1_val, vol, time)
    return strike * np.exp(-rate * time) * norm.cdf(-d2_val) - spot * np.exp(
        -div * time
    ) * norm.cdf(-d1_val)


def delta_binary_call(
    spot: float, strike: float, time: float, rate: float, div: float, vol: float
) -> float:
    """Calculate delta for binary call option."""
    if vol <= 0 or time <= 0:
        return 0.0

    d1_val = d1(spot, strike, time, rate, div, vol)
    d2_val = d2(d1_val, vol, time)
    return np.exp(-rate * time) * norm.pdf(d2_val) / (spot * vol * np.sqrt(time))


def delta_binary_put(
    spot: float, strike: float, time: float, rate: float, div: float, vol: float
) -> float:
    """Calculate delta for binary put option."""
    return -delta_binary_call(spot, strike, time, rate, div, vol)


def vega_binary_call(
    spot: float, strike: float, time: float, rate: float, div: float, vol: float
) -> float:
    """Calculate vega for binary call option."""
    if vol <= 0 or time <= 0:
        return 0.0

    d1_val = d1(spot, strike, time, rate, div, vol)
    d2_val = d2(d1_val, vol, time)
    return -np.exp(-rate * time) * norm.pdf(d2_val) * d2_val / vol


def vega_binary_put(
    spot: float, strike: float, time: float, rate: float, div: float, vol: float
) -> float:
    """Calculate vega for binary put option."""
    return -vega_binary_call(spot, strike, time, rate, div, vol)


def vega_vanilla_call(
    spot: float, strike: float, time: float, rate: float, div: float, vol: float
) -> float:
    """Calculate vega for vanilla call option."""
    if vol <= 0 or time <= 0:
        return 0.0

    d1_val = d1(spot, strike, time, rate, div, vol)
    return spot * np.exp(-div * time) * np.sqrt(time) * norm.pdf(d1_val)


def vega_vanilla_put(
    spot: float, strike: float, time: float, rate: float, div: float, vol: float
) -> float:
    """Calculate vega for vanilla put option."""
    return vega_vanilla_call(spot, strike, time, rate, div, vol)


def price_binary_option(
    contract_type: ContractType,
    spot: float,
    strike: float,
    time: float,
    rate: float,
    div: float,
    vol: float,
) -> float:
    """Price a binary option based on contract type."""
    if contract_type == ContractType.CALL:
        return binary_call(spot, strike, time, rate, div, vol)
    elif contract_type == ContractType.PUT:
        return binary_put(spot, strike, time, rate, div, vol)
    else:
        raise ValueError(f"Unsupported contract type: {contract_type}")
