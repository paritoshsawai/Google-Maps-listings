from __future__ import annotations

from pathlib import Path

from job_monitor.google_maps_web import create_scrape_run, find_available_port, scrape_listings, start_scrape_run


def test_scrape_listings_validates_inputs():
    try:
        scrape_listings(query="", location="London", max_results=10, output_csv=None)
    except ValueError as exc:
        assert "Business type is required." in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing query")


def test_scrape_listings_rejects_invalid_max_results():
    try:
        scrape_listings(query="takeaway", location="London", max_results=0, output_csv=None)
    except ValueError as exc:
        assert "Max results must be between 1 and 100." in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid max_results")


def test_scrape_listings_uses_scraper_and_returns_serialized_rows(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, config):
            captured["config"] = config

        def run(self):
            return [
                type(
                    "Lead",
                    (),
                    {
                        "name": "Sample Lead",
                        "category": "Takeaway",
                        "address": "1 Example Street",
                        "phone": "01234",
                        "website": "",
                        "google_maps_url": "https://www.google.com/maps/place/sample",
                        "query": "takeaway",
                        "location": "Manchester",
                    },
                )()
            ]

    monkeypatch.setattr("job_monitor.google_maps_web.GoogleMapsNoWebsiteAgent", FakeAgent)
    result = scrape_listings(
        query="takeaway",
        location="Manchester",
        max_results=12,
        output_csv=str(tmp_path / "custom.csv"),
    )

    config = captured["config"]
    assert config.query == "takeaway"
    assert config.location == "Manchester"
    assert config.max_results == 12
    assert config.output_csv_path == Path(tmp_path / "custom.csv")
    assert result["count"] == 1
    assert result["listings"][0]["name"] == "Sample Lead"


def test_create_scrape_run_validates_and_stores_payload():
    run = create_scrape_run(query="takeaway", location="London", max_results=10, output_csv=None)
    assert run.payload["query"] == "takeaway"
    assert run.payload["location"] == "London"
    assert run.payload["max_results"] == 10
    assert run.run_id


def test_start_scrape_run_returns_run_id(monkeypatch):
    started: dict[str, object] = {}

    class FakeThread:
        def __init__(self, target, args, daemon):
            started["target"] = target
            started["args"] = args
            started["daemon"] = daemon

        def start(self):
            started["started"] = True

    monkeypatch.setattr("job_monitor.google_maps_web.threading.Thread", FakeThread)
    result = start_scrape_run(query="takeaway", location="London", max_results=10, output_csv=None)
    assert result["run_id"]
    assert started["started"] is True


def test_find_available_port_returns_port():
    assert find_available_port("127.0.0.1", 8000) >= 8000
