# Pricing Engine: European Digital Slope

## Overview
A comprehensive pricing engine for European digital options with volatility skew and slope adjustments. This implementation includes:
- First and second-order expansions
- Volatility surface calibration
- Market-specific adjustments for FX and commodities
- Extensive validation tools

## Mathematical Framework

### Core Pricing Methods

1. **Butterfly Spread Approximation**:
$$
\mathrm{Digital}(K) = \lim_{\Delta K \to 0} \frac{\text{Call}(K, \sigma(K)) - \text{Call}(K + \Delta K, \sigma(K + \Delta K))}{\Delta K}
$$

2. **First Derivative with Skew**:
$$
\mathrm{Digital}(K) = -\frac{\partial \text{Call}}{\partial K} - \mathrm{Vega} \cdot \text{skew}
$$

3. **Second Order Expansion**:
$$
\begin{aligned}
\frac{d^2}{dK^2} \text{Call}(K, \sigma(K)) &= \frac{\partial^2 \text{Call}}{\partial K^2} + 2 \frac{\partial^2 \text{Call}}{\partial K \partial \sigma} \cdot \frac{\partial \sigma}{\partial K} \\
&+ \frac{\partial^2 \text{Call}}{\partial \sigma^2} \left(\frac{\partial \sigma}{\partial K}\right)^2 + \frac{\partial \text{Call}}{\partial \sigma} \frac{\partial^2 \sigma}{\partial K^2}
\end{aligned}
$$

## Project Structure

```
.
├── european_digital_slope/
│   ├── __init__.py
│   ├── black_scholes.py          # Core BS implementation
│   ├── butterfly_finite_diff.py   # Butterfly method
│   ├── pricing_engine.py         # Main pricing engine
│   ├── higher_order_smile.py     # Smile adjustments
│   ├── monte_carlo_validation.py # Validation tools
│   └── data/                     # Market data
│       ├── commodities/
│       │   ├── gold/
│       │   └── silver/
│       └── forex/
│           ├── frJPYUSD/
│           ├── frxEURUSD/
│           └── frxGBPUSD/
├── lib/
│   └── Pricing/
│       └── Engine/
│           └── EuropeanDigitalSlope.pm
├── t/                           # Test suite
│   ├── price_check.t
│   ├── pricing.t
│   └── slope.t
└── docs/                        # Documentation
    ├── results.md               # Analysis results
    └── pricing_formula_analysis.md
```

## Key Features

1. **Multiple Pricing Methods**
   - Butterfly spread approximation
   - First derivative with skew adjustment
   - Higher-order expansions

2. **Market Coverage**
   - FX Majors (EUR, GBP)
   - JPY Crosses
   - Commodities (Gold, Silver)

3. **Volatility Surface Handling**
   - Skew calibration
   - Smile adjustments
   - Term structure

4. **Validation Tools**
   - Monte Carlo simulations
   - Market price comparisons
   - Error analysis

## Implementation Details

### Core Components

1. **Black-Scholes Engine**
   - Standard option pricing
   - Greeks calculation
   - Volatility adjustments

2. **Slope Engine**
   - First derivative implementation
   - Skew adjustments
   - Higher-order corrections

3. **Market Data**
   - Historical volatility surfaces
   - Real-time data integration
   - Calibration tools

## Validation Results

Our analysis shows:
1. Strong agreement between butterfly and first derivative methods (diff < 0.1%)
2. Vanna*skew term dominates higher-order corrections
3. Market-specific patterns in convergence and accuracy

## Usage

```perl
use Pricing::Engine::EuropeanDigitalSlope;

my $engine = Pricing::Engine::EuropeanDigitalSlope->new(
    spot => 100,
    strike => 102,
    maturity => 0.25,  # in years
    rate => 0.05,
    volatility => 0.2,
    skew => -0.002     # dσ/dK
);

my $price = $engine->price();
my $delta = $engine->delta();
```

## Dependencies
- Perl 5.10 or higher
- Math::CDF
- Statistics::Descriptive
- Date::Calc

## Installation

```bash
perl Makefile.PL
make
make test
make install
```

## Testing
Run the test suite:
```bash
prove -l t/
```

## Contributing
1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License
MIT License

## Authors
Sami El Mokh

## References
- Results and analysis documentation
- Market data sources
- Validation methodology
