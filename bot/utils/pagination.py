from __future__ import annotations


def total_pages(count: int, per_page: int) -> int:
    if count <= 0:
        return 1
    return (count + per_page - 1) // per_page


def clamp_page(page: int, pages: int) -> int:
    if pages <= 1:
        return 1
    return min(max(page, 1), pages)
