
import pytest

from app.warehouses.models import Shelf
from app.core.enums import ShelfStatus


def create_test_shelf(status=ShelfStatus.ACTIVE):
    """Створює тестовий об'єкт полиці без запису в БД."""

    return Shelf(
        rack_id=1,
        code="S-TEST",
        qr="TEST-S-TEST",
        width=2.0,
        length=1.0,
        height=0.5,
        max_weight=500,
        status=status,
        is_occupied=False,
    )


def test_occupy_active_shelf():
    shelf = create_test_shelf()

    shelf.occupy()

    assert shelf.is_occupied is True
    assert shelf.status == ShelfStatus.ACTIVE


def test_occupy_inactive_shelf():
    shelf = create_test_shelf(ShelfStatus.INACTIVE)

    with pytest.raises(ValueError):
        shelf.occupy()

    assert shelf.is_occupied is False
    assert shelf.status == ShelfStatus.INACTIVE


def test_release_occupied_shelf():
    shelf = create_test_shelf()
    shelf.is_occupied = True

    shelf.release()

    assert shelf.is_occupied is False
    assert shelf.status == ShelfStatus.ACTIVE


def test_release_inactive_shelf():
    shelf = create_test_shelf(ShelfStatus.INACTIVE)
    shelf.is_occupied = True

    shelf.release()

    assert shelf.is_occupied is False
    assert shelf.status == ShelfStatus.INACTIVE
