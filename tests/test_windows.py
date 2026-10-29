from datetime import datetime, timedelta, timezone
import pytest
from radar_ia.windows import collection_start

NOW = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)


def test_initial_window():
    assert collection_start(NOW, None)[0] == NOW - timedelta(days=7)


def test_monday_includes_weekend():
    monday = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
    friday = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
    assert collection_start(monday, friday.isoformat())[0] == friday - timedelta(hours=1)


def test_recovery_limited_and_reported():
    since, reason = collection_start(NOW, (NOW - timedelta(days=20)).isoformat())
    assert since == NOW - timedelta(days=7)
    assert "lacuna" in reason


@pytest.mark.parametrize("last", ["inválida", "2026-10-28T12:00:00", "2030-01-01T00:00:00+00:00"])
def test_invalid_checkpoint_rejected(last):
    with pytest.raises(ValueError):
        collection_start(NOW, last)


def test_multiple_sources_continue_after_failure(tmp_path, monkeypatch):
    import json
    import runpy
    from pathlib import Path
    example = Path(__file__).parents[1] / "examples" / "ler_rss.py"
    module = runpy.run_path(str(example))
    monkeypatch.chdir(tmp_path)
    sources = [{"name": "Falha", "url": "https://bad.example/feed", "domains": ["bad.example"]},
               {"name": "Boa", "url": "https://good.example/feed", "domains": ["good.example"]}]
    (tmp_path / "sources.json").write_text(json.dumps(sources))
    monkeypatch.setenv("RSS_SOURCES_FILE", "sources.json")
    monkeypatch.setenv("OUTPUT_DIR", "local-output")
    class FakeFetcher:
        def __init__(self, domains):
            self.bad = domains == ["bad.example"]
        def get(self, url):
            if self.bad:
                raise ValueError("falha simulada")
            return b"xml", url
        def close(self):
            pass
    from types import SimpleNamespace
    monkeypatch.setattr(module["feedparser"], "parse", lambda body: SimpleNamespace(entries=[{"title": "Sem data"}], bozo=False))
    module["main"].__globals__["Fetcher"] = FakeFetcher
    module["main"]()
    report = json.loads((tmp_path / "local-output" / "coleta.json").read_text())
    assert [s["status"] for s in report["sources"]] == ["erro", "ok"]
    assert len(report["rejected"]) == 1
    assert not (tmp_path / "local-output" / "edicoes.json").exists()
