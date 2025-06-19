# Digital Option Pricing: Comparative Analysis of Methods and Market Impact

## I. Butterfly vs First Derivative Methods: Convergence Analysis

1. **Methodology Comparison**:
   - Butterfly: Uses finite difference approximation of digital price


$$
\mathrm{Digital}(K) = \lim_{\Delta K \to 0} \frac{\text{Call}(K, \sigma(K)) - \text{Call}(K + \Delta K, \sigma(K + \Delta K))}{\Delta K}
$$

   - Engine (EDS): Uses analytical first derivative with skew adjustment


$$
\mathrm{Digital}(K) = -\frac{\partial \text{Call}}{\partial K} - \mathrm{Vega} \cdot \text{skew}
$$

2. **Convergence Analysis (Q1 2024)**:
   - EURUSD:
     * 1-day: EDS 0.3158 vs Butterfly 0.3066 (diff: +0.92%)
     * 30-day: EDS 0.5184 vs Butterfly 0.5171 (diff: +0.12%)
     * Largest discrepancies in short-term
   - GBPUSD:
     * 1-day: EDS 0.3357 vs Butterfly 0.3285 (diff: +0.72%)
     * 30-day: EDS 0.5156 vs Butterfly 0.5149 (diff: +0.07%)
     * Similar pattern but smaller differences
   - JPYUSD:
     * 1-day: EDS 0.3641 vs Butterfly 0.3642 (diff: -0.00%)
     * 30-day: EDS 0.5119 vs Butterfly 0.5128 (diff: -0.08%)
     * Exceptional agreement across maturities
   - XAUUSD:
     * 1-day: EDS 0.3286 vs Butterfly 0.3281 (diff: +0.05%)
     * 30-day: EDS 0.5164 vs Butterfly 0.5172 (diff: -0.07%)
     * Good agreement despite steep smile
   - XAGUSD:
     * 1-day: EDS 0.4449 vs Butterfly 0.4436 (diff: +0.14%)
     * 30-day: EDS 0.5009 vs Butterfly 0.5015 (diff: -0.06%)
     * Higher base probabilities but good convergence

3. **Market-Specific Patterns**:
   - FX Majors (EURUSD, GBPUSD):
     * Largest discrepancies in short-term
     * Strong convergence with maturity
     * Higher base volatilities
   - JPY Crosses:
     * Exceptional agreement between methods
     * Flatter volatility smile (wings: 1.04)
     * Lower risk reversals (-0.001/-0.002)
   - Commodities:
     * XAUUSD: Steeper smile (wings: 1.10)
     * XAGUSD: Higher base volatility (~0.14)
     * Better agreement in short-term vs FX

4. **Key Findings**:
   - Maturity Effect: Differences decrease with longer maturities
   - Market Impact: FX majors show larger adjustments than commodities
   - Volatility Impact: Higher base volatility leads to larger differences
   - Smile Effect: Steeper smiles (XAUUSD) show more pronounced differences

5. **Practical Implications**:
   - Short-dated options (1-5 days): Engine pricing provides meaningful adjustments
   - Medium-term options (10-20 days): Methods converge significantly
   - Long-dated options (30+ days): Differences become negligible (<0.1%)
   - Market choice: FX requires more attention to methodology than commodities

### Key Findings (Overall Analysis)

1. **Convergence with Maturity**: The difference between Butterfly and EDS methods generally decreases with maturity across all instruments.

2. **Short-term Behavior**: Largest discrepancies observed in short-term (1-day) maturities, particularly for FX majors (EURUSD, GBPUSD).

3. **Market Type Impact**:
   - FX Majors show larger skew adjustments
   - Commodities (XAUUSD, XAGUSD) show smaller adjustments but higher base probabilities

## II. Impact Analysis of Higher-Order Terms in Digital Option Pricing

First Order (EDS):


$$
\mathrm{Digital}(K) = -\frac{\partial \text{Call}}{\partial K} - \mathrm{Vega} \cdot \text{skew}
$$

Second Order:


$$
\begin{aligned}
\frac{d^2}{dK^2} \text{Call}(K, \sigma(K)) &= \frac{\partial^2 \text{Call}}{\partial K^2} + 2 \frac{\partial^2 \text{Call}}{\partial K \partial \sigma} \cdot \frac{\partial \sigma}{\partial K} \\
&+ \frac{\partial^2 \text{Call}}{\partial \sigma^2} \left(\frac{\partial \sigma}{\partial K}\right)^2 + \frac{\partial \text{Call}}{\partial \sigma} \frac{\partial^2 \sigma}{\partial K^2}
\end{aligned}
$$

### Currency-Specific Analysis (Q1 2024)

#### 1. EURUSD (January-March 2024)
- Short-term (1-day) impact: -0.08% to -0.10%
- Medium-term (10-day) impact: -0.01%
- Long-term (30-day) impact: 0.02%
- Key characteristics:
  * Strongest second-order effects in short-dated options
  * Vanna term dominates adjustments
  * Convexity effects minimal

#### 2. GBPUSD (January-March 2024)
- Short-term (1-day) impact: -0.06% to -0.09%
- Medium-term (10-day) impact: -0.01%
- Long-term (30-day) impact: 0.02%
- Key characteristics:
  * Similar pattern to EURUSD
  * Slightly lower second-order effects
  * More pronounced put-call asymmetry

#### 3. JPYUSD (January-March 2024)
- Short-term (1-day) impact: 0.00%
- Medium-term (10-day) impact: 0.00%
- Long-term (30-day) impact: 0.00%
- Key characteristics:
  * Minimal higher-order impacts across all maturities
  * Flatter volatility smile (wings: 1.04)
  * Lower risk reversals (-0.001/-0.002)
  * Base volatility range: 0.029-0.052
  * Most stable across all instruments
  * First order approximation highly accurate

#### 4. XAUUSD (January-March 2024)
- Short-term (1-day) impact: 0.00%
- Medium-term (10-day) impact: 0.00%
- Long-term (30-day) impact: 0.00%
- Key characteristics:
  * Steeper volatility smile (wings: 1.10)
  * Lower base volatility (0.03-0.05)
  * First order adjustments dominate
  * Minimal higher-order effects despite steep smile

#### 5. XAGUSD (January-March 2024)
- Short-term (1-day) impact: -0.01% to 0.01%
- Medium-term (10-day) impact: 0.00%
- Long-term (30-day) impact: 0.00%
- Key characteristics:
  * Moderate smile steepness (wings: 1.06)
  * Higher base volatility (0.11-0.15)
  * Small but measurable short-term impacts
  * Asymmetric put-call adjustments

### Comparative Analysis

#### FX vs Commodities
1. **Volatility Levels**:
   - FX: Moderate base volatility (0.04-0.06)
   - Gold: Lower base volatility (0.03-0.05)
   - Silver: Higher base volatility (0.11-0.15)

2. **Smile Characteristics**:
   - FX Majors: Standard smile (wings: 1.05-1.06)
   - JPY: Flatter smile (wings: 1.04)
   - Gold: Steeper smile (wings: 1.10)
   - Silver: Moderate smile (wings: 1.06)

3. **Higher Order Effects**:
   - FX Majors: Significant (-0.08% to -0.10%)
   - JPY: Minimal (0.00%)
   - Gold: Minimal (0.00%)
   - Silver: Small (-0.01% to 0.01%)

### Impact Analysis by Term

1. **Vanna Term**:


$$
-\mathrm{Vanna} \cdot \text{skew}
$$
   - Most significant for EURUSD and GBPUSD
   - Negligible for JPYUSD due to flatter smile
   - Dominates short-term adjustments

2. **Vomma Term**:


$$
-\frac{1}{2} \mathrm{Vomma} \cdot \text{skew}^2
$$
   - Secondary effect for FX majors
   - More significant in high volatility periods
   - Increases with maturity

3. **Convexity Term**:


$$
-\mathrm{Vega} \cdot \text{skew}'
$$
   - Smallest contribution overall
   - Most noticeable in short-dated options
   - More relevant for steeper smiles

### Key Findings

1. **Maturity Effect**:
   - Higher order impacts decrease with maturity
   - Most significant in 1-5 day options
   - Nearly vanish beyond 20 days

2. **Market Impact**:
   - FX majors (EUR, GBP): Notable second-order effects
   - JPY crosses: Minimal higher-order impacts
   - Impact correlates with smile steepness

3. **Volatility Regime**:
   - Higher base volatility increases second-order effects
   - Steeper smiles amplify adjustments
   - Market stress periods show larger impacts

### Key Conclusions

1. **Butterfly vs First Derivative Methods**:
   - Both methods show remarkable agreement across most market conditions
   - Differences are minimal (typically < 0.1%) for most maturities
   - Notable divergences only occur in specific cases:
     * Very short-dated options (1-5 days)
     * FX majors with steep volatility skews
     * High volatility environments (market stress periods)

2. **Higher-Order Terms Analysis**:
   - The Vanna*skew term ($-\mathrm{Vanna} \cdot \text{skew}$) dominates the correction:
     * Most significant impact on pricing accuracy
     * Particularly important for short-dated FX options
     * Critical for markets with pronounced volatility skews
   - Other higher-order terms (Vomma, convexity) show limited impact:
     * Typically < 0.01% effect on pricing
     * Mainly relevant in extreme market conditions
     * Can be safely omitted for most standard pricing applications

3. **Practical Implementation Recommendations**:
   - For standard pricing: First derivative method with Vanna*skew adjustment is sufficient
   - Additional terms warranted only for:
     * Options < 5 days to expiry
     * Markets with exceptionally steep volatility skews
     * Periods of significant market stress
