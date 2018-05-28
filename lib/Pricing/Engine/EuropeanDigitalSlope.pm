package Pricing::Engine::EuropeanDigitalSlope;

use 5.010;
use Moose;
use Moose::Util::TypeConstraints;

use File::ShareDir ();
use Storable qw(dclone);
use List::Util qw(min max sum);
use YAML::XS qw(LoadFile);
use Finance::Asset;
use Math::Business::BlackScholesMerton::Binaries;
use Math::Business::BlackScholesMerton::NonBinaries;
use Math::Business::BlackScholes::Binaries::Greeks::Vega;
use Math::Business::BlackScholes::Binaries::Greeks::Delta;
use Machine::Epsilon;
use Quant::Framework::Underlying;
use Quant::Framework::VolSurface::Delta;
use Quant::Framework::VolSurface::Moneyness;
use Pricing::Engine::Markup::EqualTie;

subtype 'Pricing::Engine::EuropeanDigitalSlope::DateObject', as 'Date::Utility';
coerce 'Pricing::Engine::EuropeanDigitalSlope::DateObject', from 'Str', via { Date::Utility->new($_) };

=head1 NAME

Pricing::Engine::EuropeanDigitalSlope - A pricing model for european digital contracts.

=cut

our $VERSION = '1.25';

=head1 SYNOPSIS

  use Pricing::Engine::EuropeanDigitalSlope;

  my $now = time;
  my $probability = Pricing::Engine::EuropeanDigitalSlope->new(
      contract_type => 'CALL', # supports CALL, PUT, EXPIRYMISS and EXPIRYRANGE
      underlying_symbol => 'frxUSDJPY',
      spot => 120,
      strikes => [121], # an array reference of strikes. [$strike1, $strike2] for multiple strikes contracts
      date_start => $now, # epoch or Date::Utility object
      date_pricing => $now, # epoch or Date::Utility object
      date_expiry => $now + 86400, # epoch or Date::Utility object
      mu => 0.001,
      vol => 0.1, # 10% volatility
      discount_rate => 0.001, # payout currency rate
      r_rate => 0.0023,
      q_rate => 0.0021,
      payouttime_code => 0, # boolean. True if the contract payouts at hit, false otherwise
      priced_with => 'numeraire', # numeraire, base or quanto?
  )->theo_probability;

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

=head2 is_atm_contract

Is this At The Money contract?

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
    },
    commodities => {
        traded_market_markup => 1,
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
        qw(for_date volsurface volsurface_creation_date contract_type spot strikes vol date_start date_pricing
            date_expiry discount_rate mu payouttime_code q_rate r_rate priced_with underlying_symbol
            chronicle_reader is_atm_contract)
    ];
}

has [
    qw(volsurface volsurface_creation_date contract_type spot strikes vol
        discount_rate mu payouttime_code q_rate r_rate priced_with underlying_symbol
        chronicle_reader is_atm_contract)
    ] => (
    is       => 'ro',
    required => 1,
    );

has for_date => (
    is => 'ro',
);

has [qw(date_start date_pricing date_expiry)] => (
    is       => 'ro',
    isa      => 'Pricing::Engine::EuropeanDigitalSlope::DateObject',
    required => 1,
    coerce   => 1,
);

has debug_info => (
    is      => 'rw',
    default => sub { {} },
);

has error => (
    is       => 'rw',
    init_arg => undef,
    default  => '',
);

has apply_equal_tie_markup => (
    is         => 'ro',
    required => 1,
);

sub _validate {
    my $self = shift;

    my $contract_type = $self->contract_type;
    unless ($supported_types->{$contract_type}) {
        $self->error('Unsupported contract type [' . $contract_type . '] for ' . __PACKAGE__);
    }

    my @strikes = @{$self->strikes};
    my $err     = 'Barrier error for contract type [' . $contract_type . ']';
    if ($self->_two_barriers) {
        $self->error($err) if @strikes != 2;
    } else {
        $self->error($err) if @strikes != 1;
    }

    if ($self->date_expiry->is_before($self->date_start)) {
        $self->error('Date expiry is before date start');
    }
    return;
}

=head2 theo_probability

Final probability of the contract.

=cut

sub theo_probability {
    my $self = shift;

    $self->_validate;

    my $probability = $self->_base_probability + $self->_risk_markup;

    return max(0, min(1, $probability));
}

sub _base_probability {
    my $self = shift;

    $self->_validate;

    return 1 if $self->error;
    return max(0, min(1, $self->_calculate_probability));
}

=head2 _bs_probability

BlackScholes probability.

=cut

sub _bs_probability {
    my $self = shift;

    $self->_validate;

    return 1 if $self->error;

    my $bs_formula = _bs_formula_for($self->contract_type);
    my $params     = $self->_pricing_args;
    my $result     = max(0, $bs_formula->(_to_array($params)));

    return $result;
}

sub _get_volsurface {
    my $self = shift;

    my $underlying = Quant::Framework::Underlying->new({
            symbol           => $self->underlying_symbol,
            chronicle_reader => $self->chronicle_reader
        },
        $self->for_date
    );

    my $class = 'Quant::Framework::VolSurface::Delta';
    $class = 'Quant::Framework::VolSurface::Moneyness' if $underlying->volatility_surface_type eq 'moneyness';

    return $class->new({
        underlying       => $underlying,
        surface          => $self->volsurface,
        creation_date    => $self->volsurface_creation_date,
        chronicle_reader => $self->chronicle_reader,
        type             => $underlying->volatility_surface_type,
    });
}

=head2 risk_markup

Risk markup imposed by this engine.

=cut

sub _risk_markup {
    my $self = shift;

    return 0 if $self->error;

    my $underlying_config    = $self->_underlying_config;
    my $market               = $underlying_config->{market};
    my $market_markup_config = $markup_config->{$market};
    my $is_intraday          = $self->_is_intraday;

    my $risk_markup = 0;
    if ($market_markup_config->{'traded_market_markup'}) {
        # risk_markup is zero for forward_starting contracts due to complaints from Australian affiliates.
        return $risk_markup if ($self->_is_forward_starting);

        my %greek_params = %{$self->_pricing_args};

        my $vol_args = $self->_get_vol_expiry;
        $greek_params{vol} = $self->_get_atm_volatility($vol_args);

        # vol_spread_markup
        if (not $self->is_atm_contract) {
            my $vol_spread = $self->_get_spread({
                sought_point => 'max',
                day          => $self->_timeindays
            });

            my $bs_vega_formula   = _greek_formula_for('vega', $self->contract_type);
            my $bs_vega           = abs($bs_vega_formula->(_to_array(\%greek_params)));
            my $vol_spread_markup = min($vol_spread * $bs_vega, 0.7);
            $risk_markup += $vol_spread_markup;
            $self->debug_info->{risk_markup}{parameters}{vol_spread_markup} = $vol_spread_markup;
        }

        # spot_spread_markup
        if (not $is_intraday) {
            my $underlying_config  = $self->_underlying_config;
            my $spot_spread_size   = $underlying_config->{spot_spread_size} // 50;
            my $spot_spread_base   = $spot_spread_size * $underlying_config->{pip_size};
            my $bs_delta_formula   = _greek_formula_for('delta', $self->contract_type);
            my $bs_delta           = abs($bs_delta_formula->(_to_array(\%greek_params)));
            my $spot_spread_markup = max(0, min($spot_spread_base * $bs_delta, 0.01));
            $risk_markup += $spot_spread_markup;
            $self->debug_info->{risk_markup}{parameters}{spot_spread_markup} = $spot_spread_markup;
        }

        # Generally for indices, the minimum available tenor for smile is 30 days.
        # We use this to price short term contracts, so adding a 5% markup for the volatility uncertainty.
        if ($market_markup_config->{smile_uncertainty_markup} and $self->_timeindays < 7 and not $self->is_atm_contract) {
            my $smile_uncertainty_markup = 0.05;
            $risk_markup += $smile_uncertainty_markup;
            $self->debug_info->{risk_markup}{parameters}{smile_uncertainty_markup} = $smile_uncertainty_markup;
        }

        # risk_markup divided equally on both sides.
        $risk_markup /= 2;

        if ($self->apply_equal_tie_markup) {
            my $equal_tie_markup = Pricing::Engine::Markup::EqualTie->new(underlying_symbol => $self->underlying_symbol, timeinyears => $self->_timeinyears)->markup->amount;
            $risk_markup += $equal_tie_markup;
            $self->debug_info->{risk_markup}{parameters}{equal_tie_markup} = $equal_tie_markup;
        }

    }

    $self->debug_info->{risk_markup}{amount} = $risk_markup;

    return $risk_markup;
}

## PRIVATE ##

sub _underlying_config {
    my $self = shift;
    return Finance::Asset->instance->get_parameters_for($self->underlying_symbol);
}

sub _timeindays {
    my $self = shift;

    my $ind = ($self->date_expiry->epoch - $self->date_start->epoch) / 86400;
    # Preventing duration to go to zero when date_pricing == date_expiry
    # Zero duration will cause pricing calculation error
    # Capping duration at 730 days
    my $epsilon = machine_epsilon();
    $ind = min(730, max($epsilon, $ind));

    return $ind;
}

sub _timeinyears {
    my $self = shift;
    return $self->_timeindays / 365;
}

sub _is_forward_starting {
    my $self = shift;
    # 5 seconds is used as the threshold.
    # if pricing takes more than that, we are in trouble.
    return ($self->date_start->epoch - $self->date_pricing->epoch > 5) ? 1 : 0;
}

sub _two_barriers {
    my $self = shift;
    return (grep { $self->contract_type eq $_ } qw(EXPIRYMISS EXPIRYRANGE)) ? 1 : 0;
}

sub _is_intraday {
    my $self = shift;
    return ($self->_timeindays > 1) ? 0 : 1;
}

sub _calculate_probability {
    my ($self, $modified) = @_;

    my $contract_type = delete $modified->{contract_type} || $self->contract_type;

    my $probability;
    if ($contract_type eq 'EXPIRYMISS') {
        $probability = $self->_two_barrier_probability($modified);
    } elsif ($contract_type eq 'EXPIRYRANGE') {
        my $discounted_probability = exp(-$self->discount_rate * $self->_timeinyears);
        $self->debug_info->{discounted_probability} = $discounted_probability;
        $probability = $discounted_probability - $self->_two_barrier_probability($modified, $self->debug_info);
    } else {
        my $priced_with = $self->priced_with;
        my $params      = $self->_pricing_args;
        $params->{$_} = $modified->{$_} foreach keys %$modified;

        my (%debug_info, $calc_parameters);
        if ($priced_with eq 'numeraire') {
            ($probability, $calc_parameters) = $self->_calculate($contract_type, $params);
            $debug_info{base_probability}{amount}     = $probability;
            $debug_info{base_probability}{parameters} = $calc_parameters;
        } elsif ($priced_with eq 'quanto') {
            $params->{mu} = $self->r_rate - $self->q_rate;
            ($probability, $calc_parameters) = $self->_calculate($contract_type, $params);
            $debug_info{base_probability}{amount}     = $probability;
            $debug_info{base_probability}{parameters} = $calc_parameters;
        } elsif ($priced_with eq 'base') {
            my %cloned_params = %$params;
            # refer to formula 5.23 and 5.24 of castagna book page 149, both digital and vanilla option need to be priced in numeraire
            $cloned_params{mu}            = $self->r_rate - $self->q_rate;
            $cloned_params{discount_rate} = $self->r_rate;

            my $numeraire_prob;
            ($numeraire_prob, $calc_parameters) = $self->_calculate($contract_type, \%cloned_params);
            $debug_info{base_probability}{parameters}{numeraire_probability}{amount}     = $numeraire_prob;
            $debug_info{base_probability}{parameters}{numeraire_probability}{parameters} = $calc_parameters;
            my $vanilla_formula          = _bs_formula_for('vanilla_' . $contract_type);
            my $base_vanilla_probability = $vanilla_formula->(_to_array(\%cloned_params));
            $debug_info{base_probability}{parameters}{base_vanilla_probability}{amount}     = $base_vanilla_probability;
            $debug_info{base_probability}{parameters}{base_vanilla_probability}{parameters} = \%cloned_params;
            my $which_way = $contract_type eq 'CALL' ? 1 : -1;
            my $strike = $params->{strikes}->[0];
            $debug_info{base_probability}{parameters}{spot}{amount}   = $self->spot;
            $debug_info{base_probability}{parameters}{strike}{amount} = $strike;
            $probability = ($numeraire_prob * $strike + $base_vanilla_probability * $which_way) / $self->spot;
            $debug_info{base_probability}{amount} = $probability;
        } else {
            $self->error('Unrecognized priced_with[' . $priced_with . ']');
            $probability = 1;
        }

        $self->debug_info->{$contract_type} = \%debug_info;
    }

    return $probability;
}

sub _two_barrier_probability {
    my ($self, $modified) = @_;

    my ($low_strike, $high_strike) = sort { $a <=> $b } @{$self->strikes};

    my $high_vol  = $self->vol->{high_barrier_vol};
    my $call_prob = $self->_calculate_probability({
        contract_type => 'CALL',
        strikes       => [$high_strike],
        vol           => $high_vol,
        %$modified
    });

    my $low_vol  = $self->vol->{low_barrier_vol};
    my $put_prob = $self->_calculate_probability({
        contract_type => 'PUT',
        strikes       => [$low_strike],
        vol           => $low_vol,
        %$modified
    });

    return $call_prob + $put_prob;
}

sub _get_overnight_tenor {
    my $self = shift;

    return $self->_get_volsurface->_ON_day;
}

sub _get_spread {
    my ($self, $spread_args) = @_;

    return $self->_get_volsurface->get_spread($spread_args);
}

sub _get_market_rr_bf {
    my $self       = shift;
    my $first_term = shift;

    return $self->_get_volsurface->get_market_rr_bf($first_term);
}

sub _get_atm_volatility {
    my $self     = shift;
    my $vol_args = shift;

    $vol_args->{delta} = 50;
    return $self->_get_volatility($vol_args);
}

sub _get_volatility {
    my $self         = shift;
    my $vol_args     = shift;
    my $surface_data = shift;

    my $volsurface = $self->_get_volsurface;
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
    my ($self, $contract_type, $params) = @_;

    my %debug_info;
    my $bs_formula     = _bs_formula_for($contract_type);
    my @pricing_args   = _to_array($params);
    my $bs_probability = $bs_formula->(@pricing_args);
    $debug_info{bs_probability}{amount}     = $bs_probability;
    $debug_info{bs_probability}{parameters} = $params;

    my $slope_adjustment = 0;
    unless ($self->_is_forward_starting) {
        my $vanilla_vega_formula = _greek_formula_for('vega', 'vanilla_' . $contract_type);
        my $vanilla_vega = $vanilla_vega_formula->(@pricing_args);
        $debug_info{slope_adjustment}{parameters}{vanilla_vega}{amount}     = $vanilla_vega;
        $debug_info{slope_adjustment}{parameters}{vanilla_vega}{parameters} = $params;
        my $strike   = $params->{strikes}->[0];
        my $vol_args = {
            spot   => $self->spot,
            q_rate => $self->q_rate,
            r_rate => $self->r_rate,
            %{$self->_get_vol_expiry}};
        my $pip_size = $self->_underlying_config->{pip_size};
        # Move by pip size either way.
        $vol_args->{strike} = $strike - $pip_size;
        my $down_vol = $self->_get_volatility($vol_args);
        $vol_args->{strike} = $strike + $pip_size;
        my $up_vol = $self->_get_volatility($vol_args);
        my $slope = ($up_vol - $down_vol) / (2 * $pip_size);
        $debug_info{slope_adjustment}{parameters}{slope} = $slope;
        my $base_amount = $contract_type eq 'CALL' ? -1 : 1;
        $slope_adjustment = $base_amount * $vanilla_vega * $slope;

        if ($self->_get_first_tenor_on_surface > 7 and $self->_is_intraday) {
            $slope_adjustment = max(-0.03, min(0.03, $slope_adjustment));
        }
        $debug_info{slope_adjustment}{amount} = $slope_adjustment;
    }

    my $prob = $bs_probability + $slope_adjustment;

    return ($prob, \%debug_info);
}

sub _bs_formula_for {
    my $contract_type = shift;
    my $module = $contract_type =~ /^vanilla_/ ? 'Math::Business::BlackScholesMerton::NonBinaries' : 'Math::Business::BlackScholesMerton::Binaries';

    return $module->can(lc $contract_type) or die 'Could not price ' . $contract_type;
}

sub _greek_formula_for {
    my ($greek, $contract_type) = @_;
    my $formula_path = 'Math::Business::BlackScholes::Binaries::Greeks::' . ucfirst lc $greek . '::' . lc $contract_type;
    return \&$formula_path;
}

sub _pricing_args {
    my $self = shift;
    my %result = map { $_ => $self->$_ } @{$formula_args};

    #timeinyears does not exist in input parameters, we have to calculate it
    $result{_timeinyears} = $self->_timeinyears;
    $result{vol}          = $self->vol;

    return \%result;
}

sub _to_array {
    my ($params) = @_;
    my @array = map { ref $params->{$_} eq 'ARRAY' ? @{$params->{$_}} : $params->{$_} } @{$formula_args};
    return @array;
}

sub _get_first_tenor_on_surface {
    my $self = shift;

    my $original_surface = $self->volsurface;
    my $first_term = (sort { $a <=> $b } keys %$original_surface)[0];
    return $first_term;
}

sub _get_vol_expiry {
    my $self = shift;

    return {
        from => $self->date_start,
        to   => $self->date_expiry
    };
}

=head1 AUTHOR

Binary.com, C<< <support at binary.com> >>

=head1 SUPPORT

You can find documentation for this module with the perldoc command.

    perldoc Pricing::Engine::EuropeanDigitalSlope

=cut

no Moose;
__PACKAGE__->meta->make_immutable;
1;
