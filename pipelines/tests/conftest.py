import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Tests never touch the real data/ directory or real API keys."""
    monkeypatch.setenv("HIRUP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HIRUP_MAP_EXTENT", "pilot")  # keep the small pilot grid in tests
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
    monkeypatch.delenv("WAQI_TOKEN", raising=False)
    return tmp_path / "data"
