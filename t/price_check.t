#!/usr/bin/perl

use Test::More;
use Test::FailWarnings;
use Test::Exception;

use Scalar::Util qw(looks_like_number);
use Format::Util::Numbers qw(roundnear);
use Pricing::Engine::EuropeanDigitalSlope;
use Date::Utility;
use Test::MockModule;

my $now = Date::Utility->new('2015-10-21')->plus_time_interval('3h');
my $multiplier = 1.0;

my $module = Test::MockModule->new('Pricing::Engine::EuropeanDigitalSlope');
$module->mock('_get_spread', sub {
        my $self = shift;
        my $args      = shift;
        my %volspread = (
            max => 0.0010,
            atm => 0.0069,
        );
        return $volspread{$args->{sought_point}};
    });

$module->mock('_get_volatility', sub {
        my $self = shift;
        my $vol_args = shift;

        my %vols = (
            101.00001 => 0.1000006,
            101       => 0.1001,
            100.99999 => 0.0999991,
            100.00001 => 0.01000008,
            100       => 0.01002,
            99.99999  => 0.00999985,
            99.00001  => 0.1500015,
            99        => 0.15001,
            98.99999  => 0.1499965,
        );
        
        return $multiplier * $vols{$vol_args->{strike}};
    });

$module->mock('_get_market_rr_bf', sub {
        return {
            ATM   => 0.01,
            RR_25 => 0.013,
            BF_25 => 0.014,
        }});

$module->mock('_get_overnight_tenor', sub { return 1; });
$module->mock('_get_atm_volatility', sub { return 0.14; });

sub _get_params {
    my $ct = shift;

    my %strikes = (
        CALL        => [100 * $multiplier],
        EXPIRYMISS  => [101 * $multiplier, 99 * $multiplier],
        EXPIRYRANGE => [101 * $multiplier, 99 * $multiplier],
    );
    return {
        volsurface        => {
            1 => {
                smile => {
                    25 => 0.18,
                    50 => 0.17,
                    75 => 0.24,
                },
                vol_spread => {
                    50 => 0.01,
                }
            },
            7 => {
                smile => {
                    25 => 0.19,
                    50 => 0.14,
                    75 => 0.15,
                },
                vol_spread => {
                    50 => 0.01,
                }
            },
        },
        priced_with       => 'numeraire',
        spot              => 100,
        strikes           => $strikes{$ct},
        date_start        => $now,
        date_pricing      => $now,
        date_expiry       => $now->plus_time_interval('10d'),
        discount_rate     => 0.02 * $multiplier,
        q_rate            => 0.003 * $multiplier,
        r_rate            => 0.026 * $multiplier,
        mu                => 0.024 * $multiplier,
        vol               => $ct eq ('CALL' or 'PUT') ? 0.1 : {high_barrier_vol => 0.1, low_barrier_vol => 0.16},
        payouttime_code   => 0,
        contract_type     => $ct,
        underlying_symbol => 'frxEURUSD',
        volsurface_recorded_date => $now,
        chronicle_reader  => undef,
    };
}

price_check('EXPIRYRANGE', 0.0011);
price_check('EXPIRYMISS', 1);
price_check('CALL', 0.4368);

$multiplier = 1.001;
price_check('EXPIRYRANGE', 0.3747);
price_check('EXPIRYMISS', 0.627);
price_check('CALL', 0.4882);

$multiplier = 0.97;
price_check('EXPIRYRANGE', 0.0408);
price_check('EXPIRYMISS', 0.9594);
price_check('CALL', 0.9696);

$multiplier = 0.99;
price_check('EXPIRYRANGE', 0.2653);
price_check('EXPIRYMISS', 0.7358);
price_check('CALL', 0.0006);

sub price_check {
    my $type = shift;
    my $expected = shift;

    my $pe = Pricing::Engine::EuropeanDigitalSlope->new(_get_params($type));
    is roundnear(0.0001, $pe->theo_probability), $expected, 'correct theo probability';
}

done_testing();
