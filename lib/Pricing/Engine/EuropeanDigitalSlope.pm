package Pricing::Engine::EuropeanDigitalSlope;

use 5.010;

use File::ShareDir ();
use Storable qw(dclone);
use List::Util qw(min max sum);
use YAML::XS qw(LoadFile);
use Finance::Asset;
use Math::Function::Interpolator;
use Math::Business::BlackScholes::Binaries;
use Math::Business::BlackScholes::Binaries::Greeks::Vega;
use Math::Business::BlackScholes::Binaries::Greeks::Delta;
use Machine::Epsilon;

=head1 NAME

Pricing::Engine::EuropeanDigitalSlope - A pricing model for european digital contracts.

=head1 VERSION

Version 1.20

=cut

our $VERSION = '1.20';

=head1 SYNOPSIS

  use Pricing::Engine::EuropeanDigitalSlope;

  my $now = time;
  my $pe = Pricing::Engine::EuropeanDigitalSlope->new(
      contract_type => 'CALL' # supports CALL, PUT, EXPIRYMISS and EXPIRYRANGE
      underlying_symbol => 'frxUSDJPY',
      spot => 120,
      strikes => [121], # an array reference of strikes. [$strike1, $strike2] for multiple strikes contracts
      date_start => $now, # epoch or Date::Utility object
      date_pricing => $now, # epoch or Date::Utility object
      date_expiry => $now + 86400, # epoch or Date::Utility object
      mu => 0.001,
      vol => 0.1, 10% volatility
      discount_rate => 0.001, # payout currency rate
      r_rate => 0.0023,
      q_rate => 0.0021,
      payouttime_code => 0, # boolean. True if the contract payouts at hit, false otherwise
      priced_with => 'numeraire', # numeraire, base or quanto?
      market_data => $market_data, # hash reference of subroutine reference to fetch market data
      market_convention => $market_convention, # hash reference of subroutine reference to fetch market convention information
  );

  Final probability (base_probability + risk_markup)
  my $ask_probability = $pe->ask_probability;

=head1 ATTRIBUTES

=head2 contract_type

The contract that we wish to price.

=head2 spot

The spot value of the underlying instrument.

=head2 strikes

The strike{s) of the contract. (Array Reference)

=head2 discount_rate

The interest rate of the payout currency

=head2 mu

The drift of the underlying instrument.

=head2 vol

volatility of the underlying instrument.

=head2 q_rate

asset rate of the underlying instrument.

=head2 r_rate

quoted currency rate of the underlying instrument.

=head2 underlying_symbol

The symbol of the underlying instrument.

=head2 priced_with

Is this a base, numeraire or quanto contract.

=cut

=head2 date_start

The start time of the contract. Is a Date::Utility object.

=head2 date_pricing

The time of which the contract is priced. Is a Date::Utility object.

=head2 date_expiry

The expiration time of the contract. Is a Date::Utility object.

=cut

=head2 market_data

A hash reference of subroutine references to fetch market data.

- get_vol_spread: Expects a underlying_symbol, spread_type and timeindays as input. Returns a vol spread number.

my $vol_spread = $market_data->{get_vol_spread}->('atm', 7);

- get_volsurface_data: Expects nothing as input. Returns a hash reference of volsurface data.

my $surface_data = $market_data->{get_volsurface_data}->();

- get_market_rr_bf: Expects timeindays as input. Returns a hash reference of 25 risk reversal and 25 butterfly information.

my $market_rr_bf = $market_data->{get_market_rr_bf}->(7);

- get_volatility: Expects a hash refernce of volatility argument as input. Optional input: surface data. Returns a volatility number.

my $vol = $market_data->{get_volatility}->({delta => 50, from => $from, to => $to});
my $surface_data = {
    7 => {
        smile => {
            75 => 0.1,
            50 => 0.11,
            25 => 0.25
        }
    },
    14 => {
        smile => {
            75 => 0.12,
            50 => 0.21,
            25 => 0.21
        }
    },
};

# To get volatility with a modified surface.
$vol = $market_data->{get_volatility}->({delta => 50, from => $from, to => $to}, $surface_data);

- get_atm_volatility: Expects a hash reference as input. Returns a volatility number.

my $atm_vol = $market_data->{get_atm_volatility}->({expiry_date => Date::Utility->new});
$atm_vol = $market_data->{get_atm_volatility}->({days => 7});

=head2 market_convention

A hash reference of subroutine references to fetch market convention.

- get_rollover_time: Rollover time is of which a volsurface is expected to rollover to the next trading day. Expects a date as input. Returns Date::Utility object of the rollover time.

my $rollover_time = $market_data->{get_rollover_time}->(Date::Utility->new);

=cut

# required for now since market data and convention are still
# very much intact to BOM code

=head2 debug_information

Logging output.

=cut

=head2 error

Error thrown while calculating probability or markups.

=cut

# Contract types supported by this engine.
state $supported_types = {
    CALL        => 1,
    PUT         => 1,
    EXPIRYMISS  => 1,
    EXPIRYRANGE => 1
};

state $formula_args = [qw(spot strikes _timeinyears discount_rate mu vol payouttime_code)];

state $markup_config = {
    forex => {
        traded_market_markup => 1,
        end_of_day_markup    => 1,
        butterfly_markup     => 1
    },
    commodities => {
        traded_market_markup => 1,
        end_of_day_markup    => 1,
    },
    stocks => {
        traded_market_markup     => 1,
        smile_uncertainty_markup => 1,
    },
    indices => {
        traded_market_markup     => 1,
        smile_uncertainty_markup => 1,
    },
    volidx => {},
};

=head2 required_args

Required arguments for this engine to work.

=cut

sub required_args {
    return [
        qw(for_date volsurface volsurface_recorded_date contract_type spot strikes date_start date_pricing 
        date_expiry discount_rate mu payouttime_code q_rate r_rate priced_with underlying_symbol 
        market_convention chronicle_reader)
    ];
}

=head2 ask_probability

Final probability of the contract.

=cut

sub ask_probability {
    my $args = shift;
    my $debug_info = shift;

    my $contract_type = $args->{contract_type};
    unless ($supported_types->{$contract_type}) {
        $debug_info->{error} = 'Unsupported contract type [' . $contract_type . '] for ' . __PACKAGE__;
    }

    my @strikes = @{$args->{strikes}};
    my $err     = 'Barrier error for contract type [' . $contract_type . ']';
    if (_two_barriers($args)) {
        $debug_info->{error} = $err if @strikes != 2;
    } else {
        $debug_info->{error} = $err if @strikes != 1;
    }

    if ($args->{date_expiry}->is_before($args->{date_start})) {
        $debug_info->{error} = 'Date expiry is before date start';
    }

    my $probability = theo_probability($args, $debug_info) + _risk_markup($args, $debug_info);

    return max(0, min(1, $probability));
}

=head2 theo_probability

BlackScholes probability.

=cut

sub theo_probability {
    my $args = shift;
    my $debug_info = shift;

    return 1 if $debug_info->{error};
    my $result = max(0, min(1, _calculate_probability($args, {}, $debug_info)));
    return $result;
}

sub _get_volsurface {
    my $args = shift;

    my $underlying = Quant::Framework::Underlying->new({
            symbol           => $args->{underlying_symbol},
            chronicle_reader => $args->{chronicle_reder}
        }, $args->{for_date});

    my $class = 'Quant::Framework::VolSurface::Delta';
    $class = 'Quant::Framework::VolSurface::Moneyness' if $underlying->volatility_surface_type eq 'moneyness';

    return $class->new({
            underlying => $underlying,
            surface    => $args->{volsurface},
            recorded_date => $args->{volsurface_recorded_date},
            chronicle_reader => $args->{chronicle_reader},
            type => $underlying->volatility_surface_type,
        });
}

=head2 risk_markup

Risk markup imposed by this engine.

=cut

sub _risk_markup {
    my $args = shift;
    my $debug_info = shift;

    return 0 if $debug_info->{error};

    my $underlying_config = _underlying_config($args);
    my $market        = $underlying_config->{market};
    my $market_markup_config = $markup_config->{$market};
    my $is_intraday   = _is_intraday($args);

    my $risk_markup = 0;
    if ($market_markup_config->{'traded_market_markup'}) {
        # risk_markup is zero for forward_starting contracts due to complaints from Australian affiliates.
        return $risk_markup if (_is_forward_starting($args));

        my %greek_params = %{_pricing_args($args)};

        my $vol_args = _get_vol_expiry($args);
        $vol_args->{delta} = 50;
        $greek_params{vol} = _get_volatility($args, $vol_args);

        # vol_spread_markup
        my $spread_type = _is_atm_contract($args) ? 'atm' : 'max';
        my $vol_spread = _get_spread($args, {
            sought_point => $spread_type,
            day          => _timeindays($args)
        });

        my $bs_vega_formula   = _greek_formula_for('vega', $args->{contract_type});
        my $bs_vega           = abs($bs_vega_formula->(_to_array(\%greek_params)));
        my $vol_spread_markup = min($vol_spread * $bs_vega, 0.7);
        $risk_markup += $vol_spread_markup;
        $debug_info->{risk_markup}{parameters}{vol_spread_markup} = $vol_spread_markup;

        # spot_spread_markup
        if (not $is_intraday) {
            my $underlying_config = _underlying_config($args);
            my $spot_spread_size   = $underlying_config->{spot_spread_size} // 50;
            my $spot_spread_base   = $spot_spread_size * $underlying_config->{pip_size};
            my $bs_delta_formula   = _greek_formula_for('delta', $args->{contract_type});
            my $bs_delta           = abs($bs_delta_formula->(_to_array(\%greek_params)));
            my $spot_spread_markup = max(0, min($spot_spread_base * $bs_delta, 0.01));
            $risk_markup += $spot_spread_markup;
            $debug_info->{risk_markup}{parameters}{spot_spread_markup} = $spot_spread_markup;
        }

        # Generally for indices and stocks the minimum available tenor for smile is 30 days.
        # We use this to price short term contracts, so adding a 5% markup for the volatility uncertainty.
        if ($market_markup_config->{smile_uncertainty_markup} and _timeindays($args) < 7 and not _is_atm_contract($args)) {
            my $smile_uncertainty_markup = 0.05;
            $risk_markup += $smile_uncertainty_markup;
            $debug_info->{risk_markup}{parameters}{smile_uncertainty_markup} = $smile_uncertainty_markup;
        }

        # end of day market risk markup
        # This is added for uncertainty in volatilities during rollover period.
        # The rollover time for volsurface is set at NY 1700. However, we are not sure when the actual rollover
        # will happen. Hence we add a 5% markup to the price. This markup applies to forex and commodities only.
        if ($market_markup_config->{'end_of_day_markup'} and not _is_atm_contract($args) and _timeindays($args) <= 3) {
            my $ny_1600 = $args->{market_convention}->{get_rollover_time}->($args->{date_start})->minus_time_interval('1h');
            if ($ny_1600->is_before($args->{date_start}) or ($is_intraday and $ny_1600->is_before($args->{date_expiry}))) {
                my $eod_market_risk_markup = 0.05;    # flat 5%
                $risk_markup += $eod_market_risk_markup;
                $debug_info->{risk_markup}{parameters}{end_of_day_markup} = $eod_market_risk_markup;
            }
        }

        # This is added for the high butterfly condition where the overnight butterfly is higher than threshold (0.01),
        # We add the difference between then original probability and adjusted butterfly probability as markup.
        if ($market_markup_config->{'butterfly_markup'} and _timeindays($args) <= _get_overnight_tenor($args)) {
            my $butterfly_cutoff = 0.01;
            my $original_surface = _get_volsurface($args)->surface;
            my $first_term       = (sort { $a <=> $b } keys %$original_surface)[0];
            my $market_rr_bf     = _get_volsurface($args)->get_market_rr_bf($first_term);
            if ($first_term == _get_overnight_tenor($args) and $market_rr_bf->{BF_25} > $butterfly_cutoff) {
                my $original_bf = $market_rr_bf->{BF_25};
                my $original_rr = $market_rr_bf->{RR_25};
                my ($atm, $c25, $c75) = map { $original_surface->{$first_term}{smile}{$_} } qw(50 25 75);
                my $c25_mod             = $butterfly_cutoff + $atm + 0.5 * $original_rr;
                my $c75_mod             = $c25 - $original_rr;
                my $cloned_surface_data = dclone($original_surface);
                $cloned_surface_data->{$first_term}{smile}{25} = $c25_mod;
                $cloned_surface_data->{$first_term}{smile}{75} = $c75_mod;
                my $vol_args = {
                    strike => _two_barriers($args) ? $args->{spot} : $args->{strikes}->[0],
                    %{_get_vol_expiry($args)},
                };
                my $vol_after_butterfly_adjustment = _get_volatility($args, $vol_args, $cloned_surface_data);
                my $butterfly_adjusted_prob = _calculate_probability($args, {vol => $vol_after_butterfly_adjustment}, $debug_info);
                my $butterfly_markup = min(0.1, abs(_base_probability($args, $debug_info) - $butterfly_adjusted_prob));
                $risk_markup += $butterfly_markup;
                $debug_info->{risk_markup}{parameters}{butterfly_markup} = $butterfly_markup;
            }
        }

        # risk_markup divided equally on both sides.
        $risk_markup /= 2;
    }

    $debug_info->{risk_markup}{amount} = $risk_markup;

    return $risk_markup;
}

## PRIVATE ##

sub _underlying_config {
    my $args = shift;
    return Finance::Asset->instance->get_parameters_for($args->{underlying_symbol});
}

sub _timeindays {
    my $args = shift;

    my $ind = ($args->{date_expiry}->epoch - $args->{date_start}->epoch) / 86400;
    # Preventing duration to go to zero when date_pricing == date_expiry
    # Zero duration will cause pricing calculation error
    # Capping duration at 730 days
    my $epsilon = machine_epsilon();
    $ind = min(730, max($epsilon, $ind));

    return $ind;
}

sub _timeinyears {
    my $args = shift;
    return _timeindays($args) / 365;
}

sub _is_forward_starting {
    my $args = shift;
    # 5 seconds is used as the threshold.
    # if pricing takes more than that, we are in trouble.
    return ($args->{date_start}->epoch - $args->{date_pricing}->epoch > 5) ? 1 : 0;
}

sub _two_barriers {
    my $args = shift;
    return (grep { $args->{contract_type} eq $_ } qw(EXPIRYMISS EXPIRYRANGE)) ? 1 : 0;
}

sub _is_intraday {
    my $args = shift;
    return (_timeindays($args) > 1) ? 0 : 1;
}

sub _is_atm_contract {
    my $args = shift;
    return ($args->{_two_barriers} or $args->{spot} != $args->{strikes}->[0]) ? 0 : 1;
}

sub _calculate_probability {
    my ($args, $modified, $debug_info) = @_;

    my $contract_type = delete $modified->{contract_type} || $args->{contract_type};

    my $probability;
    if ($contract_type eq 'EXPIRYMISS') {
        $probability = _two_barrier_probability($args, $modified, $debug_info);
    } elsif ($contract_type eq 'EXPIRYRANGE') {
        my $discounted_probability = exp(-$args->{discount_rate} * _timeinyears($args));
        $debug_info->{discounted_probability} = $discounted_probability;
        $probability = $discounted_probability - _two_barrier_probability($args, $modified, $debug_info);
    } else {
        my $priced_with = $args->{priced_with};
        my $params      = _pricing_args($args);
        $params->{$_} = $modified->{$_} foreach keys %$modified;

        my (%debug_information, $calc_parameters);
        if ($priced_with eq 'numeraire') {
            ($probability, $calc_parameters) = _calculate($args, $contract_type, $params);
            $debug_information{base_probability}{amount}     = $probability;
            $debug_information{base_probability}{parameters} = $calc_parameters;
        } elsif ($priced_with eq 'quanto') {
            $params->{mu} = $args->{r_rate} - $args->{q_rate};
            ($probability, $calc_parameters) = _calculate($args, $contract_type, $params);
            $debug_information{base_probability}{amount}     = $probability;
            $debug_information{base_probability}{parameters} = $calc_parameters;
        } elsif ($priced_with eq 'base') {
            my %cloned_params = %$params;
            $cloned_params{mu}            = $args->{r_rate} - $args->{q_rate};
            $cloned_params{discount_rate} = $args->{r_rate};
            my $numeraire_prob;
            ($numeraire_prob, $calc_parameters) = _calculate($args, $contract_type, \%cloned_params);
            $debug_information{base_probability}{parameters}{numeraire_probability}{amount}     = $numeraire_prob;
            $debug_information{base_probability}{parameters}{numeraire_probability}{parameters} = $calc_parameters;
            my $vanilla_formula          = _bs_formula_for('vanilla_' . $contract_type);
            my $base_vanilla_probability = $vanilla_formula->(_to_array($params));
            $debug_information{base_probability}{parameters}{base_vanilla_probability}{amount}     = $base_vanilla_probability;
            $debug_information{base_probability}{parameters}{base_vanilla_probability}{parameters} = $params;
            my $which_way = $contract_type eq 'CALL' ? 1 : -1;
            my $strike = $params->{strikes}->[0];
            $debug_information{base_probability}{parameters}{spot}{amount}   = $args->{spot};
            $debug_information{base_probability}{parameters}{strike}{amount} = $strike;
            $probability = ($numeraire_prob * $strike + $base_vanilla_probability * $which_way) / $args->{spot};
            $debug_information{base_probability}{amount} = $probability;
        } else {
            $debug_info->{error} = 'Unrecognized priced_with[' . $priced_with . ']';
            $probability = 1;
        }

        $debug_info->{$contract_type} = \%debug_information;
    }

    return $probability;
}

sub _two_barrier_probability {
    my ($args, $modified, $debug_info) = @_;

    my ($low_strike, $high_strike) = sort { $a <=> $b } @{$args->{strikes}};

    my $vol_args = _get_vol_expiry($args);
    $vol_args->{strike} = $high_strike;
    my $high_vol  = _get_volatility($args, $vol_args);
    my $call_prob = _calculate_probability($args, {
        contract_type => 'CALL',
        strikes       => [$high_strike],
        vol           => $high_vol,
        %$modified
    }, $debug_info);

    $vol_args->{strike} = $low_strike;
    my $low_vol  = _get_volatility($args, $vol_args);
    my $put_prob = _calculate_probability($args, { 
        contract_type => 'PUT',
        strikes       => [$low_strike],
        vol           => $low_vol,
        %$modified
    }, $debug_info);

    return $call_prob + $put_prob;
}

sub _get_overnight_tenor {
    my $args = shift;

    return _get_volsurface($args)->_ON_day;
}

sub _get_vol_at_strike {
    my $args = shift;

    return $args->{vol} if ( exists $args->{vol} );

    my $vol_args     = {
        strike => $args->{strikes}->[0],
        q_rate => $args->{q_rate},
        r_rate => $args->{r_rate},
        spot   => $args->{spot},
        from   => $args->{date_start},
        to     => $args->{date_expiry},
    };

    if (scalar $args->{strikes} == 2 ) {
        $vol_args->{strike} = $args->{spot};
    }

    return _get_volsurface($args)->get_volatility($vol_args);
}

sub _get_spread {
    my ($args, $spread_args) = @_;

    return _get_volsurface($args)->get_spread($spread_args);
}

sub _get_volatility {
    my $args = shift;
    my $vol_args = shift;
    my $surface_data = shift;

    return $args->{vol} if ( exists $args->{vol} );

    my $volsurface = _get_volsurface($args);
    my $vol;
    if ($surface_data) {
        my $new_volsurface_obj = $volsurface->clone({surface_data => $surface_data});
        $vol = $new_volsurface_obj->get_volatility($vol_args);
    } else {
        $vol = $volsurface->get_volatility($vol_args);
    }

    return $vol;
}

sub _calculate {
    my ($args, $contract_type, $params) = @_;

    my %debug_information;
    my $bs_formula     = _bs_formula_for($contract_type);
    my @pricing_args   = _to_array($params);
    my $bs_probability = $bs_formula->(@pricing_args);
    $debug_information{bs_probability}{amount}     = $bs_probability;
    $debug_information{bs_probability}{parameters} = $params;

    my $slope_adjustment = 0;
    unless (_is_forward_starting($args)) {
        my $vanilla_vega_formula = _greek_formula_for('vega', 'vanilla_' . $contract_type);
        my $vanilla_vega = $vanilla_vega_formula->(@pricing_args);
        $debug_information{slope_adjustment}{parameters}{vanilla_vega}{amount}     = $vanilla_vega;
        $debug_information{slope_adjustment}{parameters}{vanilla_vega}{parameters} = $params;
        my $strike   = $params->{strikes}->[0];
        my $vol_args = {
            spot   => $args->{spot},
            q_rate => $args->{q_rate},
            r_rate => $args->{r_rate},
            %{_get_vol_expiry($args)}};
        my $pip_size = _underlying_config($args)->{pip_size};
        # Move by pip size either way.
        $vol_args->{strike} = $strike - $pip_size;
        my $down_vol = _get_volatility($args, $vol_args);
        $vol_args->{strike} = $strike + $pip_size;
        my $up_vol = _get_volatility($args, $vol_args);
        my $slope = ($up_vol - $down_vol) / (2 * $pip_size);
        $debug_information{slope_adjustment}{parameters}{slope} = $slope;
        my $base_amount = $contract_type eq 'CALL' ? -1 : 1;
        $slope_adjustment = $base_amount * $vanilla_vega * $slope;

        if (_get_first_tenor_on_surface($args) > 7 and _is_intraday($args)) {
            $slope_adjustment = max(-0.03, min(0.03, $slope_adjustment));
        }
        $debug_information{slope_adjustment}{amount} = $slope_adjustment;
    }

    my $prob = $bs_probability + $slope_adjustment;

    return ($prob, \%debug_information);
}

sub _bs_formula_for {
    my $contract_type = shift;
    my $formula_path  = 'Math::Business::BlackScholes::Binaries::' . lc $contract_type;
    return \&$formula_path;
}

sub _greek_formula_for {
    my ($greek, $contract_type) = @_;
    my $formula_path = 'Math::Business::BlackScholes::Binaries::Greeks::' . ucfirst lc $greek . '::' . lc $contract_type;
    return \&$formula_path;
}

sub _pricing_args {
    my $args = shift;
    my %args = map { $_ => $args->{$_} } @{$formula_args};

    #timeinyears does not exist in input parameters, we have to calculate it
    $args{_timeinyears} = _timeinyears($args);
    $args{vol} = _get_vol_at_strike($args);

    return \%args;
}

sub _to_array {
    my ($params) = @_;
    my @array = map { ref $params->{$_} eq 'ARRAY' ? @{$params->{$_}} : $params->{$_} } @{$formula_args};
    return @array;
}

sub _get_first_tenor_on_surface {
    my $args = shift;

    my $original_surface = $args->{volsurface}->{$args->{underlying_symbol}};
    my $first_term = (sort { $a <=> $b } keys %$original_surface)[0];
    return $first_term;
}

sub _get_vol_expiry {
    my $args = shift;

    return {
        from => $args->{date_start},
        to   => $args->{date_expiry}
    };
}

=head1 AUTHOR

Binary.com, C<< <support at binary.com> >>

=head1 SUPPORT

You can find documentation for this module with the perldoc command.

    perldoc Pricing::Engine::EuropeanDigitalSlope

=cut

1;
