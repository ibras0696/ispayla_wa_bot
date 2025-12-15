import json

import pytest

from app.bot.handlers import buy


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch, tmp_path):
    """Очистить состояние фильтров и писать стейт в temp-файл."""
    buy._FILTER_STATE.clear()
    buy._LAST_CATALOG.clear()
    buy._LAST_DETAILS.clear()
    buy._LAST_VIEWED.clear()
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(buy, "_STATE_FILE", state_file, raising=False)
    yield
    buy._FILTER_STATE.clear()


def test_parse_range_variants():
    assert buy._parse_range("цена 100-200") == (100, 200)
    assert buy._parse_range("год 2020") == (2020, None)
    assert buy._parse_range("нет чисел") == (None, None)


def test_shift_page_and_persist(tmp_path):
    user = "tester"
    buy._reset_filters(user)
    buy._shift_page(user, 2)
    assert buy._FILTER_STATE[user]["page"] == 2


def test_persist_filter_state(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(buy, "_STATE_FILE", state_file, raising=False)
    user = "tester"
    buy._reset_filters(user)
    buy._update_price_filter(user, "цена 100000-200000")
    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert data[user]["min_price"] == 100000
    # эмулируем рестарт
    buy._FILTER_STATE.clear()
    buy._load_filter_state()
    assert buy._FILTER_STATE[user]["min_price"] == 100000
