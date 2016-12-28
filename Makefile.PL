use 5.006;
use strict;
use warnings;
use ExtUtils::MakeMaker;

WriteMakefile(
    NAME               => 'Pricing::Engine::EuropeanDigitalSlope',
    AUTHOR             => q{Binary.com <support@binary.com>},
    VERSION_FROM       => 'lib/Pricing/Engine/EuropeanDigitalSlope.pm',
    ABSTRACT_FROM      => 'lib/Pricing/Engine/EuropeanDigitalSlope.pm',
    PL_FILES           => {},
    MIN_PERL_VERSION   => 5.14.0,
    CONFIGURE_REQUIRES => {
        'ExtUtils::MakeMaker' => 0,
    },
    BUILD_REQUIRES => {
        'Test::More'         => 0,
        'Test::FailWarnings' => 0,
        'Test::Exception'    => 0,
        'Scalar::Util'       => 0,
        'Date::Utility'      => 0,
        'Test::Perl::Critic' => 0,
        'Format::Util::Numbers' => 0,
    },
    PREREQ_PM => {
        'Storable'                                              => 0,
        'List::Util'                                            => 0,
        'Date::Utility'                                         => 0,
        'YAML::XS'                                              => 0,
        'Cache::RedisDB'                                        => 0,
        'Finance::Asset'                                        => 0,
        'Format::Util::Numbers'                                 => 0,
        'JSON'                                                  => 0,
        'Quant::Framework'                                      => 0,
        'Math::Function::Interpolator'                          => 0,
        'Math::Business::BlackScholes::Binaries'                => 0,
        'Math::Business::BlackScholes::Binaries::Greeks::Vega'  => 0,
        'Math::Business::BlackScholes::Binaries::Greeks::Delta' => 0,
    },
    dist => {
        COMPRESS => 'gzip -9f',
        SUFFIX   => 'gz',
    },
    clean => {FILES => 'Pricing-Engine-EuropeanDigitalSlope-*'},
);
