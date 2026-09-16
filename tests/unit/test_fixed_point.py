from decimal import Decimal

from darwin.hermes.dataset import PRICE_SCALE, from_fixed_point, to_fixed_point


def test_exact_round_trip_typical_price():
    original = Decimal("4361.00000")
    fp = to_fixed_point(original)
    assert fp == 436_100_000
    assert from_fixed_point(fp) == original


def test_exact_round_trip_smallest_unit():
    original = Decimal("0.00001")
    fp = to_fixed_point(original)
    assert fp == 1
    assert from_fixed_point(fp) == original


def test_no_binary_float_rounding_artifact():
    # 4343.03500 cannot be represented exactly in binary float — this is
    # exactly the class of bug the fixed-point representation exists to avoid.
    original = Decimal("4343.03500")
    fp = to_fixed_point(original)
    assert from_fixed_point(fp) == original
    assert fp == 434_303_500


def test_scale_is_five_decimal_places():
    assert PRICE_SCALE == 100_000
