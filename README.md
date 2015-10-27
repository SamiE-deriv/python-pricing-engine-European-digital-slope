# perl-Pricing-Engine-European-Digital-Slope
European Digital options Pricing Engine for Binary.com.

This model is a pricing algorithm for European Digital Options. European digital options have a payout of 1 or 0 at expiry, depending on the expiring conditions. The most common pricing method for european digitals is using tight-call spread, wherein vanilla options are used to replicate the payoff of the required digital option.

~~~~

Tight Call spread (static replica approach)

DC(K) = 1/(2*dK) [C(K-dK) - C(K+dK)]

Where, C(x) is price of vanilla call at strike 'x' and DC(x) is price of a digital call at strike 'K'. As dK->0, the value approaches the price of a digital call.

The static replica method is a model independent approach and allows us to define a digital options price simply by retrieving plain vanilla prices available in the market.

~~~~

To price digital call options, we use a model where the Black Scholes price (assuming a flat smile) is adjusted with the volatility skew observed in the market.

~~~~

In this model, the value of the digital call is equal to the value of a digital call in a flat volatility environment (with vol at strike K) plus Vega of a call option at strike K, times a factor which is the slope of the volatility smile at strike level
(dvol(K)/dK).

DC(S,K) = DC_flat_vol - Vega(S,K) * dvol(K)/dK

Where, DC_flat_vol is the BlackScholes price of a Digital Call (N(d2), where N(.) is the CDF and d2 is the standard expression for (ln(S/K)-(mu-vol^2)*t)/(vol*sqrt(t))) in a flat smile world.
Vega(S,K) is the vega of a vanilla call option struck at strike K.
~~~~

Since Vega of a European plain vanilla option is always positive, the digital call's value is abated in the presence of an upward-sloping volatility smile, whereas the reverse occurs when the volatility smile is downward sloping.

