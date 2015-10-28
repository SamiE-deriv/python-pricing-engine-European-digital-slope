#!/usr/bin/perl
use 5.14.0;
use strict;
use warnings;
use Test::More tests => 1;
use Test::Pod::Coverage 1.00;

pod_coverage_ok('Pricing::Engine::EuropeanDigitalSlope');
