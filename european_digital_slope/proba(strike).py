from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import pandas as pd
import matplotlib.pyplot as plt

from european_digital_slope.constants import ContractType, PricingCurrency
from european_digital_slope.pricing_engine import (
    EuropeanDigitalSlope,
    PricingParameters,
)
from european_digital_slope.risk_markup import MarkupParameters
from european_digital_slope.historical_vol_surface import build_vol_surface


def run_backtest(
    start_date: datetime, end_date: datetime, maturities: List[int]
) -> Dict[int, List[Dict]]:
    """Run backtest over a date range for multiple maturities.

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
            # Skip weekends (files don't exist)
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            # Load data and build vol surface
            vol_surface = build_vol_surface(current_date)

            # Get spot price from data
            data_path = Path("european_digital_slope/data/forex/frxEURUSD")
            date_str = current_date.strftime("%Y%m%d")
            filename = f"frxEURUSD_{date_str}.csv"

            with open(data_path / filename) as f:
                first_line = f.readline()
                _, bid, ask, _, mid, *_ = first_line.split(",")
                spot = float(mid)

            # Calculate probabilities for each maturity
            for days_to_expiry in maturities:
                # Create pricing parameters
                params = PricingParameters(
                    contract_type=ContractType.CALL,
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
                    underlying_symbol="EURUSD",
                    market_type="forex",
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

                # Get debug info
                debug_info = engine.debug_info[ContractType.CALL]
                bs_prob = debug_info["bs_probability"]["amount"]
                slope_adj = debug_info["slope_adjustment"]["amount"]
                vanilla_vega = debug_info["slope_adjustment"]["parameters"][
                    "vanilla_vega"
                ]["amount"]
                slope = debug_info["slope_adjustment"]["parameters"]["slope"]

                # Store results
                results[days_to_expiry].append(
                    {
                        "date": current_date,
                        "spot": spot,
                        "strike": params.strikes[0],
                        "atm_vol": vol_surface[1]["smile"][50],
                        "base_prob": bs_prob,
                        "vanilla_vega": vanilla_vega,
                        "vol_slope": slope,
                        "slope_adj": slope_adj,
                        "final_prob": probability,
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

    results = run_backtest(start_date, end_date, maturities)

    # Create DataFrames for analysis
    dfs = {maturity: pd.DataFrame(data) for maturity, data in results.items()}

    # Create plots
    plt.style.use("bmh")
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 12))

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
    ax1.set_title("EUR/USD Spot Price and ATM Volatility")

    # Plot 2: Volatility Slope
    for maturity, color in zip(maturities, colors):
        ax2.plot(
            dfs[maturity]["date"],
            dfs[maturity]["vol_slope"],
            color=color,
            label=f"{maturity}d",
        )
    ax2.set_ylabel("Volatility Slope")
    ax2.set_title("Volatility Smile Slope")
    ax2.axhline(y=0, color="gray", linestyle=":")
    ax2.legend()

    # Plot 3: Probabilities for different maturities
    for maturity, color in zip(maturities, colors):
        df = dfs[maturity]
        # Plot base probability
        ax3.plot(
            df["date"],
            df["base_prob"],
            color=color,
            linestyle="--",
            alpha=0.5,
            label=f"{maturity}d Base",
        )
        # Plot final probability
        ax3.plot(
            df["date"],
            df["final_prob"],
            color=color,
            linestyle="-",
            label=f"{maturity}d Final",
        )

    ax3.set_ylabel("Probability")
    ax3.set_title("Option Probabilities (Solid: Final, Dashed: Base)")
    ax3.legend(bbox_to_anchor=(1.05, 1), loc="upper left")

    plt.tight_layout()
    plt.show()

    # Print summary statistics for each maturity
    print("\nBacktest Results Summary")
    print("=======================")
    print(f"Period: {start_date.date()} to {end_date.date()}")

    for maturity in maturities:
        df = dfs[maturity]
        print(f"\n{maturity}-day Maturity Analysis:")
        print(f"Average Base Probability: {df['base_prob'].mean():.4f}")
        print(f"Average Final Probability: {df['final_prob'].mean():.4f}")
        print(f"Average Slope Adjustment: {df['slope_adj'].mean():.4f}")
        print(
            f"Probability Range: {df['final_prob'].min():.4f} to {df['final_prob'].max():.4f}"
        )


if __name__ == "__main__":
    main()
