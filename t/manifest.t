#!perl -T
use 5.006;
use strict;
use warnings;
use Test::More;
use Test::CheckManifest;

ok_manifest({exclude => ['.git']});
