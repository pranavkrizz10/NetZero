"""Tests for balance math and the remainder-safe equal split."""
from app.services.balances import equal_split


def test_equal_split_exact():
    shares = equal_split(1000, [1, 2, 3, 4])
    assert sum(shares.values()) == 1000
    assert all(v == 250 for v in shares.values())


def test_equal_split_with_remainder():
    # 1000 paise / 3 = 333.33 -> shares must still sum to exactly 1000.
    shares = equal_split(1000, [1, 2, 3])
    assert sum(shares.values()) == 1000
    # remainder of 1 paisa distributed to exactly one person
    assert sorted(shares.values()) == [333, 333, 334]


def test_equal_split_single():
    shares = equal_split(777, [5])
    assert shares == {5: 777}


def test_no_paise_created_or_lost_across_sizes():
    for total in (1, 7, 99, 100, 12345, 100000):
        for n in range(1, 8):
            shares = equal_split(total, list(range(n)))
            assert sum(shares.values()) == total
