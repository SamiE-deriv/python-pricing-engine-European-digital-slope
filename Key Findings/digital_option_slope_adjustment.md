# Taylor Expansion of Digital Option Price with Volatility Skew and Convexity

## 1. Setup

Let the Black-Scholes call price be a function of strike and implied volatility:

$$
\text{Call}(K, \sigma(K))
$$

where implied volatility depends on strike, $\sigma = \sigma(K)$.

A European digital call option can be understood as the limit of a butterfly spread as the spread width approaches zero:

$$
\mathrm{Digital}(K) = \lim_{\Delta K \to 0} \frac{\text{Call}(K, \sigma(K)) - \text{Call}(K + \Delta K, \sigma(K + \Delta K))}{\Delta K}
$$

Which in the limit gives us:

$$
\mathrm{Digital}(K) = -\frac{\partial}{\partial K} \text{Call}(K, \sigma(K))
$$

## 2. First Derivative (Digital Price with Skew Adjustment)

By the chain rule:

$$
\begin{aligned}
\frac{\partial}{\partial K} \text{Call}(K, \sigma(K)) &= 
\frac{\partial \text{Call}}{\partial K} + 
\frac{\partial \text{Call}}{\partial \sigma} \cdot \frac{\partial \sigma}{\partial K}
\end{aligned}
$$

Therefore:

$$
\mathrm{Digital}(K) = -\frac{\partial \text{Call}}{\partial K} - \mathrm{Vega} \cdot \text{skew}
$$

where:

- $\mathrm{Vega} = \frac{\partial \text{Call}}{\partial \sigma}$
- $\text{skew} = \frac{\partial \sigma}{\partial K}$

## 3. Second-order Expansion (Include Convexity Terms)

Differentiate again with respect to $K$ for higher accuracy (useful for local volatility or highly curved surfaces):

$$
\begin{aligned}
\frac{d^2}{dK^2} \text{Call}(K, \sigma(K)) &= 
\frac{\partial^2 \text{Call}}{\partial K^2} + 
2 \frac{\partial^2 \text{Call}}{\partial K \partial \sigma} \cdot \frac{\partial \sigma}{\partial K} \\
&+ \frac{\partial^2 \text{Call}}{\partial \sigma^2} \left(\frac{\partial \sigma}{\partial K}\right)^2 + 
\frac{\partial \text{Call}}{\partial \sigma} \frac{\partial^2 \sigma}{\partial K^2}
\end{aligned}
$$

**The digital option price including first and second order skew is:**

$$
\begin{aligned}
\mathrm{Digital}(K) \approx
&- \frac{\partial \text{Call}}{\partial K} \\
&- \mathrm{Vega} \cdot \text{skew} \\
&- \mathrm{Vanna} \cdot \text{skew} \\
&- \frac{1}{2} \mathrm{Vomma} \cdot \text{skew}^2 \\
&- \mathrm{Vega} \cdot \text{skew}'
\end{aligned}
$$

where:

- $\mathrm{Digital}_{\mathrm{BS}} = - \frac{\partial \text{Call}}{\partial K} = e^{-rT} N(d_2)$
- $\mathrm{Vega} = \frac{\partial \text{Call}}{\partial \sigma} = S_0 \sqrt{T} \phi(d_1)$
- $\mathrm{Vanna} = \frac{\partial^2 \text{Call}}{\partial K \partial \sigma} = -\frac{d_2}{K \sigma \sqrt{T}} \mathrm{Vega}$
- $\mathrm{Vomma} = \frac{\partial^2 \text{Call}}{\partial \sigma^2} = \mathrm{Vega} \cdot \frac{d_1 d_2}{\sigma}$
- $\text{skew} = \frac{\partial \sigma}{\partial K}$
- $\text{skew}' = \frac{\partial^2 \sigma}{\partial K^2}$

and:

- $d_1 = \frac{\ln(S_0/K) + (r + 0.5 \sigma^2) T}{\sigma \sqrt{T}}$
- $d_2 = d_1 - \sigma \sqrt{T}$
- $\phi(x)$ is the standard normal PDF

## 4. Final Explicit Formula

$$
\begin{aligned}
D(K, T) \approx
&\quad e^{-rT} N(d_2) \\
&- \mathrm{Vega} \cdot \text{skew} \\
&- \mathrm{Vanna} \cdot \text{skew} \\
&- \frac{1}{2} \mathrm{Vomma} \cdot \text{skew}^2 \\
&- \mathrm{Vega} \cdot \text{skew}'
\end{aligned}
$$

## 5. Parameter/Greek Definitions

| Symbol | Description |
|--------|-------------|
| $S_0$ | Spot price |
| $K$ | Strike |
| $T$ | Time to maturity (in years) |
| $r$ | Risk-free rate |
| $\sigma$ | Implied volatility at strike $K$ |
| $N(d_2)$ | Standard normal CDF at $d_2$ |
| $\phi(d_1)$ | Standard normal PDF at $d_1$ |

## 6. Notes

1. Most digital option pricing systems use only the first correction ($-\mathrm{Vega} \cdot \text{skew}$), but for high accuracy, the vanna, vomma, and skew slope ("convexity of skew") terms matter.

2. All Greeks should be evaluated at $(K, \sigma(K), T)$.

3. For flat vol surfaces, all skew and curvature terms vanish and the result reduces to the standard Black-Scholes digital price.

4. Convexity matters in option pricing because two volatility curves with identical ATM volatility and slope can still price options differently if they have different convexity, particularly for options far from ATM. The key measures are:

   - **Skew Slope**: First derivative of the IV curve, measuring rate of change of IV per strike:
   $\frac{\sigma_{up} - \sigma_{down}}{2\Delta K}$

   - **Skew Convexity**: Second derivative, measuring how the slope changes:
   $\frac{\sigma_{up} - 2\sigma_{mid} + \sigma_{down}}{(\Delta K)^2}$

   where $\sigma_{up}$, $\sigma_{mid}$, $\sigma_{down}$ are volatilities at strike ± ΔK, obtained from the volatility surface.

5. While convexity effects are small for ATM digital options, they become more significant for:
   - Longer maturities
   - Strikes far from current spot
   - Periods of market stress when volatility surfaces become more curved

## 7. Empirical Analysis

Analysis of volatility surface effects based on EUR/USD data from January 2024:

### 7.1 Volatility Smile Structure
- ATM volatility exhibits significant term structure, increasing with maturity
- Base probabilities (BS) show consistent increase with maturity:
  * 1-day: 27.87%
  * 30-day: 51.14%
- Vega scales with √T as expected:
  * 1-day: ~0.02
  * 30-day: ~0.125

### 7.2 Skewness (First Order) Effects
- First order adjustment (engine_prob - bs_prob) is consistently positive
- Impact by maturity:
  * 1-day: +3.71% (0.3158 - 0.2787)
  * 5-day: +2.40% (0.4382 - 0.4142)
  * 30-day: +1.20% (0.5234 - 0.5114)
- Relative impact decreases with maturity, indicating diminishing skew dominance

### 7.3 Convexity Analysis
- Convexity is calculated using finite differences of slopes:
  * Forward slope: (vol_up - vol_center) / pip_size
  * Backward slope: (vol_center - vol_down) / pip_size
  * Convexity: (slope_up - slope_down) / pip_size
- Impact is minimal across all maturities:
  * 1-day: 0.0000 (0.00% impact)
  * 5-day: 0.0000 (0.00% impact)
  * 10-day: 0.0000 (0.00% impact)
  * 20-day: 0.0000 (0.00% impact)
  * 30-day: 0.0000 (0.00% impact)
- Key observations:
  1. Convexity effect is negligible when measured directly from volatility surface
  2. Suggests volatility surface is nearly linear in strike around ATM
  3. Implies first-order skew adjustment captures most of the smile effect

### 7.4 Second/Third Order Terms
- Second order (Vanna) terms show small but systematic pattern with maturity:
  * 1-day: -0.0002 (-0.08% impact)
  * 5-day: -0.0001 (-0.02% impact)
  * 10-day: -0.0001 (-0.01% impact)
  * 20-day: 0.0000 (0.01% impact)
  * 30-day: 0.0001 (0.02% impact)
- Third order (Vomma) terms are consistently negligible (-0.0000) across all maturities

### 7.5 Total Impact Analysis
- First order (skew) effects dominate across all maturities:
  * 1-day: +3.71% (0.3158 - 0.2787)
  * 5-day: +2.40% (0.4382 - 0.4142)
  * 30-day: +1.20% (0.5234 - 0.5114)
- Higher order impacts are minimal:
  * 1-day: -0.08% total adjustment
  * 5-day: -0.02% total adjustment
  * 10-day: -0.01% total adjustment
  * 20-day: +0.01% total adjustment
  * 30-day: +0.02% total adjustment

This empirical analysis demonstrates that the first-order skew adjustment captures the vast majority of the volatility surface effect on digital option prices. Higher-order terms provide only minor refinements to the price, with their impact decreasing as maturity increases. This suggests that for practical purposes, the first-order correction is sufficient for most applications.

## 8. Put Option Analysis

For put options, the formulas are similar but with opposite signs due to the relationship between price and strike:

$$
\mathrm{Digital}_{\mathrm{Put}}(K) = \frac{\partial}{\partial K} \text{Put}(K, \sigma(K))
$$

Note the positive sign (vs negative for calls) because put value increases with strike. This leads to:

$$
\begin{aligned}
\mathrm{Digital}_{\mathrm{Put}}(K) \approx
&\quad e^{-rT} (1 - N(d_2)) \\
&+ \mathrm{Vega} \cdot \text{skew} \\
&+ \mathrm{Vanna} \cdot \text{skew} \\
&+ \frac{1}{2} \mathrm{Vomma} \cdot \text{skew}^2 \\
&+ \mathrm{Vega} \cdot \text{skew}'
\end{aligned}
$$

### 8.1 Empirical Results for Puts

Analysis of EUR/USD put options from January 2024:

#### Base Probabilities and First Order Effects
- Base probabilities (BS) show complementary behavior to calls:
  * 1-day: 72.12% (vs 27.87% for calls)
  * 30-day: 48.70% (vs 51.14% for calls)
- First order adjustments remain significant but with opposite sign:
  * 1-day: +3.71% (0.7583 - 0.7212)
  * 5-day: +2.39% (0.6094 - 0.5855)
  * 30-day: +1.20% (0.4990 - 0.4870)

#### Higher Order Effects
- Second order (Vanna) terms show opposite pattern to calls:
  * 1-day: +0.0002 (+0.03% impact)
  * 5-day: +0.0001 (+0.02% impact)
  * 10-day: +0.0001 (+0.01% impact)
  * 20-day: -0.0000 (-0.01% impact)
  * 30-day: -0.0001 (-0.02% impact)
- Third order and convexity terms remain minimal but with flipped signs
- Total higher order impact ranges from +0.03% at 1-day to -0.02% at 30-day

This analysis confirms that put-call parity is maintained in the higher order terms, with adjustments having similar magnitude but opposite signs compared to calls. The dominance of first-order effects and diminishing impact of higher-order terms holds true for both puts and calls.
