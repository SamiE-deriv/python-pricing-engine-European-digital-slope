from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm

from european_digital_slope.constants import ContractType, PricingCurrency
from european_digital_slope.pricing_engine import (
    EuropeanDigitalSlope,
    PricingParameters,
)
from european_digital_slope.risk_markup import MarkupParameters
from european_digital_slope.historical_vol_surface import build_vol_surface
from european_digital_slope.utils import get_volatility_from_surface


def calculate_higher_order_adjustments(
    spot: float,
    strike: float,
    vol: float,
    time_to_expiry: float,
    r_rate: float,
    vanilla_vega: float,
    slope: float,
    vol_up: float,
    vol_center: float,
    vol_down: float,
    pip_size: float,
    is_call: bool,
) -> Dict[str, float]:
    """Calculate higher order smile adjustments based on Taylor expansion."""
    # Calculate common terms
    sqrt_time = np.sqrt(time_to_expiry)
    vol_time = vol * sqrt_time

    # Calculate d1 and d2 (needed for Greeks)
    d1 = (
        np.log(spot / strike) + (r_rate + 0.5 * vol * vol) * time_to_expiry
    ) / vol_time
    d2 = d1 - vol_time

    # Calculate Greeks using engine's vanilla_vega
    vega = vanilla_vega  # Use engine's vega
    vanna = -d2 / (strike * vol * sqrt_time) * vega  # ∂²C/∂K∂σ = -d₂/(Kσ√T) * Vega
    vomma = vega * d1 * d2 / vol  # ∂²C/∂σ² = Vega * d₁d₂/σ

    # Calculate skew terms
    skew = slope  # ∂σ/∂K

    # Calculate skew_prime using finite difference of slopes
    slope_up = (vol_up - vol_center) / pip_size  # Forward slope
    slope_down = (vol_center - vol_down) / pip_size  # Backward slope
    skew_prime = (slope_up - slope_down) / pip_size  # Second derivative

    # Calculate each adjustment term
    first_order = -vega * skew  # First order skew adjustment (already in engine)
    second_order = -vanna * skew  # Second order (vanna) term
    third_order = -0.5 * vomma * skew * skew  # Third order (vomma) term
    convexity = -vega * skew_prime  # Convexity adjustment

    # Total adjustment (excluding first order which is in engine)
    total_adjustment = second_order + third_order + convexity

    # Flip signs for puts (since ∂P/∂K = -∂C/∂K)
    sign = 1 if is_call else -1
    first_order *= sign
    second_order *= sign
    third_order *= sign
    convexity *= sign
    total_adjustment *= sign

    # Cap adjustment for short-term trades
    if time_to_expiry <= 1 / 365:
        total_adjustment = max(-0.03, min(0.03, total_adjustment))

    return {
        "first_order": first_order,  # For reference only
        "second_order": second_order,
        "third_order": third_order,
        "convexity": convexity,
        "total_adjustment": total_adjustment,
    }


def run_backtest(
    start_date: datetime, end_date: datetime, maturities: List[int]
) -> Dict[str, Dict[int, List[Dict]]]:
    """Run backtest over a date range for multiple maturities."""
    results = {
        "call": {maturity: [] for maturity in maturities},
        "put": {maturity: [] for maturity in maturities},
    }
    current_date = start_date

    while current_date <= end_date:
        try:
            # Skip weekends (files don't exist)
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            # Load data and build vol surface
            vol_surface = build_vol_surface(
                current_date, market_type="commodities", symbol="XAGUSD"
            )

            # Get spot price from data
            data_path = Path("european_digital_slope/data/commodities/xagusd")
            date_str = current_date.strftime("%Y%m%d")
            filename = f"frxXAGUSD_{date_str}.csv"

            with open(data_path / filename) as f:
                first_line = f.readline()
                _, bid, ask, _, mid, *_ = first_line.split(",")
                spot = float(mid)

            # Calculate probabilities for each maturity and option type
            for days_to_expiry in maturities:
                for contract_type in [ContractType.CALL, ContractType.PUT]:
                    # Create pricing parameters
                    params = PricingParameters(
                        contract_type=contract_type,
                        spot=spot,
                        strikes=[spot * 1.001],  # 0.1% OTM
                        date_start=current_date,
                        date_pricing=current_date,
                        date_expiry=current_date + timedelta(days=days_to_expiry),
                        discount_rate=0.02,
                        mu=0.004,
                        vol_surface=vol_surface,
                        q_rate=0.03,
                        r_rate=0.02,
                        priced_with=PricingCurrency.NUMERAIRE,
                        underlying_symbol="XAGUSD",
                        market_type="commodities",
                        is_atm=False,
                        for_sale=True,
                        markup_parameters=MarkupParameters(
                            spot_spread_size=50.0,
                            pip_size=0.0001,
                            vol_spread=0.01,
                            equal_tie_amount=0.01,
                            model_arbitrage_amount=0.05,
                            smile_uncertainty_amount=0.05,
                        ),
                    )

                    # Price option
                    engine = EuropeanDigitalSlope(params)
                    probability = engine.calculate_probability()

                    # Get debug info from engine
                    debug_info = engine.debug_info[contract_type]
                    bs_prob = debug_info["bs_probability"]["amount"]
                    vanilla_vega = debug_info["slope_adjustment"]["parameters"][
                        "vanilla_vega"
                    ]["amount"]
                    slope = debug_info["slope_adjustment"]["parameters"]["slope"]

                    # Calculate higher order adjustments
                    time_to_expiry = days_to_expiry / 365.0
                    pip_size = params.markup_parameters.pip_size
                    strike = params.strikes[0]

                    # Get volatilities at three points for skew_prime calculation
                    vol_down = get_volatility_from_surface(
                        vol_surface,
                        spot,
                        strike - pip_size,
                        time_to_expiry,
                        params.q_rate,
                        params.r_rate,
                    )

                    vol_center = get_volatility_from_surface(
                        vol_surface,
                        spot,
                        strike,
                        time_to_expiry,
                        params.q_rate,
                        params.r_rate,
                    )

                    vol_up = get_volatility_from_surface(
                        vol_surface,
                        spot,
                        strike + pip_size,
                        time_to_expiry,
                        params.q_rate,
                        params.r_rate,
                    )

                    adjustments = calculate_higher_order_adjustments(
                        spot=spot,
                        strike=params.strikes[0],
                        vol=vol_center,
                        time_to_expiry=time_to_expiry,
                        r_rate=params.r_rate,
                        vanilla_vega=vanilla_vega,
                        slope=slope,
                        vol_up=vol_up,
                        vol_center=vol_center,
                        vol_down=vol_down,
                        pip_size=pip_size,
                        is_call=contract_type == ContractType.CALL,
                    )

                    # Store results with all components
                    option_type = (
                        "call" if contract_type == ContractType.CALL else "put"
                    )
                    results[option_type][days_to_expiry].append(
                        {
                            "date": current_date,
                            "spot": spot,
                            "strike": params.strikes[0],
                            "atm_vol": vol_center,
                            "bs_prob": bs_prob,
                            "engine_prob": probability,  # First order included
                            "second_order_adj": adjustments["second_order"],
                            "third_order_adj": adjustments["third_order"],
                            "convexity_adj": adjustments["convexity"],
                            "higher_order_adj": adjustments["total_adjustment"],
                            "final_prob": probability + adjustments["total_adjustment"],
                        }
                    )

        except Exception as e:
            print(f"Error processing {current_date}: {str(e)}")

        current_date += timedelta(days=1)

    return results


def create_plots(
    results: Dict[str, Dict[int, List[Dict]]],
    option_type: str,
    start_date: datetime,
    end_date: datetime,
    month: str,
):
    """Create plots for a specific option type (call or put)."""
    # Create DataFrames for analysis
    dfs = {
        maturity: pd.DataFrame(data) for maturity, data in results[option_type].items()
    }

    # Create plots
    plt.style.use("bmh")
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle(
        f"{month} 2024 - XAG/USD (Silver) {option_type.upper()} Options Analysis",
        fontsize=16,
    )

    # Colors for different maturities
    colors = ["blue", "green", "red", "purple", "orange"]

    # Plot 1: Spot Price and ATM Volatility
    ax1.plot(dfs[1]["date"], dfs[1]["spot"], label="Spot", color="black")
    ax1.set_ylabel("Spot Price", color="black")
    ax1.tick_params(axis="y", labelcolor="black")

    ax1_twin = ax1.twinx()
    ax1_twin.plot(
        dfs[1]["date"], dfs[1]["atm_vol"], label="ATM Vol", color="red", linestyle="--"
    )
    ax1_twin.set_ylabel("ATM Volatility", color="red")
    ax1_twin.tick_params(axis="y", labelcolor="red")
    ax1.set_title("XAG/USD (Silver) Spot Price and ATM Volatility")

    # Plot 2: Higher Order Impact by Maturity
    for maturity, color in zip(dfs.keys(), colors):
        df = dfs[maturity]
        ax2.plot(
            df["date"],
            df["higher_order_adj"],
            color=color,
            label=f"{maturity}d",
        )
    ax2.set_ylabel("Higher Order Adjustment")
    ax2.set_title("Higher Order Impact by Maturity")
    ax2.grid(True, which="both", linestyle=":")
    ax2.legend()

    # Plot 3: Relative Impact by Term (all maturities)
    terms = [
        ("First Order", lambda df: df["engine_prob"] - df["bs_prob"], "-"),
        ("Second Order", lambda df: df["second_order_adj"], "--"),
        ("Third Order", lambda df: df["third_order_adj"], ":"),
        ("Convexity", lambda df: df["convexity_adj"], "-."),
    ]
    for maturity, color in zip(dfs.keys(), colors):
        df = dfs[maturity]
        for label, func, style in terms:
            relative_impact = (func(df) / df["bs_prob"]) * 100
            ax3.plot(
                df["date"],
                relative_impact,
                label=f"{maturity}d {label}",
                color=color,
                linestyle=style,
            )
    ax3.set_ylabel("Relative Impact vs BS (%)")
    ax3.set_title("Relative Impact of All Terms by Maturity")
    ax3.axhline(y=0, color="gray", linestyle=":")
    ax3.grid(True, which="both", linestyle=":")
    ax3.legend(ncol=2, fontsize="small")

    # Plot 4: Probability Evolution by Maturity
    linestyles = ["-", "--", ":"]
    for maturity, color in zip(dfs.keys(), colors):
        df = dfs[maturity]
        ax4.plot(
            df["date"],
            df["bs_prob"],
            color=color,
            linestyle=linestyles[0],
            label=f"{maturity}d BS",
        )
        ax4.plot(
            df["date"],
            df["engine_prob"],
            color=color,
            linestyle=linestyles[1],
            label=f"{maturity}d Engine",
        )
        ax4.plot(
            df["date"],
            df["final_prob"],
            color=color,
            linestyle=linestyles[2],
            label=f"{maturity}d Final",
        )
    ax4.set_ylabel("Probability")
    ax4.set_title("Probability Evolution by Maturity")
    ax4.grid(True)
    ax4.legend(ncol=2, fontsize="small")

    plt.tight_layout()
    plt.show()

    # Print summary statistics
    print(f"\nBacktest Results Summary for {option_type.upper()} Options")
    print("=======================")
    print(f"Period: {start_date.date()} to {end_date.date()}")

    for maturity in dfs.keys():
        df = dfs[maturity]
        print(f"\n{maturity}-day Maturity Analysis:")
        print(f"Average BS Base: {df['bs_prob'].mean():.4f}")
        print(f"Average Engine Prob (with first order): {df['engine_prob'].mean():.4f}")
        print("\nAverage Higher Order Adjustments:")
        print(f"  Second Order: {df['second_order_adj'].mean():.4f}")
        print(f"  Third Order: {df['third_order_adj'].mean():.4f}")
        print(f"  Convexity: {df['convexity_adj'].mean():.4f}")
        print(f"Total Higher Order Impact: {df['higher_order_adj'].mean():.4f}")
        print(f"Final Probability: {df['final_prob'].mean():.4f}")
        print(
            f"Higher Order Impact: {(df['higher_order_adj'] / df['engine_prob']).mean() * 100:.2f}%"
        )


def main():
    # Run backtest for three different months
    periods = [
        (datetime(2024, 1, 2), datetime(2024, 1, 31), "January"),
        (datetime(2024, 2, 1), datetime(2024, 2, 29), "February"),
        (datetime(2024, 3, 1), datetime(2024, 3, 31), "March"),
    ]

    # Different maturities to analyze (in days)
    maturities = [1, 5, 10, 20, 30]

    # Run analysis for each period
    for start_date, end_date, month in periods:
        print(f"\nAnalyzing {month} 2024...")

        # Run backtest for both calls and puts
        results = run_backtest(start_date, end_date, maturities)

        # Create separate plots for calls and puts
        for option_type in ["call", "put"]:
            create_plots(results, option_type, start_date, end_date, month)

        print(f"\nCompleted {month} analysis")


if __name__ == "__main__":
    main()
