from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Dict, Tuple

from .constants import ContractType, PricingCurrency
from .pricing_engine import PricingParameters, EuropeanDigitalSlope
from .risk_markup import MarkupParameters
from .historical_vol_surface import build_vol_surface


def calculate_slope_adjustment(
    spot: float,
    strike: float,
    vol_surface: Dict,
    days: int,
    pip_size: float = 0.0001,
) -> float:
    """Calculate volatility slope adjustment."""
    if days not in vol_surface:
        return 0.0

    smile = vol_surface[days]["smile"]

    # Calculate slope using same method as EDS
    k_up = strike + pip_size
    k_down = strike - pip_size

    # Get volatilities at k±pip
    moneyness_up = k_up / spot
    moneyness_down = k_down / spot

    # Interpolate volatilities
    def get_vol(moneyness):
        if moneyness < 0.95:
            return smile[10]
        elif moneyness < 0.975:
            return smile[25]
        elif moneyness < 1.025:
            return smile[50]
        elif moneyness < 1.05:
            return smile[75]
        else:
            return smile[90]

    vol_up = get_vol(moneyness_up)
    vol_down = get_vol(moneyness_down)

    # Calculate slope
    slope = (vol_up - vol_down) / (2 * pip_size)
    return slope


def simulate_paths(
    spot: float,
    strike: float,
    vol: float,
    time_to_expiry: float,
    r_rate: float,
    q_rate: float,
    n_paths: int = 10000,
    n_steps: int = 252,
    vol_surface: Dict = None,
) -> np.ndarray:
    """Simulate price paths using Monte Carlo with local volatility.

    Args:
        spot: Initial spot price
        strike: Strike price
        vol: ATM volatility
        time_to_expiry: Time to expiry in years
        r_rate: Risk-free rate
        q_rate: Dividend/carry rate
        n_paths: Number of simulation paths
        n_steps: Number of time steps
        vol_surface: Optional volatility surface for local vol

    Returns:
        Array of final prices for each path
    """
    dt = time_to_expiry / n_steps
    drift = (r_rate - q_rate - 0.5 * vol**2) * dt
    diffusion = vol * np.sqrt(dt)

    # Initialize paths
    paths = np.zeros((n_paths, n_steps + 1))
    paths[:, 0] = spot

    # Generate random walks
    for t in range(n_steps):
        if vol_surface:
            # Use full volatility surface with smile effects
            current_spot = paths[:, t]
            current_time = t * dt
            days = int(current_time * 365)

            # Get volatilities from surface with slope and markup adjustments
            local_vols = np.zeros(n_paths)
            for i in range(n_paths):
                spot_price = current_spot[i]
                # Find closest tenor in surface
                if days in vol_surface:
                    smile = vol_surface[days]["smile"]
                    # Calculate moneyness and interpolate in smile
                    moneyness = spot_price / strike
                    if moneyness < 0.95:
                        vol_idx = 10
                    elif moneyness < 0.975:
                        vol_idx = 25
                    elif moneyness < 1.025:
                        vol_idx = 50
                    elif moneyness < 1.05:
                        vol_idx = 75
                    else:
                        vol_idx = 90

                    # Get base volatility
                    base_vol = smile[vol_idx]

                    # Add slope adjustment
                    slope = calculate_slope_adjustment(
                        spot=spot_price,
                        strike=strike,
                        vol_surface=vol_surface,
                        days=days,
                    )

                    # Apply all EDS adjustments
                    time_factor = np.sqrt(time_to_expiry)

                    # Slope adjustment
                    slope_adjustment = slope * time_factor

                    # Risk markup adjustments
                    vol_spread = 0.01  # From markup parameters
                    model_arbitrage = 0.05  # From markup parameters
                    smile_uncertainty = 0.05  # From markup parameters

                    # Combined adjustments
                    total_adjustment = (
                        slope_adjustment  # Slope effect
                        + vol_spread * time_factor  # Volatility spread
                        + model_arbitrage * time_factor  # Model arbitrage
                        + smile_uncertainty
                        * abs(slope)
                        * time_factor  # Smile uncertainty
                    )

                    # Final volatility with all adjustments
                    local_vols[i] = base_vol + total_adjustment
                else:
                    local_vols[i] = vol
            local_drift = (r_rate - q_rate - 0.5 * local_vols**2) * dt
            local_diffusion = local_vols * np.sqrt(dt)

            # Update paths with local volatility
            paths[:, t + 1] = current_spot * np.exp(
                local_drift + local_diffusion * np.random.normal(0, 1, n_paths)
            )
        else:
            # Standard geometric Brownian motion
            paths[:, t + 1] = paths[:, t] * np.exp(
                drift + diffusion * np.random.normal(0, 1, n_paths)
            )

    return paths[:, -1]  # Return final prices


def calculate_mc_probability(
    spot: float,
    strike: float,
    vol: float,
    time_to_expiry: float,
    r_rate: float,
    q_rate: float,
    n_paths: int = 10000,
    n_steps: int = 252,
    vol_surface: Dict = None,
) -> Tuple[float, float]:
    """Calculate probability using Monte Carlo simulation.

    Args:
        spot: Initial spot price
        strike: Strike price
        vol: ATM volatility
        time_to_expiry: Time to expiry in years
        r_rate: Risk-free rate
        q_rate: Dividend/carry rate
        n_paths: Number of simulation paths
        n_steps: Number of time steps
        vol_surface: Optional volatility surface for local vol

    Returns:
        Tuple of (probability, standard error)
    """
    # Simulate paths
    final_prices = simulate_paths(
        spot=spot,
        strike=strike,
        vol=vol,
        time_to_expiry=time_to_expiry,
        r_rate=r_rate,
        q_rate=q_rate,
        n_paths=n_paths,
        n_steps=n_steps,
        vol_surface=vol_surface,
    )

    # Calculate probability and error
    successes = (final_prices > strike).sum()
    prob = successes / n_paths
    std_error = np.sqrt(prob * (1 - prob) / n_paths)

    return prob, std_error


def run_comparison_backtest(
    start_date: datetime,
    end_date: datetime,
    maturities: List[int],
    n_paths: int = 10000,
    n_steps: int = 252,
) -> Dict[int, List[Dict]]:
    """Run backtest comparing Monte Carlo with other methods.

    Args:
        start_date: Start date for backtest
        end_date: End date for backtest
        maturities: List of days to expiry to analyze
        n_paths: Number of simulation paths
        n_steps: Number of time steps

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
            vol_surface = build_vol_surface(current_date)

            # Get spot price
            data_path = Path("european_digital_slope/data/forex/frxEURUSD")
            date_str = current_date.strftime("%Y%m%d")
            filename = f"frxEURUSD_{date_str}.csv"

            with open(data_path / filename) as f:
                first_line = f.readline()
                _, bid, ask, _, mid, *_ = first_line.split(",")
                spot = float(mid)

            # Calculate probabilities for each maturity
            for days_to_expiry in maturities:
                # Parameters
                strike = spot * 1.001  # 0.1% OTM
                time_to_expiry = days_to_expiry / 365.0
                atm_vol = vol_surface[1]["smile"][50]

                # Calculate Monte Carlo probability
                mc_prob, mc_error = calculate_mc_probability(
                    spot=spot,
                    strike=strike,
                    vol=atm_vol,
                    time_to_expiry=time_to_expiry,
                    r_rate=0.02,
                    q_rate=0.03,
                    n_paths=n_paths,
                    n_steps=n_steps,
                    vol_surface=vol_surface,
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

                engine = EuropeanDigitalSlope(params)
                eds_prob = engine.calculate_probability()

                # Store results
                results[days_to_expiry].append(
                    {
                        "date": current_date,
                        "spot": spot,
                        "strike": strike,
                        "atm_vol": atm_vol,
                        "mc_prob": mc_prob,
                        "mc_error": mc_error,
                        "eds_prob": eds_prob,
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

    # Run Monte Carlo comparison
    results = run_comparison_backtest(
        start_date=start_date,
        end_date=end_date,
        maturities=maturities,
        n_paths=10000,
        n_steps=252,
    )

    # Create DataFrames for analysis
    dfs = {}
    for maturity, data in results.items():
        if data:  # Only create DataFrame if we have data
            df = pd.DataFrame(data)
            df["date"] = pd.to_datetime(df["date"])
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

    # Plot 1: Monte Carlo vs EDS Probabilities
    for maturity, color in zip(maturities, colors):
        df = dfs[maturity]
        # Plot Monte Carlo
        ax1.plot(
            df["date"],
            df["mc_prob"],
            color=color,
            linestyle="--",
            label=f"{maturity}d MC",
        )
        # Add error bands
        ax1.fill_between(
            df["date"],
            df["mc_prob"] - 2 * df["mc_error"],
            df["mc_prob"] + 2 * df["mc_error"],
            color=color,
            alpha=0.1,
        )
        # Plot EDS
        ax1.plot(
            df["date"],
            df["eds_prob"],
            color=color,
            linestyle="-",
            label=f"{maturity}d EDS",
        )

    ax1.set_ylabel("Probability")
    ax1.set_title("Monte Carlo vs EDS Probabilities (with MC 95% CI)")
    ax1.legend()

    # Plot 2: Differences over time
    for maturity, color in zip(maturities, colors):
        df = dfs[maturity]
        ax2.plot(
            df["date"],
            df["eds_prob"] - df["mc_prob"],
            color=color,
            label=f"{maturity}d",
        )
    ax2.set_ylabel("EDS - MC Difference")
    ax2.set_title("Probability Differences Over Time")
    ax2.legend()

    # Plot 3: Average probabilities vs maturity
    maturities_array = np.array(maturities)
    mc_means = [dfs[m]["mc_prob"].mean() for m in maturities]
    eds_means = [dfs[m]["eds_prob"].mean() for m in maturities]

    ax3.plot(maturities_array, mc_means, "b-", label="MC")
    ax3.plot(maturities_array, eds_means, "r-", label="EDS")
    ax3.set_xlabel("Maturity (days)")
    ax3.set_ylabel("Average Probability")
    ax3.set_title("Probability vs Maturity")
    ax3.legend()

    # Plot 4: ATM Volatility
    ax4.plot(dfs[1]["date"], dfs[1]["atm_vol"], label="ATM Vol")
    ax4.set_ylabel("ATM Volatility")
    ax4.set_title("ATM Volatility")
    ax4.legend()

    plt.tight_layout()
    plt.show()

    # Print summary statistics
    print("\nMonte Carlo Results Summary")
    print("========================")
    print(f"Period: {start_date.date()} to {end_date.date()}")
    print(f"Paths: 10000, Steps: 252")  # Default values used in backtest

    for maturity in maturities:
        df = dfs[maturity]
        print(f"\n{maturity}-day Maturity Analysis:")
        mc_mean = df["mc_prob"].mean()
        mc_error = df["mc_error"].mean()
        eds_mean = df["eds_prob"].mean()
        print(f"Average MC Probability: {mc_mean:.4f}")
        print(f"Average MC Std Error: {mc_error:.4f}")
        print(
            f"MC 95% CI: [{mc_mean - 2 * mc_error:.4f}, {mc_mean + 2 * mc_error:.4f}]"
        )
        print(f"Average EDS Probability: {eds_mean:.4f}")
        print(f"EDS vs MC Difference: {eds_mean - mc_mean:.4f}")


if __name__ == "__main__":
    main()
