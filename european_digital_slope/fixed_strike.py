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


def analyze_fixed_strike(
    start_date: datetime, expiry_date: datetime, fixed_strike: float
) -> List[Dict]:
    """Analyze option probabilities with fixed strike and expiry.

    Args:
        start_date: Start date for analysis
        expiry_date: Fixed expiry date
        fixed_strike: Fixed strike price

    Returns:
        List of dictionaries containing analysis results
    """
    results = []
    current_date = start_date

    while current_date < expiry_date:
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

            # Calculate days to expiry
            days_to_expiry = (expiry_date - current_date).days

            # Create pricing parameters
            params = PricingParameters(
                contract_type=ContractType.CALL,
                spot=spot,
                strikes=[fixed_strike],  # Fixed strike
                date_start=current_date,
                date_pricing=current_date,
                date_expiry=expiry_date,
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
            vanilla_vega = debug_info["slope_adjustment"]["parameters"]["vanilla_vega"][
                "amount"
            ]
            slope = debug_info["slope_adjustment"]["parameters"]["slope"]

            # Store results
            results.append(
                {
                    "date": current_date,
                    "days_to_expiry": days_to_expiry,
                    "spot": spot,
                    "moneyness": spot / fixed_strike - 1,  # % OTM/ITM
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
    # Analyze January 2024 with fixed strike
    start_date = datetime(2024, 1, 2)
    expiry_date = datetime(2024, 1, 31)

    # Get initial spot price to set fixed strike
    with open(
        "european_digital_slope/data/forex/frxEURUSD/frxEURUSD_20240102.csv"
    ) as f:
        first_line = f.readline()
        _, bid, ask, _, mid, *_ = first_line.split(",")
        initial_spot = float(mid)

    fixed_strike = initial_spot * 1.001  # 0.1% OTM from initial spot

    results = analyze_fixed_strike(start_date, expiry_date, fixed_strike)

    # Convert to DataFrame for analysis
    df = pd.DataFrame(results)

    # Print summary statistics
    print("\nFixed Strike Analysis")
    print("====================")
    print(f"Period: {start_date.date()} to {expiry_date.date()}")
    print(f"Fixed Strike: {fixed_strike:.4f}")

    print(f"\nSpot Price Analysis:")
    print(f"Initial Spot: {df['spot'].iloc[0]:.4f}")
    print(f"Final Spot: {df['spot'].iloc[-1]:.4f}")
    print(f"Spot Range: {df['spot'].min():.4f} to {df['spot'].max():.4f}")
    print(
        f"Moneyness Range: {df['moneyness'].min():.1%} to {df['moneyness'].max():.1%}"
    )

    print(f"\nProbability Analysis:")
    print(f"Initial Probability: {df['final_prob'].iloc[0]:.4f}")
    print(f"Final Probability: {df['final_prob'].iloc[-1]:.4f}")
    print(
        f"Probability Range: {df['final_prob'].min():.4f} to {df['final_prob'].max():.4f}"
    )

    # Create plots
    plt.style.use("bmh")
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10))

    # Plot 1: Spot Price vs Strike
    ax1.plot(df["date"], df["spot"], label="Spot", color="blue")
    ax1.axhline(y=fixed_strike, color="red", linestyle="--", label="Strike")
    ax1.set_ylabel("Price")
    ax1.legend()
    ax1.set_title(f"EUR/USD Spot Price vs Fixed Strike ({fixed_strike:.4f})")

    # Plot 2: Moneyness and Time to Expiry
    ax2.plot(df["date"], df["moneyness"], color="purple")
    ax2.set_ylabel("Moneyness (Spot/Strike - 1)")
    ax2.set_title("Option Moneyness")
    ax2.axhline(y=0, color="gray", linestyle=":")

    # Plot 3: Probabilities
    ax3.plot(df["date"], df["base_prob"], label="Base Prob", color="blue")
    ax3.plot(df["date"], df["final_prob"], label="Final Prob", color="green")
    ax3.fill_between(
        df["date"],
        df["base_prob"],
        df["final_prob"],
        alpha=0.2,
        color="gray",
        label="Adjustment",
    )
    ax3.set_ylabel("Probability")
    ax3.set_title("Option Probabilities")
    ax3.legend()

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
