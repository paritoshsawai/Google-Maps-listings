from __future__ import annotations

from pathlib import Path

from job_monitor.google_maps_agent import (
    BusinessLead,
    GoogleMapsAgentConfig,
    GoogleMapsNoWebsiteAgent,
    build_search_url,
    default_output_csv_path,
    is_missing_website,
    normalize_place_url,
    slugify_filename_part,
)


def test_build_search_url_encodes_query_and_location():
    url = build_search_url("plumbers", "London")
    assert url == "https://www.google.com/maps/search/plumbers%20in%20London"


def test_normalize_place_url_strips_query_and_fragment():
    url = normalize_place_url(
        "https://www.google.com/maps/place/Test+Ltd/@51.1,0.1,17z/data=!3m1!4b1?entry=ttu#details"
    )
    assert url == "https://www.google.com/maps/place/Test+Ltd/@51.1,0.1,17z/data=!3m1!4b1"


def test_is_missing_website_treats_blank_as_missing():
    assert is_missing_website("")
    assert is_missing_website("   ")
    assert not is_missing_website("https://example.com")


def test_slugify_filename_part_normalizes_location_and_query():
    assert slugify_filename_part("New York") == "new_york"
    assert slugify_filename_part("Cafe & Bakery") == "cafe_bakery"


def test_default_output_csv_path_uses_location_and_query(tmp_path: Path):
    path = default_output_csv_path("dentists", "Dubai Marina", base_dir=tmp_path)
    assert path == tmp_path / "google_maps_dubai_marina_dentists.csv"


def test_agent_writes_csv_for_missing_website_leads(tmp_path: Path):
    output_path = tmp_path / "leads.csv"
    agent = GoogleMapsNoWebsiteAgent(
        GoogleMapsAgentConfig(
            query="electricians",
            location="London",
            output_csv_path=output_path,
            max_results=10,
        )
    )
    leads = [
        BusinessLead(
            name="North London Electric",
            category="Electrician",
            address="1 Example Street, London",
            phone="020 0000 0000",
            website="",
            google_maps_url="https://www.google.com/maps/place/North+London+Electric",
            query="electricians",
            location="London",
        )
    ]

    agent._write_csv(leads)

    content = output_path.read_text(encoding="utf-8")
    assert "North London Electric" in content
    assert "https://www.google.com/maps/place/North+London+Electric" in content


def test_agent_emits_completed_progress_event(tmp_path: Path):
    events: list[dict[str, object]] = []
    output_path = tmp_path / "leads.csv"
    agent = GoogleMapsNoWebsiteAgent(
        GoogleMapsAgentConfig(
            query="electricians",
            location="London",
            output_csv_path=output_path,
            max_results=10,
        ),
        progress_callback=events.append,
    )

    agent._write_csv(
        [
            BusinessLead(
                name="North London Electric",
                category="Electrician",
                address="1 Example Street, London",
                phone="020 0000 0000",
                website="",
                google_maps_url="https://www.google.com/maps/place/North+London+Electric",
                query="electricians",
                location="London",
            )
        ]
    )
    agent._emit_progress(
        {
            "event": "completed",
            "query": "electricians",
            "location": "London",
            "count": 1,
            "output_csv": str(output_path),
            "listings": [
                {
                    "name": "North London Electric",
                    "category": "Electrician",
                    "address": "1 Example Street, London",
                    "phone": "020 0000 0000",
                    "website": "",
                    "google_maps_url": "https://www.google.com/maps/place/North+London+Electric",
                    "query": "electricians",
                    "location": "London",
                }
            ],
        }
    )

    assert events[-1]["event"] == "completed"
    assert events[-1]["count"] == 1
