from src.state import Position, StateStore


def test_position_open_and_reset():
    p = Position("KRW-BTC")
    assert p.is_open is False
    p.entry_price = 100
    p.day_high = 120
    assert p.is_open is True
    p.reset()
    assert p.is_open is False
    assert p.day_high == 0.0


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(str(path))
    positions = store.load(["KRW-BTC", "KRW-ETH"])
    positions["KRW-BTC"].entry_price = 50_000_000
    positions["KRW-BTC"].day_high = 51_000_000
    store.save(positions)

    reloaded = StateStore(str(path)).load(["KRW-BTC", "KRW-ETH"])
    assert reloaded["KRW-BTC"].entry_price == 50_000_000
    assert reloaded["KRW-BTC"].day_high == 51_000_000
    assert reloaded["KRW-ETH"].is_open is False


def test_load_missing_file_returns_fresh(tmp_path):
    store = StateStore(str(tmp_path / "nope.json"))
    positions = store.load(["KRW-BTC"])
    assert positions["KRW-BTC"].is_open is False


def test_load_corrupt_file_returns_fresh(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{ not json")
    positions = StateStore(str(path)).load(["KRW-BTC"])
    assert positions["KRW-BTC"].is_open is False
