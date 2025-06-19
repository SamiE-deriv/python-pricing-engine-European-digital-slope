import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from .constants import Number


def calculate_time_to_expiry(start_date: datetime, expiry_date: datetime) -> float:
    """Calculate time to expiry in years."""
    days = (expiry_date - start_date).total_seconds() / (24 * 60 * 60)
    # Prevent duration from going to zero and cap at 730 days (2 years)
    epsilon = np.finfo(float).eps
    return min(730, max(epsilon, days)) / 365


def get_volatility_from_surface(
    vol_surface: Dict,
    spot: float,
    strike: float,
    time_to_expiry: float,
    q_rate: float,
    r_rate: float,
) -> float:
    """Extract volatility from volatility surface."""
    # Find closest tenor
    tenors = sorted(vol_surface.keys())
    tenor = min(tenors, key=lambda x: abs(x - time_to_expiry * 365))

    # Get smile data for tenor
    smile_data = vol_surface[tenor]["smile"]

    # Calculate delta for strike
    forward = spot * np.exp((r_rate - q_rate) * time_to_expiry)
    moneyness = np.log(strike / forward)

    # Interpolate volatility using available smile points
    deltas = sorted(smile_data.keys())
    vols = [smile_data[d] for d in deltas]

    # Simple linear interpolation
    delta = 50 + (moneyness / (2 * np.pi)) * 100
    if delta <= min(deltas):
        return vols[0]
    if delta >= max(deltas):
        return vols[-1]

    # Linear interpolation between closest points
    for i in range(len(deltas) - 1):
        if deltas[i] <= delta <= deltas[i + 1]:
            w = (delta - deltas[i]) / (deltas[i + 1] - deltas[i])
            return vols[i] * (1 - w) + vols[i + 1] * w

    return smile_data[50]  # Default to ATM vol if interpolation fails


def get_spread_from_surface(vol_surface: Dict, tenor: int) -> float:
    """Get volatility spread for a given tenor."""
    return vol_surface[tenor].get("vol_spread", {}).get(50, 0.01)


def is_forward_starting(pricing_date: datetime, start_date: datetime) -> bool:
    """Check if contract is forward starting (>5 seconds difference)."""
    return (start_date - pricing_date).total_seconds() > 5


def is_intraday(time_to_expiry: float) -> bool:
    """Check if contract duration is less than 1 day."""
    return time_to_expiry <= 1 / 365
