import csv
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
from typing import Dict, List, Tuple


def load_market_data(
    date: datetime, market_type: str, symbol: str
) -> List[Tuple[float, float, float]]:
    """Load market data for a specific instrument and date.

    Args:
        date: The date to load data for
        market_type: Type of market ('forex' or 'commodities')
        symbol: Instrument symbol (e.g., 'EURUSD', 'GBPUSD', 'XAUUSD')

    Returns:
        List of (bid, ask, mid) prices
    """
    date_str = date.strftime("%Y%m%d")

    # Construct data path based on market type and symbol
    if market_type == "forex":
        if symbol == "JPYUSD":
            data_path = Path(__file__).parent / "data/forex/frxUSDJPY"
        else:
            data_path = Path(__file__).parent / f"data/forex/frx{symbol}"
    elif market_type == "commodities":
        if symbol == "XAUUSD":
            data_path = Path(__file__).parent / "data/commodities/xauusd"
        else:
            data_path = Path(__file__).parent / f"data/commodities/{symbol.lower()}"
    else:
        raise ValueError(f"Unsupported market type: {market_type}")

    # Special case for JPYUSD which uses USDJPY in filenames
    if symbol == "JPYUSD":
        filename = f"frxUSDJPY_{date_str}.csv"
    else:
        filename = f"frx{symbol}_{date_str}.csv"
    full_path = data_path / filename

    prices = []
    with open(full_path, "r") as f:
        for line in f:
            # Parse CSV line: timestamp,bid,ask,'',mid,source,...
            ts_ms, bid, ask, _, mid, *_ = line.split(",")
            prices.append((float(bid), float(ask), float(mid)))

    return prices


def calculate_historical_volatility(
    prices: List[Tuple[float, float, float]], window_days: int = 30
) -> float:
    """Calculate historical volatility from price data.

    Args:
        prices: List of (bid, ask, mid) prices
        window_days: Rolling window in days

    Returns:
        Annualized volatility
    """
    # Use mid prices for volatility calculation
    mid_prices = np.array([mid for _, _, mid in prices])

    # Calculate log returns
    returns = np.log(mid_prices[1:] / mid_prices[:-1])

    # Annualize volatility (assuming 1-second data)
    annualization = np.sqrt(252 * 24 * 60 * 60)  # days * hours * minutes * seconds
    volatility = np.std(returns) * annualization

    return volatility


def get_market_parameters(market_type: str, symbol: str) -> Dict:
    """Get market-specific volatility surface parameters.

    Args:
        market_type: Type of market ('forex' or 'commodities')
        symbol: Instrument symbol

    Returns:
        Dictionary of market parameters
    """
    # Default parameters (EUR/USD like)
    default_params = {
        "smile_wings": 1.06,  # 10-delta wings up factor
        "smile_body": 1.02,  # 25-delta factor
        "rr_25": -0.002,  # 25-delta risk reversal
        "rr_10": -0.004,  # 10-delta risk reversal
        "bf_25": 0.0015,  # 25-delta butterfly
        "bf_10": 0.0025,  # 10-delta butterfly
        "term_slope": 0.1,  # Term structure slope
        "rr_term": 0.1,  # RR term structure factor
        "bf_term": 0.05,  # BF term structure factor
    }

    # Market specific adjustments
    if market_type == "forex":
        if symbol == "GBPUSD":
            # GBP/USD typically has steeper smile and larger risk reversals
            return {
                **default_params,
                "smile_wings": 1.08,
                "rr_25": -0.003,
                "rr_10": -0.006,
            }
        elif symbol == "JPYUSD":
            # JPY/USD typically has flatter smile
            return {
                **default_params,
                "smile_wings": 1.04,
                "smile_body": 1.01,
                "rr_25": -0.001,
                "rr_10": -0.002,
            }
        else:  # EURUSD and others
            return default_params

    elif market_type == "commodities":
        if symbol == "XAUUSD":
            # Gold typically has higher vol and steeper smile
            return {
                **default_params,
                "smile_wings": 1.10,
                "smile_body": 1.03,
                "bf_25": 0.002,
                "bf_10": 0.003,
                "term_slope": 0.15,
            }
        else:
            return default_params

    return default_params


def build_vol_surface(
    date: datetime, market_type: str = "forex", symbol: str = "EURUSD"
) -> Dict:
    """Build volatility surface from historical data.

    Args:
        date: The date to build surface for
        market_type: Type of market ('forex' or 'commodities')
        symbol: Instrument symbol

    Returns:
        Volatility surface dictionary
    """
    # Load price data
    prices = load_market_data(date, market_type, symbol)

    # Calculate base volatility
    base_vol = calculate_historical_volatility(prices)

    # Get market-specific parameters
    params = get_market_parameters(market_type, symbol)
    print(f"\nVolatility surface parameters for {symbol}:")
    print(f"Market type: {market_type}")
    print(f"Base volatility: {base_vol:.4f}")
    print(f"Smile wings: {params['smile_wings']}")
    print(f"Smile body: {params['smile_body']}")
    print(f"Risk reversal 25d: {params['rr_25']}")
    print(f"Risk reversal 10d: {params['rr_10']}")

    # Create volatility surface with smile
    vol_surface = {
        1: {  # 1-day tenor
            "smile": {
                10: base_vol * params["smile_wings"],
                25: base_vol * params["smile_body"],
                50: base_vol,  # ATM
                75: base_vol * params["smile_body"],
                90: base_vol * params["smile_wings"],
            },
            "vol_spread": {50: 0.01},
            "rr": {  # Risk reversals
                25: params["rr_25"],
                10: params["rr_10"],
            },
            "bf": {  # Butterflies
                25: params["bf_25"],
                10: params["bf_10"],
            },
        }
    }

    # Add term structure
    for tenor in [7, 30, 90, 180, 365]:  # 1W, 1M, 3M, 6M, 1Y
        term_factor = 1.0 + params["term_slope"] * np.log(tenor / 365 + 1)
        vol_surface[tenor] = {
            "smile": {
                10: base_vol * term_factor * params["smile_wings"],
                25: base_vol * term_factor * params["smile_body"],
                50: base_vol * term_factor,
                75: base_vol * term_factor * params["smile_body"],
                90: base_vol * term_factor * params["smile_wings"],
            },
            "vol_spread": {50: 0.01},
            "rr": {
                25: params["rr_25"] * (1 + params["rr_term"] * tenor / 365),
                10: params["rr_10"] * (1 + params["rr_term"] * tenor / 365),
            },
            "bf": {
                25: params["bf_25"] * (1 + params["bf_term"] * tenor / 365),
                10: params["bf_10"] * (1 + params["bf_term"] * tenor / 365),
            },
        }

    return vol_surface
