from app.interpreter.time_parser import hours_from_range


def test_normal_range():
    assert hours_from_range(1, 3) == [1, 2]


def test_equal_start_end():
    assert hours_from_range(5, 5) == []


def test_full_day():
    assert hours_from_range(0, 24) == list(range(24))


def test_wrap_around():
    assert hours_from_range(23, 2) == [0, 1, 23]


def test_single_hour():
    assert hours_from_range(12, 13) == [12]


def test_none_returns_empty():
    assert hours_from_range(None, 5) == []
    assert hours_from_range(5, None) == []


def test_sorted_output():
    result = hours_from_range(23, 2)
    assert result == sorted(result)
    assert 0 in result
    assert 23 in result


def test_large_overnight():
    result = hours_from_range(21, 3)
    assert sorted(result) == [0, 1, 2, 21, 22, 23]