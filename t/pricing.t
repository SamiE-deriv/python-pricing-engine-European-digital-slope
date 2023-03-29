use Test::More;
use Test::Exception;
use Test::Warnings;
use Test::MockModule;

use YAML::XS qw(LoadFile);
use Date::Utility;
use Format::Util::Numbers qw(roundnear);

use Data::Chronicle::Mock;
use Pricing::Engine::EuropeanDigitalSlope;
use Postgres::FeedDB::Spot::Tick;
use Quant::Framework::Utils::Test;

$ENV{TEST_DATABASE} = 1;
my $dir = 't/raw_test_config';
opendir(DIR, $dir) or die "cannot open directory";
@docs = grep(/\.yml$/, readdir(DIR));

foreach $file (@docs) {
    my $data   = LoadFile($dir . '/' . $file);
    my $input  = $data->{params};
    my $output = $data->{result};
    $input->{apply_equal_tie_markup} = 0;
    $_ = Date::Utility->new(0 + $_) for (@{$input}{qw/date_start for_date date_pricing volsurface_creation_date/});

    my ($chronicle_r, $chronicle_w) = Data::Chronicle::Mock::get_mocked_chronicle();

    Quant::Framework::Utils::Test::create_doc(
        'currency',
        {
            symbol           => $_,
            recorded_date    => $input->{date_start},
            chronicle_reader => $chronicle_r,
            chronicle_writer => $chronicle_w,
        }) for (qw/EUR USD EUR-USD USD-EUR/);

    my $qf_ul = Test::MockModule->new('Quant::Framework::Underlying');
    $qf_ul->mock('spot_tick', sub { return Postgres::FeedDB::Spot::Tick->new({epoch => $t->{ts}, quote => $input->{spot}}); } );

    $input->{chronicle_reader} = $chronicle_r;

    my $actual_result = roundnear(0.0001, Pricing::Engine::EuropeanDigitalSlope->new($input)->theo_probability);
    is $actual_result, $output, "pricing result is as expected [ $actual_result vs $output] in $file";
}

done_testing;
