from dataclasses import dataclass
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
from european_digital_slope.butterfly_finite_diff import calculate_bs_probability
from european_digital_slope.utils import get_volatility_from_surface
from european_digital_slope.black_scholes import (
    price_binary_option,
    vega_vanilla_call,
    vanilla_call,
)


@dataclass
class Product:
    """Class to hold product-specific parameters."""

    symbol: str
    market_type: str
    data_path: str
    pip_size: float
    spot_spread: float
    filename_prefix: str


def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1 + erf(x / np.sqrt(2)))


def get_products() -> List[Product]:
    """Get list of products to analyze."""
    return [
        # Forex
        Product(
            symbol="EURUSD",
            market_type="forex",
            data_path="/Users/samielmokh/Documents/perl-Pricing-Engine-European-Digital-Slope/european_digital_slope/data/forex/frxEURUSD",
            pip_size=0.0001,
            spot_spread=0.00020,
            filename_prefix="frxEURUSD_",
        ),
        Product(
            symbol="GBPUSD",
            market_type="forex",
            data_path="/Users/samielmokh/Documents/perl-Pricing-Engine-European-Digital-Slope/european_digital_slope/data/forex/frxGBPUSD",
            pip_size=0.0001,
            spot_spread=0.00020,
            filename_prefix="frxGBPUSD_",
        ),
        Product(
            symbol="JPYUSD",
            market_type="forex",
            data_path="/Users/samielmokh/Documents/perl-Pricing-Engine-European-Digital-Slope/european_digital_slope/data/forex/frxUSDJPY",
            pip_size=0.000001,
            spot_spread=0.000002,
            filename_prefix="frxUSDJPY_",
        ),
        # Commodities
        Product(
            symbol="XAUUSD",
            market_type="commodities",
            data_path="/Users/samielmokh/Documents/perl-Pricing-Engine-European-Digital-Slope/european_digital_slope/data/commodities/xauusd",
            pip_size=0.01,
            spot_spread=0.50,
            filename_prefix="frxXAUUSD_",
        ),
        Product(
            symbol="XAGUSD",
            market_type="commodities",
            data_path="/Users/samielmokh/Documents/perl-Pricing-Engine-European-Digital-Slope/european_digital_slope/data/commodities/xagusd",
            pip_size=0.001,
            spot_spread=0.020,
            filename_prefix="frxXAGUSD_",
        ),
    ]


def run_comparison_backtest(
    product: Product, start_date: datetime, end_date: datetime, maturities: List[int]
) -> Dict[int, List[Dict]]:
    """Run backtest comparing both probability calculation methods.

    Args:
        product: Product to analyze
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
                current_date, market_type=product.market_type, symbol=product.symbol
            )

            # Get spot price
            date_str = current_date.strftime("%Y%m%d")
            filename = f"{product.filename_prefix}{date_str}.csv"

            with open(f"{product.data_path}/{filename}") as f:
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
                    spot_spread_size=product.spot_spread,
                    pip_size=product.pip_size,
                    vol_spread=0.01,
                    equal_tie_amount=0.01,
                    model_arbitrage_amount=0.05,
                    smile_uncertainty_amount=0.05,
                )

                # Calculate butterfly probability using finite difference
                pip_size = markup_params.pip_size

                # Get volatilities at K and K+ΔK
                vol_k = get_volatility_from_surface(
                    vol_surface,
                    spot,
                    strike,
                    time_to_expiry,
                    q_rate=0.03,
                    r_rate=0.02,
                )
                vol_k_plus = get_volatility_from_surface(
                    vol_surface,
                    spot,
                    strike + pip_size,
                    time_to_expiry,
                    q_rate=0.03,
                    r_rate=0.02,
                )

                # Calculate vanilla call prices with corresponding vols using engine's rates
                vanilla_price_k = vanilla_call(
                    spot,
                    strike,
                    time_to_expiry,
                    rate=0.02,  # discount_rate
                    div=0.004,  # mu (drift rate)
                    vol=vol_k,
                )
                vanilla_price_k_plus = vanilla_call(
                    spot,
                    strike + pip_size,
                    time_to_expiry,
                    rate=0.02,  # discount_rate
                    div=0.004,  # mu (drift rate)
                    vol=vol_k_plus,
                )

                # Calculate digital price using finite difference
                # Digital price = [C(K) - C(K+ΔK)]/ΔK
                digital_price = (vanilla_price_k - vanilla_price_k_plus) / pip_size

                # Convert digital price to probability by dividing by discount factor
                # P(S_T > K) = Digital price / exp(-rT)
                butterfly_prob = digital_price / np.exp(
                    -0.02 * time_to_expiry
                )  # r_rate

                # Create engine instance to get markup
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
                    underlying_symbol=product.symbol,
                    market_type=product.market_type,
                    is_atm=False,
                    for_sale=True,
                    markup_parameters=markup_params,
                )

                # Create engine, get markup and EDS probability
                engine = EuropeanDigitalSlope(params)
                delta = engine._calculate_delta()
                vega = engine._calculate_vega()
                markup = engine.risk_markup.calculate_total_markup(delta, vega)

                # Add markup to butterfly probability
                butterfly_prob = butterfly_prob + markup

                # Get EDS probability
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
                    }
                )

        except Exception as e:
            print(f"Error processing {current_date} for {product.symbol}: {str(e)}")

        current_date += timedelta(days=1)

    return results


def plot_product_results(
    product: Product,
    results: Dict[int, List[Dict]],
    start_date: datetime,
    end_date: datetime,
    maturities: List[int],
):
    """Plot results for a single product."""
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
        print(
            f"No data collected for {product.symbol}. Check the data loading process."
        )
        return

    # Create comparison plots
    plt.style.use("bmh")
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle(
        f"{product.symbol} Digital Option Probability Methods Comparison", fontsize=16
    )

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
            df["bs_prob"] - df["butterfly_prob"],
            color=color,
            label=f"{maturity}d",
        )

    ax2.set_ylabel("BS - Butterfly Difference")
    ax2.set_title("Butterfly vs Black-Scholes")
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
    butterfly_bs_diffs = [
        (dfs[m]["bs_prob"] - dfs[m]["butterfly_prob"]).mean() for m in maturities
    ]
    eds_butterfly_diffs = [dfs[m]["prob_diff"].mean() for m in maturities]

    ax4.plot(
        maturities_array,
        butterfly_bs_diffs,
        "b-",
        label="BS vs Butterfly",
    )
    ax4.plot(maturities_array, eds_butterfly_diffs, "r-", label="EDS vs Butterfly")
    ax4.set_xlabel("Maturity (days)")
    ax4.set_ylabel("Average Difference")
    ax4.set_title("Method Differences vs Maturity")
    ax4.legend()

    plt.tight_layout()
    plt.show()

    # Print summary statistics
    print(f"\n{product.symbol} Comparison Results Summary")
    print("=" * (len(product.symbol) + 28))
    print(f"Period: {start_date.date()} to {end_date.date()}")

    for maturity in maturities:
        df = dfs[maturity]
        print(f"\n{maturity}-day Maturity Analysis:")
        print(f"Black-Scholes Probability: {df['bs_prob'].mean():.4f}")
        print(f"Butterfly Probability: {df['butterfly_prob'].mean():.4f}")
        print(f"EDS Probability: {df['eds_prob'].mean():.4f}")
        print(f"EDS vs Butterfly Difference: {df['prob_diff'].mean():.4f}")


def main():
    # Run backtest for January 2024
    start_date = datetime(2024, 1, 2)
    end_date = datetime(2024, 1, 31)

    # Different maturities to analyze (in days)
    maturities = [1, 5, 10, 20, 30]

    # Get products to analyze
    products = get_products()

    # Run comparison backtest for each product
    for product in products:
        print(f"\nAnalyzing {product.symbol}...")
        results = run_comparison_backtest(product, start_date, end_date, maturities)
        plot_product_results(product, results, start_date, end_date, maturities)


if __name__ == "__main__":
    main()
