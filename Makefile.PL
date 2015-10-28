use 5.006;
use strict;
use warnings;
use ExtUtils::MakeMaker;

BEGIN {
    eval "use File::ShareDir::Install;";
    $@ and die $@;
}

use File::ShareDir::Install;
install_share dist => "share";

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
        'Test::NoWarnings'   => 0,
        'Test::Exception'    => 0,
        'Scalar::Util'       => 0,
        'Date::Utility'      => 0,
        'Test::Perl::Critic' => 0,
    },
    PREREQ_PM => {
        'Storable'                                              => 0,
        'List::Util'                                            => 0,
        'Date::Utility'                                         => 0,
        'File::ShareDir'                                        => 0,
        'YAML::XS'                                              => 0,
        'Finance::Asset'                                        => 0,
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

{
    package MY;
    use File::ShareDir::Install qw(postamble);
}
