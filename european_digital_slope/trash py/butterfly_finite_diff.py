from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from math import erf

from european_digital_slope.constants import ContractType, PricingCurrency
from european_digital_slope.pricing_engine import (
    EuropeanDigitalSlope,
    PricingParameters,
)
from european_digital_slope.risk_markup import MarkupParameters, RiskMarkup
from european_digital_slope.historical_vol_surface import build_vol_surface


def calculate_bs_probability(
    spot: float,
    strike: float,
    vol: float,
    time_to_expiry: float,
    r_rate: float,
    q_rate: float,
) -> float:
    """Calculate the Black-Scholes probability N(d2)."""
    if time_to_expiry <= 0:
        return 1.0 if spot > strike else 0.0

    d1 = (np.log(spot / strike) + (r_rate - q_rate + 0.5 * vol**2) * time_to_expiry) / (
        vol * np.sqrt(time_to_expiry)
    )
    d2 = d1 - vol * np.sqrt(time_to_expiry)
    return norm_cdf(d2)


def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1 + erf(x / np.sqrt(2)))


def calculate_butterfly_probability(
    spot: float,
    strike: float,
    vol: float,
    time_to_expiry: float,
    r_rate: float,
    q_rate: float,
    markup_params: Optional[MarkupParameters] = None,
    market_type: str = "forex",
    is_atm: bool = False,
    for_sale: bool = True,
) -> float:
    """Calculate probability using butterfly finite difference method with markup.

    Args:
        spot: Current spot price
        strike: Strike price
        vol: Volatility
        time_to_expiry: Time to expiry in years
        r_rate: Risk-free rate
        q_rate: Dividend/carry rate
        delta_k: Strike spacing for finite difference (default 0.0001)
        markup_params: Optional markup parameters
        market_type: Market type for markup calculation
        is_atm: Whether the option is at-the-money
        for_sale: Whether the option is for sale

    Returns:
        Estimated probability with markup
    """
    # First calculate the base Black-Scholes probability
    bs_prob = calculate_bs_probability(
        spot, strike, vol, time_to_expiry, r_rate, q_rate
    )

    # Calculate butterfly spread prices
    def bs_call(k: float) -> float:
        d1 = (np.log(spot / k) + (r_rate - q_rate + 0.5 * vol**2) * time_to_expiry) / (
            vol * np.sqrt(time_to_expiry)
        )
        d2 = d1 - vol * np.sqrt(time_to_expiry)
        return spot * np.exp(-q_rate * time_to_expiry) * norm_cdf(d1) - k * np.exp(
            -r_rate * time_to_expiry
        ) * norm_cdf(d2)

    # Get pip size from markup parameters or use default
    delta_k = markup_params.pip_size if markup_params else 0.0001

    # Calculate butterfly spread prices
    c_minus = bs_call(strike - delta_k)
    c_center = bs_call(strike)
    c_plus = bs_call(strike + delta_k)

    # Calculate probability density using Breeden-Litzenberger formula
    density = (c_plus - 2 * c_center + c_minus) / (delta_k**2)
    density = density * np.exp(r_rate * time_to_expiry)

    # Calculate cumulative probability P(ST > K)
    # We start with BS probability and add the density contribution
    # Use same pip size for density contribution
    prob = bs_prob + density * delta_k

    # Apply markup if parameters are provided
    if markup_params:
        # Calculate Greeks for markup
        delta = (c_plus - c_minus) / (2 * delta_k)  # Finite difference delta
        vega = bs_call(strike) * np.sqrt(time_to_expiry)  # Simple vega approximation

        # Initialize risk markup calculator
        risk_markup = RiskMarkup(
            is_atm=is_atm,
            is_forward_starting=False,  # We don't handle forward starting in butterfly
            time_to_expiry=time_to_expiry,
            market_type=market_type,
            for_sale=for_sale,
            parameters=markup_params,
        )

        # Calculate and apply markup
        markup = risk_markup.calculate_total_markup(delta, vega)
        prob += markup

    # Ensure probability is between 0 and 1
    return prob


def run_comparison_backtest(
    start_date: datetime, end_date: datetime, maturities: List[int]
) -> Dict[int, List[Dict]]:
    """Run backtest comparing both probability calculation methods.

    Args:
        start_date: Start date for backtest
        end_date: End date for backtest
        maturities: List of days to expiry to analyze

    Returns:
        Dictionary mapping days to expiry to list of results
    """
    results = {maturity: [] for maturity in maturities}
    current_date = start_date

    while current_date <= end_date:
        try:
            # Skip weekends
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            # Load data and build vol surface
            vol_surface = build_vol_surface(
                current_date, market_type="commodities", symbol="XAUUSD"
            )

            # Get spot price
            data_path = Path("european_digital_slope/data/commodities/gold")
            date_str = current_date.strftime("%Y%m%d")
            filename = f"frxXAUUSD_{date_str}.csv"

            with open(data_path / filename) as f:
                first_line = f.readline()
                _, bid, ask, _, mid, *_ = first_line.split(",")
                spot = float(mid)

            # Calculate probabilities for each maturity
            for days_to_expiry in maturities:
                # Parameters for both methods
                strike = spot * 1.001  # 0.1% OTM
                time_to_expiry = days_to_expiry / 365.0
                atm_vol = vol_surface[1]["smile"][50]

                # Calculate probabilities
                bs_prob = calculate_bs_probability(
                    spot=spot,
                    strike=strike,
                    vol=atm_vol,
                    time_to_expiry=time_to_expiry,
                    r_rate=0.02,
                    q_rate=0.03,
                )

                # Create markup parameters with pip size
                markup_params = MarkupParameters(
                    spot_spread_size=50.0,
                    pip_size=0.0001,  # Use consistent pip size
                    vol_spread=0.01,
                    equal_tie_amount=0.01,
                    model_arbitrage_amount=0.05,
                    smile_uncertainty_amount=0.05,
                )

                # Calculate butterfly probability
                butterfly_prob = calculate_butterfly_probability(
                    spot=spot,
                    strike=strike,
                    vol=atm_vol,
                    time_to_expiry=time_to_expiry,
                    r_rate=0.02,
                    q_rate=0.03,
                    markup_params=markup_params,
                    market_type="forex",
                    is_atm=False,
                    for_sale=True,
                )

                # Calculate EDS probability
                params = PricingParameters(
                    contract_type=ContractType.CALL,
                    spot=spot,
                    strikes=[strike],
                    date_start=current_date,
                    date_pricing=current_date,
                    date_expiry=current_date + timedelta(days=days_to_expiry),
                    discount_rate=0.02,
                    mu=0.004,
                    vol_surface=vol_surface,
                    q_rate=0.03,
                    r_rate=0.02,
                    priced_with=PricingCurrency.NUMERAIRE,
                    underlying_symbol="XAUUSD",
                    market_type="commodities",
                    is_atm=False,
                    for_sale=True,
                    markup_parameters=markup_params,
                )

                engine = EuropeanDigitalSlope(params)
                eds_prob = engine.calculate_probability()

                # Store results
                results[days_to_expiry].append(
                    {
                        "date": current_date,
                        "spot": spot,
                        "strike": strike,
                        "atm_vol": atm_vol,
                        "bs_prob": bs_prob,
                        "butterfly_prob": butterfly_prob,
                        "eds_prob": eds_prob,
                        "prob_diff": eds_prob - butterfly_prob,
                        "butterfly_bs_diff": butterfly_prob - bs_prob,
                    }
                )

        except Exception as e:
            print(f"Error processing {current_date}: {str(e)}")

        current_date += timedelta(days=1)

    return results


def main():
    # Run backtest for January 2024
    start_date = datetime(2024, 1, 2)
    end_date = datetime(2024, 1, 31)

    # Different maturities to analyze (in days)
    maturities = [1, 5, 10, 20, 30]

    # Run comparison backtest
    results = run_comparison_backtest(start_date, end_date, maturities)

    # Create DataFrames for analysis
    dfs = {}
    for maturity, data in results.items():
        if data:  # Only create DataFrame if we have data
            df = pd.DataFrame(data)
            df["date"] = pd.to_datetime(df["date"])  # Ensure date is datetime
            dfs[maturity] = df
        else:
            print(f"No data collected for {maturity}-day maturity")

    if not dfs:
        print("No data collected for any maturity. Check the data loading process.")
        return

    # Create comparison plots
    plt.style.use("bmh")
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

    # Colors for different maturities
    colors = ["blue", "green", "red", "purple", "orange"]

    # Plot 1: All Methods Comparison
    for maturity, color in zip(maturities, colors):
        df = dfs[maturity]
        ax1.plot(
            df["date"],
            df["bs_prob"],
            color=color,
            linestyle=":",
            alpha=0.3,
            label=f"{maturity}d BS",
        )
        ax1.plot(
            df["date"],
            df["butterfly_prob"],
            color=color,
            linestyle="--",
            alpha=0.7,
            label=f"{maturity}d Butterfly",
        )
        ax1.plot(
            df["date"],
            df["eds_prob"],
            color=color,
            linestyle="-",
            alpha=1.0,
            label=f"{maturity}d EDS",
        )

    ax1.set_ylabel("Probability")
    ax1.set_title("All Methods Comparison")
    ax1.legend(bbox_to_anchor=(1.05, 1), loc="upper left")

    # Plot 2: Butterfly vs BS Convergence
    for maturity, color in zip(maturities, colors):
        df = dfs[maturity]
        ax2.plot(
            df["date"],
            df["butterfly_bs_diff"],
            color=color,
            label=f"{maturity}d",
        )

    ax2.set_ylabel("Butterfly - BS Difference")
    ax2.set_title("Butterfly Convergence to BS")
    ax2.axhline(y=0, color="gray", linestyle=":")
    ax2.legend()

    # Plot 3: EDS vs Butterfly Divergence
    for maturity, color in zip(maturities, colors):
        df = dfs[maturity]
        ax3.plot(
            df["date"],
            df["prob_diff"],
            color=color,
            label=f"{maturity}d",
        )

    ax3.set_ylabel("EDS - Butterfly Difference")
    ax3.set_title("EDS Divergence from Butterfly")
    ax3.axhline(y=0, color="gray", linestyle=":")
    ax3.legend()

    # Plot 4: Average Differences by Maturity
    maturities_array = np.array(maturities)
    butterfly_bs_diffs = [dfs[m]["butterfly_bs_diff"].mean() for m in maturities]
    eds_butterfly_diffs = [dfs[m]["prob_diff"].mean() for m in maturities]

    ax4.plot(maturities_array, butterfly_bs_diffs, "b-", label="Butterfly vs BS")
    ax4.plot(maturities_array, eds_butterfly_diffs, "r-", label="EDS vs Butterfly")
    ax4.set_xlabel("Maturity (days)")
    ax4.set_ylabel("Average Difference")
    ax4.set_title("Method Differences vs Maturity")
    ax4.legend()

    plt.tight_layout()
    plt.show()

    # Print summary statistics
    print("\nComparison Results Summary")
    print("========================")
    print(f"Period: {start_date.date()} to {end_date.date()}")

    for maturity in maturities:
        df = dfs[maturity]
        print(f"\n{maturity}-day Maturity Analysis:")
        print(f"Black-Scholes Probability: {df['bs_prob'].mean():.4f}")
        print(f"Butterfly Probability: {df['butterfly_prob'].mean():.4f}")
        print(f"EDS Probability: {df['eds_prob'].mean():.4f}")
        print(f"Butterfly vs BS Difference: {df['butterfly_bs_diff'].mean():.4f}")
        print(f"EDS vs Butterfly Difference: {df['prob_diff'].mean():.4f}")


if __name__ == "__main__":
    main()
