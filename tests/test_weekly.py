from datetime import datetime, timedelta, timezone
import pytest
from radar_ia.weekly import plan, merge_queue

NOW = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)


def item(title="SDK update", **extra):
    return dict(title=title, url="https://aws.amazon.com/post/", published=NOW.isoformat(), **extra)


def test_wednesday_tools():
    result = plan([item()], NOW)
    assert result["theme"] == "Caixa de ferramentas"
    assert len(result["main"]) == 1


def test_market_waits_on_wednesday():
    assert len(plan([item("Tech hiring")], NOW)["waiting"]) == 1


def test_tuesday_prioritizes_market():
    tuesday = NOW - timedelta(days=1)
    entry = item("Tech hiring")
    entry["published"] = tuesday.isoformat()
    assert len(plan([entry], tuesday)["main"]) == 1


def test_local_weekday_is_used():
    saturday_utc = datetime(2026, 10, 31, 1, tzinfo=timezone.utc)
    assert plan([], saturday_utc)["theme"] == "Fechamento da semana"


def test_missing_date_excluded():
    entry = item()
    del entry["published"]
    assert len(plan([entry], NOW)["excluded"]) == 1


def test_old_article_excluded():
    entry = item()
    entry["published"] = (NOW - timedelta(days=8)).isoformat()
    assert len(plan([entry], NOW)["excluded"]) == 1


def test_preview_does_not_mark_used():
    entry = item()
    plan([entry], NOW)
    assert "used_in" not in entry


def test_merge_preserves_publication_history():
    old = item(used_in=["episode-1"])
    new = item()
    new["url"] += "?utm_source=rss"
    queue = merge_queue([old], [new])
    assert len(queue) == 1
    assert queue[0]["used_in"] == ["episode-1"]


def test_used_article_not_selected_as_new():
    assert not plan([item(used_in=["episode-1"])], NOW)["main"]


def test_naive_clock_rejected():
    with pytest.raises(ValueError):
        plan([], datetime(2026, 10, 28))


def test_incidental_tools_does_not_define_wednesday():
    entry = item("Prompt caching for agents", summary="Reuse the same tools and history")
    result = plan([entry], NOW)
    assert not result["main"]
    assert len(result["waiting"]) == 1


def test_specific_sdk_in_summary_explains_match():
    entry = item("Computer vision architecture", summary="Uses SageMaker SDK")
    result = plan([entry], NOW)
    assert "sdk" in result["main"][0]["reason"]


def test_friday_recap_separated_from_news():
    friday = NOW + timedelta(days=2)
    result = plan([item(used_in=["edition-1"])], friday)
    assert not result["main"]
    assert len(result["recap"]) == 1
