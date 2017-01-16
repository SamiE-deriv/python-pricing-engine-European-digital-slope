use Test::More;
use Test::Exception;
use Test::Warnings;

use YAML::XS qw(LoadFile);
use Date::Utility;
use Format::Util::Numbers qw(roundnear);

use Pricing::Engine::EuropeanDigitalSlope;

my $dir = __FILE__ =~ s![^/]+$!raw_test_config!r;

opendir(DIR, $dir) or die "cannot open directory";
@docs = grep(/\.yml$/,readdir(DIR));

foreach $file (@docs) {
    my $data = LoadFile($dir . '/' .  $file);
    my $input = $data->{params};
    my $output = $data->{result};

    $_ = Date::Utility->new(0+$_)
        for (@{$input}{qw/date_start for_date date_pricing volsurface_recorded_date/});

    $input->{chronicle_reader} = Data::Chronicle::Reader->new({
            cache_reader => $input->{chronicle_hash},

        });

    my $actual_result = roundnear(0.0001, Pricing::Engine::EuropeanDigitalSlope->new($input)->theo_probability);
    is $actual_result, $output, "pricing result is as expected [ $actual_result vs $output] in $file";
}

done_testing;
