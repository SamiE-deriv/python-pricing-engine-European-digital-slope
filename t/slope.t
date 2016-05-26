#!/usr/bin/perl

use Test::More tests => 14;
use Test::NoWarnings;
use Test::Exception;

use Scalar::Util qw(looks_like_number);
use Pricing::Engine::EuropeanDigitalSlope;
use Date::Utility;

my $now = Date::Utility->new('2015-10-21')->plus_time_interval('3h');
# Hard-coded market_data & market_convention.
# We would not need once those classes are refactored and moved to stratopan.
my $market_data = {
    get_vol_spread => sub {
        my $args      = shift;
        my %volspread = (
            max => 0.0012,
            atm => 0.0022,
        );
        return $volspread{$args->{sought_point}};
    },
    get_volsurface_data => sub {
        return {
            1 => {
                smile => {
                    25 => 0.17,
                    50 => 0.16,
                    75 => 0.22,
                },
                vol_spread => {
                    50 => 0.01,
                }
            },
            7 => {
                smile => {
                    25 => 0.17,
                    50 => 0.152,
                    75 => 0.18,
                },
                vol_spread => {
                    50 => 0.01,
                }
            },
        };
    },
    get_market_rr_bf => sub {
        return {
            ATM   => 0.01,
            RR_25 => 0.012,
            BF_25 => 0.013,
        };
    },
    get_volatility => sub {
        my $args = shift;
        my %vols = (
            101.00001 => 0.1000005,
            101       => 0.1,
            100.99999 => 0.0999995,
            100.00001 => 0.01000005,
            100       => 0.01,
            99.99999  => 0.00999995,
            99.00001  => 0.1500005,
            99        => 0.15,
            98.99999  => 0.1499995,
        );
        return $vols{$args->{strike}};
    },
    get_atm_volatility => sub {
        return 0.11;
    },
    get_overnight_tenor => sub {
        return 1;
    },
};

my $market_convention = {
    calculate_expiry => sub {
        my ($start, $end) = @_;
        return int($end->days_between($start));
    },
    get_rollover_time => sub {
        # 22:00 GMT as rollover time
        return $now->truncate_to_day->plus_time_interval('22h');
    },
};

sub _get_params {
    my ($ct, $priced_with) = @_;

    my %discount_rate = (
        numeraire => 0.01,
        base      => 0.011,
        quanto    => 0.012,
    );
    my %strikes = (
        CALL        => [100],
        EXPIRYMISS  => [101, 99],
        EXPIRYRANGE => [101, 99],
    );
    return {
        priced_with       => $priced_with,
        spot              => 100,
        strikes           => $strikes{$ct},
        date_start        => $now,
        date_pricing      => $now,
        date_expiry       => $now->plus_time_interval('10d'),
        discount_rate     => $discount_rate{$priced_with},
        q_rate            => 0.002,
        r_rate            => 0.025,
        mu                => 0.023,
        vol               => 0.1,
        payouttime_code   => 0,
        contract_type     => $ct,
        underlying_symbol => 'frxEURUSD',
        market_data       => $market_data,
        market_convention => $market_convention,
    };
}

subtest 'CALL probability' => sub {
    my $pp = _get_params('CALL', 'numeraire');
    my $numeraire = Pricing::Engine::EuropeanDigitalSlope->new($pp);
    is $numeraire->priced_with, 'numeraire';
    ok looks_like_number($numeraire->theo_probability), 'probability looks like number';
    ok $numeraire->theo_probability <= 1, 'probability <= 1';
    ok $numeraire->theo_probability >= 0, 'probability >= 0';
    is scalar keys %{$numeraire->debug_information}, 1, 'only one set of debug information';
    ok exists $numeraire->debug_information->{CALL}, 'parameters for CALL';
    my $p   = $numeraire->debug_information->{CALL};
    my $ref = $p->{theo_probability}{parameters};
    is $ref->{bs_probability}{amount}, 0.511744030001155, 'correct bs_probability';
    is $ref->{bs_probability}{parameters}{vol},           0.1,   'correct vol for bs';
    is $ref->{bs_probability}{parameters}{mu},            0.023, 'correct mu for bs';
    is $ref->{bs_probability}{parameters}{discount_rate}, 0.01,  'correct discount_rate for bs';
    is $ref->{slope_adjustment}{parameters}{vanilla_vega}{amount}, 6.59860137878187, 'correct vanilla_vega';
    is $ref->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{vol},           0.1,   'correct vol for vanilla_vega';
    is $ref->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{mu},            0.023, 'correct mu for vanilla_vega';
    is $ref->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{discount_rate}, 0.01,  'correct discount_rate for vanilla_vega';

    $pp = _get_params('CALL', 'quanto');
    $quanto = Pricing::Engine::EuropeanDigitalSlope->new($pp);
    is $quanto->priced_with, 'quanto';
    ok looks_like_number($quanto->theo_probability), 'probability looks like number';
    ok $quanto->theo_probability <= 1, 'probability <= 1';
    ok $quanto->theo_probability >= 0, 'probability >= 0';
    is scalar keys %{$quanto->debug_information}, 1, 'only one set of debug information';
    ok exists $quanto->debug_information->{CALL}, 'parameters for CALL';
    $p   = $quanto->debug_information->{CALL};
    $ref = $p->{theo_probability}{parameters};
    is $ref->{bs_probability}{amount}, 0.511715990000614, 'correct bs_probability';
    is $ref->{bs_probability}{parameters}{vol},           0.1,   'correct vol for bs';
    is $ref->{bs_probability}{parameters}{mu},            0.023, 'correct mu for bs';
    is $ref->{bs_probability}{parameters}{discount_rate}, 0.012, 'correct discount_rate for bs';
    is $ref->{slope_adjustment}{parameters}{vanilla_vega}{amount}, 6.59823982148881, 'correct vanilla_vega';
    is $ref->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{vol},           0.1,   'correct vol for vanilla_vega';
    is $ref->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{mu},            0.023, 'correct mu for vanilla_vega';
    is $ref->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{discount_rate}, 0.012, 'correct discount_rate for vanilla_vega';

    $pp = _get_params('CALL', 'base');
    $base = Pricing::Engine::EuropeanDigitalSlope->new($pp);
    is $base->priced_with, 'base';
    ok looks_like_number($base->theo_probability), 'probability looks like number';
    ok $base->theo_probability <= 1, 'probability <= 1';
    ok $base->theo_probability >= 0, 'probability >= 0';
    is scalar keys %{$base->debug_information}, 1, 'only one set of debug information';
    ok exists $base->debug_information->{CALL}, 'parameters for CALL';
    $p = $base->debug_information->{CALL};
    my $ref = $p->{theo_probability}{parameters};
    is $ref->{numeraire_probability}{parameters}{bs_probability}{amount}, 0.511533767442995, 'correct bs_probability';
    is $ref->{numeraire_probability}{parameters}{bs_probability}{parameters}{vol},           0.1,   'correct vol for bs';
    is $ref->{numeraire_probability}{parameters}{bs_probability}{parameters}{mu},            0.023, 'correct mu for bs';
    is $ref->{numeraire_probability}{parameters}{bs_probability}{parameters}{discount_rate}, 0.025, 'correct discount_rate for bs';
    is $ref->{numeraire_probability}{parameters}{slope_adjustment}{parameters}{vanilla_vega}{amount}, 6.595890181924, 'correct vanilla_vega';
    is $ref->{numeraire_probability}{parameters}{slope_adjustment}{parameters}{vanilla_vega}{parameters}{vol}, 0.1,   'correct vol for vanilla_vega';
    is $ref->{numeraire_probability}{parameters}{slope_adjustment}{parameters}{vanilla_vega}{parameters}{mu},  0.023, 'correct mu for vanilla_vega';
    is $ref->{numeraire_probability}{parameters}{slope_adjustment}{parameters}{vanilla_vega}{parameters}{discount_rate}, 0.025,
        'correct discount_rate for vanilla_vega';
    is $ref->{base_vanilla_probability}{amount}, 0.692321231176061, 'correct base_vanilla_probability';
    is $ref->{base_vanilla_probability}{parameters}{mu},            0.023, 'correct mu for base_vanilla_probability';
    is $ref->{base_vanilla_probability}{parameters}{discount_rate}, 0.011, 'correct discount_rate for base_vanilla_probability';
};

subtest 'EXPIRYMISS probability' => sub {
    my $pp = _get_params('EXPIRYMISS', 'numeraire');
    my $numeraire = Pricing::Engine::EuropeanDigitalSlope->new($pp);
    is $numeraire->priced_with, 'numeraire';
    ok looks_like_number($numeraire->theo_probability), 'probability looks like number';
    ok $numeraire->theo_probability <= 1, 'probability <= 1';
    ok $numeraire->theo_probability >= 0, 'probability >= 0';
    is scalar keys %{$numeraire->debug_information}, 2, 'only one set of debug information';
    ok exists $numeraire->debug_information->{CALL}, 'parameters for CALL';
    ok exists $numeraire->debug_information->{PUT},  'parameters for PUT';
    my $call = $numeraire->debug_information->{CALL};
    is $call->{theo_probability}{amount}, 0.00063008065732667, 'correct tv for CALL';
    my $ref_call = $call->{theo_probability}{parameters};
    is $ref_call->{bs_probability}{amount}, 0.283800829253145, 'correct bs_probability';
    is $ref_call->{bs_probability}{parameters}{vol},           0.1,   'correct vol for bs';
    is $ref_call->{bs_probability}{parameters}{mu},            0.023, 'correct mu for bs';
    is $ref_call->{bs_probability}{parameters}{discount_rate}, 0.01,  'correct discount_rate for bs';
    is $ref_call->{bs_probability}{parameters}{strikes}->[0], 101, 'correct strike for bs';
    is $ref_call->{slope_adjustment}{parameters}{vanilla_vega}{amount}, 5.66341497191071, 'correct vanilla_vega';
    is $ref_call->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{vol},           0.1,   'correct vol for vanilla_vega';
    is $ref_call->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{mu},            0.023, 'correct mu for vanilla_vega';
    is $ref_call->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{discount_rate}, 0.01,  'correct discount_rate for vanilla_vega';
    is $ref_call->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{strikes}->[0], 101, 'correct strike for vanilla_vega';
    my $put = $numeraire->debug_information->{PUT};
    is $put->{theo_probability}{amount}, 0.637437489808321, 'correct tv for PUT';
    my $ref_put = $put->{theo_probability}{parameters};
    is $ref_put->{bs_probability}{amount}, 0.337968183618001, 'correct bs_probability';
    is $ref_put->{bs_probability}{parameters}{vol},           0.15,  'correct vol for bs';
    is $ref_put->{bs_probability}{parameters}{mu},            0.023, 'correct mu for bs';
    is $ref_put->{bs_probability}{parameters}{discount_rate}, 0.01,  'correct discount_rate for bs';
    is $ref_put->{bs_probability}{parameters}{strikes}->[0], 99, 'correct strike for bs';
    is $ref_put->{slope_adjustment}{parameters}{vanilla_vega}{amount}, 5.98938612380042, 'correct vanilla_vega';
    is $ref_put->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{vol},           0.15,  'correct vol for vanilla_vega';
    is $ref_put->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{mu},            0.023, 'correct mu for vanilla_vega';
    is $ref_put->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{discount_rate}, 0.01,  'correct discount_rate for vanilla_vega';
    is $ref_put->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{strikes}->[0], 99, 'correct strike for vanilla_vega';
};

subtest 'EXPIRYRANGE probability' => sub {
    my $pp = _get_params('EXPIRYRANGE', 'numeraire');
    my $numeraire = Pricing::Engine::EuropeanDigitalSlope->new($pp);
    is $numeraire->priced_with, 'numeraire';
    ok looks_like_number($numeraire->theo_probability), 'probability looks like number';
    ok $numeraire->theo_probability <= 1, 'probability <= 1';
    ok $numeraire->theo_probability >= 0, 'probability >= 0';
    is scalar keys %{$numeraire->debug_information}, 3, 'only one set of debug information';
    ok exists $numeraire->debug_information->{CALL},                   'parameters for CALL';
    ok exists $numeraire->debug_information->{PUT},                    'parameters for PUT';
    ok exists $numeraire->debug_information->{discounted_probability}, 'parameters for discounted_probability';
    is $numeraire->debug_information->{discounted_probability}, 0.999726064924327, 'correct discounted probability';
    my $call = $numeraire->debug_information->{CALL};
    is $call->{theo_probability}{amount}, 0.00063008065732667, 'correct tv for CALL';
    my $ref_call = $call->{theo_probability}{parameters};
    is $ref_call->{bs_probability}{amount}, 0.283800829253145, 'correct bs_probability';
    is $ref_call->{bs_probability}{parameters}{vol},           0.1,   'correct vol for bs';
    is $ref_call->{bs_probability}{parameters}{mu},            0.023, 'correct mu for bs';
    is $ref_call->{bs_probability}{parameters}{discount_rate}, 0.01,  'correct discount_rate for bs';
    is $ref_call->{bs_probability}{parameters}{strikes}->[0], 101, 'correct strike for bs';
    is $ref_call->{slope_adjustment}{parameters}{vanilla_vega}{amount}, 5.66341497191071, 'correct vanilla_vega';
    is $ref_call->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{vol},           0.1,   'correct vol for vanilla_vega';
    is $ref_call->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{mu},            0.023, 'correct mu for vanilla_vega';
    is $ref_call->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{discount_rate}, 0.01,  'correct discount_rate for vanilla_vega';
    is $ref_call->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{strikes}->[0], 101, 'correct strike for vanilla_vega';
    my $put = $numeraire->debug_information->{PUT};
    is $put->{theo_probability}{amount}, 0.637437489808321, 'correct tv for PUT';
    my $ref_put = $put->{theo_probability}{parameters};
    is $ref_put->{bs_probability}{amount}, 0.337968183618001, 'correct bs_probability';
    is $ref_put->{bs_probability}{parameters}{vol},           0.15,  'correct vol for bs';
    is $ref_put->{bs_probability}{parameters}{mu},            0.023, 'correct mu for bs';
    is $ref_put->{bs_probability}{parameters}{discount_rate}, 0.01,  'correct discount_rate for bs';
    is $ref_put->{bs_probability}{parameters}{strikes}->[0], 99, 'correct strike for bs';
    is $ref_put->{slope_adjustment}{parameters}{vanilla_vega}{amount}, 5.98938612380042, 'correct vanilla_vega';
    is $ref_put->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{vol},           0.15,  'correct vol for vanilla_vega';
    is $ref_put->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{mu},            0.023, 'correct mu for vanilla_vega';
    is $ref_put->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{discount_rate}, 0.01,  'correct discount_rate for vanilla_vega';
    is $ref_put->{slope_adjustment}{parameters}{vanilla_vega}{parameters}{strikes}->[0], 99, 'correct strike for vanilla_vega';
};

subtest 'unsupported contract_type' => sub {
    lives_ok {
        my $pp = _get_params('unsupported', 'numeraire');
        $pp->{strikes} = [100];
        my $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        is $slope->theo_probability,       1,                             'probabilility is 1';
        is $slope->bs_probability,    1,                             'probabilility is 1';
        ok $slope->error,             'has error';
        like $slope->error,           qr/Unsupported contract type/, 'correct error message';
        is $slope->risk_markup,       0,                             'risk_markup is zero';
    }
    'doesn\'t die if contract type is unsupported';
};

subtest 'unregconized priced_with' => sub {
    lives_ok {
        my $pp = _get_params('CALL', 'unregconized');
        $pp->{discount_rate} = 0.01;
        my $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        is $slope->theo_probability,       1,                            'probabilility is 1';
        is $slope->bs_probability,    1,                            'probabilility is 1';
        is $slope->risk_markup,       0,                            'risk_markup is zero';
        ok $slope->error,             'has error';
        like $slope->error,           qr/Unrecognized priced_with/, 'correct error message';
    }
    'doesn\'t die if priced_with is unregconized';
};

subtest 'barrier error' => sub {
    lives_ok {
        my $pp = _get_params('CALL', 'numeraire');
        $pp->{strikes} = [];
        my $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        ok $slope->error,             'has error';
        like $slope->error,           qr/Barrier error for/, 'correct error message';
        is $slope->theo_probability,       1, 'probabilility is 1';
        is $slope->bs_probability,    1, 'probabilility is 1';
        is $slope->risk_markup,       0, 'risk_markup is zero';
    }
    'doesn\'t die if strikes are undefined';

    lives_ok {
        my $pp = _get_params('EXPIRYMISS', 'numeraire');
        shift @{$pp->{strikes}};
        my $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        ok $slope->error,             'has error';
        like $slope->error,           qr/Barrier error for/, 'correct error message';
        is $slope->theo_probability,       1, 'probabilility is 1';
        is $slope->bs_probability,    1, 'probabilility is 1';
        is $slope->risk_markup,       0, 'risk_markup is zero';
    }
    'doesn\'t die if strikes are undefined';
};

subtest 'expiry before start' => sub {
    lives_ok {
        my $pp = _get_params('CALL', 'numeraire');
        $pp->{date_expiry} = Date::Utility->new('1999-01-02');
        my $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        ok $slope->error,             'has error';
        like $slope->error,           qr/Date expiry is before date start/, 'correct error message';
        is $slope->theo_probability,       1, 'probabilility is 1';
        is $slope->bs_probability,    1, 'probabilility is 1';
        is $slope->risk_markup,       0, 'risk_markup is zero';
    };
};

my %underlyings = (
    forex => 'frxEURUSD',
    indices => 'AEX',
    stocks => 'INICICIBC',
    commodities => 'frxXAUUSD',
);

subtest 'zero risk markup' => sub {
    my $pp = _get_params('CALL', 'numeraire');
    $pp->{underlying_symbol} = 'R_100';
    my $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
    ok !$slope->error,                'no error';
    ok !$slope->_is_forward_starting, 'non forward starting contract';
    is $slope->risk_markup, 0, 'risk markup is zero for random market';

    $pp = _get_params('CALL', 'numeraire');
    $pp->{date_start} = $now->plus_time_interval('6s');
    $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
    ok !$slope->error, 'no error';
    ok $slope->_is_forward_starting, 'forward starting contract';
    is $slope->risk_markup, 0, 'risk markup is 0 for forward starting contract';
};

# vol spread markup will always be applied.
# so will just check for it as we tests other markups.

subtest 'spot spread markup' => sub {
    my $pp = _get_params('CALL', 'numeraire');
    foreach my $market (keys %underlyings) {
        note("market: $market, $underlyings{$market}");
        $pp->{underlying_symbol} = $underlyings{$market};
        $pp->{date_expiry} = $now->plus_time_interval('24h');
        my $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        ok $slope->_is_intraday, 'is intraday';
        $slope->risk_markup;
        ok !exists $slope->debug_information->{risk_markup}{parameters}{spot_spread_markup}, 'spot spread markup will not be applied to intraday contract';
        ok exists $slope->debug_information->{risk_markup}{parameters}{vol_spread_markup}, 'vol spread markup will apply to intraday contract';
        # By right we should we testing for 1day 1 seconds here.
        # But due to FX convention of integer number of days, 2 days work for every market.
        $pp->{date_expiry} = $now->plus_time_interval('2d');
        $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        ok !$slope->_is_intraday, 'non intraday';
        $slope->risk_markup;
        ok exists $slope->debug_information->{risk_markup}{parameters}{spot_spread_markup}, 'spot spread markup will be applied to non intraday contract';
        ok exists $slope->debug_information->{risk_markup}{parameters}{vol_spread_markup}, 'vol spread markup will apply to non intraday contract';
        ok $slope->debug_information->{risk_markup}{parameters}{spot_spread_markup} > 0, 'spot spread markup is > 0';
    }
};

subtest 'smile uncertainty markup' => sub {
    my $pp = _get_params('CALL', 'numeraire');
    foreach my $market (qw(indices stocks)) {
        note("market: $market, $underlyings{$market}");
        $pp->{underlying_symbol} = $underlyings{$market};
        $pp->{date_expiry} = $now->plus_time_interval('6d');
        $pp->{strikes} = [100];
        my $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        ok $slope->_is_atm_contract, 'ATM contract';
        is $slope->_timeindays, 6, 'timeindays < 7';
        $slope->risk_markup;
        ok !exists $slope->debug_information->{risk_markup}{parameters}{smile_uncertainty_markup}, 'smile uncertainty markup will not be applied to less than 7 days ATM contract';
        $pp->{date_expiry} = $now->plus_time_interval('7d');
        $pp->{strikes} = [101];
        $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        ok !$slope->_is_atm_contract, 'non ATM contract';
        is $slope->_timeindays, 7, 'timeindays == 7';
        $slope->risk_markup;
        ok !exists $slope->debug_information->{risk_markup}{parameters}{smile_uncertainty_markup}, 'smile uncertainty markup will not be applied to 7 days non-ATM contract';
        $pp->{date_expiry} = $now->plus_time_interval('6d');
        $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        ok !$slope->_is_atm_contract, 'non ATM contract';
        is $slope->_timeindays, 6, 'timeindays < 7';
        $slope->risk_markup;
        ok exists $slope->debug_information->{risk_markup}{parameters}{smile_uncertainty_markup}, 'smile uncertainty markup will be applied to less than 7 days non-ATM contract';
        is $slope->debug_information->{risk_markup}{parameters}{smile_uncertainty_markup}, 0.05, 'smile uncertainty markup is 0.05';
    }

    foreach my $market (qw(forex commodities)) {
        note("market: $market, $underlyings{$market}");
        $pp->{underlying_symbol} = $underlyings{$market};
        $pp->{strikes} = [101];
        $pp->{date_expiry} = $now->plus_time_interval('6d');
        my $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        ok !$slope->_is_atm_contract, 'non ATM contract';
        is $slope->_timeindays, 6, 'timeindays < 7';
        $slope->risk_markup;
        ok !exists $slope->debug_information->{risk_markup}{parameters}{smile_uncertainty_markup}, 'smile uncertainty markup will not apply to less than 7 days non-ATM contract';
    }
};

# The condition for this markup is a little confusing.
# Trying to test this with best effort.
subtest 'end of day markup' => sub {
    my $pp = _get_params('CALL', 'numeraire');
    foreach my $market (qw(forex commodities)) {
        $pp->{_is_atm_contract} = 0;
        note("market: $market, $underlyings{$market}");
        $pp->{underlying_symbol} = $underlyings{$market};
        $pp->{date_expiry} = $now->plus_time_interval('4d');
        my $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        $slope->risk_markup;
        ok $slope->_timeindays > 3, 'timeindays > 3';
        ok !exists $slope->debug_information->{risk_markup}{parameters}{end_of_day_markup}, 'end of day markup will not be applied to duration more than 3 days';
        note("rollover time: 22:00, volatility uncertainty starts one hour before/after");
        note("contract start: " . $now->datetime);
        $pp->{date_expiry} = $now->plus_time_interval('17h59s');
        $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        $slope->risk_markup;
        ok $slope->_timeindays < 3, 'timeindays < 3';
        ok !exists $slope->debug_information->{risk_markup}{parameters}{end_of_day_markup}, 'end of day markup will not be applied to contract expiring before 21:00';
        $pp->{date_start} = $pp->{date_pricing} = $now->truncate_to_day->plus_time_interval('21h1s');
        $pp->{date_expiry} = $pp->{date_start}->plus_time_interval('3h');
        $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        $slope->risk_markup;
        ok exists $slope->debug_information->{risk_markup}{parameters}{end_of_day_markup}, 'end of day markup will be applied to intraday contract that starts after 21:00 GMT';
        note ('forced to non atm contract');
        $pp->{_is_atm_contract} = 1;
        $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        $slope->risk_markup;
        ok !exists $slope->debug_information->{risk_markup}{parameters}{end_of_day_markup}, 'end of day markup will not be applied to non atm contract';
    }

    delete $pp->{_is_atm_contract};
    foreach my $market (qw(stocks indices)) {
        note("market: $market, $underlyings{$market}");
        $pp->{underlying_symbol} = $underlyings{$market};
        $pp->{date_start} = $pp->{date_pricing} = $now->truncate_to_day->plus_time_interval('21h1s');
        $pp->{date_expiry} = $pp->{date_start}->plus_time_interval('3h');
        my $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        $slope->risk_markup;
        ok !exists $slope->debug_information->{risk_markup}{parameters}{end_of_day_markup}, 'end of day markup will not be applied to intraday contract that starts after 21:00 GMT';
    }
};

subtest 'butterfly markup' => sub {
    my $pp = _get_params('CALL', 'numeraire');
    foreach my $market (qw(stocks indices commodities)) {
        note("market: $market, $underlyings{$market}");
        $pp->{underlying_symbol} = $underlyings{$market};
        $pp->{date_expiry}       = $now->plus_time_interval('1d');
        $slope                   = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        $slope->risk_markup;
        ok !exists $slope->debug_information->{risk_markup}{parameters}{butterfly_markup},      'butterfly markup';
    }

    my $market = 'forex';
    note("market: $market, $underlyings{$market}");
    $pp->{underlying_symbol} = $underlyings{$market};
    $pp->{date_expiry}       = $now->plus_time_interval('1d');
    $slope                   = Pricing::Engine::EuropeanDigitalSlope->new($pp);
    $slope->risk_markup;
    ok exists $slope->debug_information->{risk_markup}{parameters}{butterfly_markup},      'butterfly markup';

    # no butterfly markup if overnight butterfly is smaller than 0.01
    $pp->{market_data}->{get_market_rr_bf} = sub {
        return {
            ATM   => 0.01,
            RR_25 => 0.012,
            BF_25 => 0.009,
        };
    };
    $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
    $slope->risk_markup;
    ok !exists $slope->debug_information->{risk_markup}{parameters}{butterfly_markup},      'butterfly markup will not be applied if the overnight butterfly is smaller than 0.01';

    $pp->{market_data} = $market_data;
    # no butterfly markup if there's no overnight tenor on volsurface
    $pp->{market_data}->{get_volsurface_data} = sub {
        return {
            7 => {
                smile => {
                    25 => 0.17,
                    50 => 0.16,
                    75 => 0.22,
                },
                vol_spread => {
                    50 => 0.01,
                }
            },
            14 => {
                smile => {
                    25 => 0.17,
                    50 => 0.152,
                    75 => 0.18,
                },
                vol_spread => {
                    50 => 0.01,
                }
            },
        };
    };
    $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
    $slope->risk_markup;
    ok !exists $slope->debug_information->{risk_markup}{parameters}{butterfly_markup},      'butterfly markup will not be applied if there is no overnight smile on the volatility surface';

    # no butterfly markup if not an overnight contract.
    $pp->{market_data} = $market_data;
    $pp->{date_expiry} = $now->plus_time_interval('2d');
    $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
    $slope->risk_markup;
    ok !exists $slope->debug_information->{risk_markup}{parameters}{butterfly_markup},      'butterfly markup will not be applied if it is not an overnight contract';
};

subtest 'zero duration' => sub {
    my $pp = _get_params('CALL', 'numeraire');
    $pp->{date_pricing} = $pp->{date_expiry};
    lives_ok {
        $slope = Pricing::Engine::EuropeanDigitalSlope->new($pp);
        cmp_ok $slope->date_expiry->epoch, "==", $slope->date_pricing->epoch, 'date_pricing == date_expiry';
        isnt $slope->_timeinyears, 0, 'timeinyears isnt zero';
    }
};
