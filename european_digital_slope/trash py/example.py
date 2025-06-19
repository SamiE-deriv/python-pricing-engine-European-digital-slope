from datetime import datetime, timedelta
from european_digital_slope.constants import ContractType, PricingCurrency
from european_digital_slope.pricing_engine import (
    EuropeanDigitalSlope,
    PricingParameters,
)
from european_digital_slope.risk_markup import MarkupParameters
from european_digital_slope.historical_vol_surface import build_vol_surface


def main():
    # Use historical data from January 2024
    pricing_date = datetime(2024, 1, 2)  # First trading day of 2024

    # Build volatility surface from historical data
    vol_surface = build_vol_surface(pricing_date)

    # Load first price from historical data to use as spot
    with open(
        "european_digital_slope/data/forex/frxEURUSD/frxEURUSD_20240102.csv"
    ) as f:
        first_line = f.readline()
        _, bid, ask, _, mid, *_ = first_line.split(",")
        spot = float(mid)
    # Set up pricing parameters
    params = PricingParameters(
        contract_type=ContractType.CALL,
        spot=spot,  # Historical EUR/USD rate
        strikes=[spot * 1.001],  # Strike 0.1% OTM
        date_start=pricing_date,  # Contract start date
        date_pricing=pricing_date,  # Pricing date
        date_expiry=pricing_date + timedelta(days=1),  # Expiry date
        discount_rate=0.02,  # USD interest rate
        mu=0.004,  # Drift rate
        vol_surface=vol_surface,  # Volatility surface
        q_rate=0.03,  # EUR interest rate
        r_rate=0.02,  # USD interest rate
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

    # Create pricing engine instance
    engine = EuropeanDigitalSlope(params)

    # Calculate option probability
    probability = engine.calculate_probability()
    print(f"\nEuropean Digital Slope Option Pricing Example")
    print(f"============================================")
    print(f"Contract Type: {params.contract_type.value}")
    print(f"Underlying: {params.underlying_symbol}")
    print(f"Current Spot: {params.spot:.4f}")
    print(f"Strike: {params.strikes[0]:.4f}")
    print(f"Time to Expiry: {engine.time_to_expiry * 365:.1f} days")
    print(f"Volatility (ATM): {vol_surface[1]['smile'][50]:.1%}")

    # Print detailed probability breakdown
    debug_info = engine.debug_info[ContractType.CALL]
    bs_prob = debug_info["bs_probability"]["amount"]
    slope_adj = debug_info["slope_adjustment"]["amount"]
    vanilla_vega = debug_info["slope_adjustment"]["parameters"]["vanilla_vega"][
        "amount"
    ]
    slope = debug_info["slope_adjustment"]["parameters"]["slope"]

    print(f"\nProbability Breakdown:")
    print(f"Base Probability (exp(-rq × t) × N(d2)): {bs_prob:.4f}")
    print(f"Vanilla Vega: {vanilla_vega:.6f}")
    print(f"Volatility Slope: {slope:.6f}")
    print(f"Slope Adjustment (-vega_vanilla × skew): {slope_adj:.4f}")
    print(f"Final Probability: {probability:.4f}")


if __name__ == "__main__":
    main()
