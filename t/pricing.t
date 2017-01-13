use Test::More;
use Test::Exception;
use Test::Warnings;

use File::ShareDir ();
use YAML::XS qw(LoadFile);
use Date::Utility;
use Format::Util::Numbers qw(roundnear);

use Pricing::Engine::EuropeanDigitalSlope;

my $dir = File::ShareDir::dist_dir('Pricing-Engine-EuropeanDigitalSlope') . "/test";
opendir(DIR, $dir) or die "cannot open directory";
@docs = grep(/\.yml$/,readdir(DIR));

foreach $file (@docs) {
    my $data = LoadFile($dir . '/' .  $file);
    my $input = $data->{params};
    my $output = $data->{result};

    $input->{date_start} = Date::Utility->new(0+$input->{date_start});
    $input->{for_date} = Date::Utility->new(0+$input->{for_datec});
    $input->{date_pricing} = Date::Utility->new(0+$input->{date_pricing});
    $input->{volsurface_recorded_date} = Date::Utility->new(0+$input->{volsurface_recorded_date});
    $input->{chronicle_reader} = Data::Chronicle::Reader->new({
            cache_reader => $input->{chronicle_hash},

        });

    $DB::single=1;
    my $actual_result = roundnear(0.0001, Pricing::Engine::EuropeanDigitalSlope->new($input)->theo_probability);
    is $actual_result, $output, "pricing result is as expected [ $actual_result vs $output] in $file";
}

done_testing;
