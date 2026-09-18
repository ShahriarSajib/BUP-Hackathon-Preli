from typing import List, Optional


def hours_from_range(start: Optional[int], end: Optional[int]) -> List[int]:
    """Convert a [start, end) half-open hour range into a sorted hour list.

    Supports ordinary ranges (1-3 -> [1, 2]) and overnight/wrap-around
    ranges (23-2 -> [0, 1, 23]). End is exclusive.
    """
    if start is None or end is None:
        return []
    try:
        start_i = int(round(float(start)))
        end_i = int(round(float(end)))
    except (TypeError, ValueError):
        return []

    if start_i == end_i:
        return []

    if start_i < end_i:
        hours = list(range(start_i, end_i))
    else:
        hours = list(range(start_i, 24)) + list(range(0, end_i))

    cleaned = [h for h in set(hours) if 0 <= h < 24]
    return sorted(cleaned)