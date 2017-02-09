requires 'Date::Utility';
requires 'Finance::Asset';
requires 'List::Util';
requires 'Scalar::Util';
requires 'Math::Business::BlackScholes::Binaries';
requires 'Math::Business::BlackScholes::Binaries::Greeks::Delta';
requires 'Math::Business::BlackScholes::Binaries::Greeks::Vega';
requires 'Math::Function::Interpolator';
requires 'Storable';
requires 'YAML::XS';
requires 'perl', '5.014000';


on configure => sub {
    requires 'ExtUtils::MakeMaker';
};

on test => sub {
    requires 'Test::Exception';
    requires 'Test::FailWarnings';
    requires 'Test::More';
    requires 'Test::Perl::Critic';
};
