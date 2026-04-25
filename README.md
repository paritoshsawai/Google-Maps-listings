# Google Maps Listings

This is a standalone Google Maps lead scraper project. It helps find businesses in a chosen location that do not have a website, exports them to CSV, and includes a simple web UI for running the scraper and watching live progress.

## Features

- Search any business category and location supported by Google Maps
- Export only listings with no website
- Auto-generate CSV filenames from query and location
- Simple browser UI with live scraping progress
- No API key required

## Setup

```bash
cd /Users/paritoshsawai/Documents/Scraper/Google-Maps-listings
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python3 -m playwright install chromium
```

## Run the scraper

```bash
run_google_maps_agent --query "takeaway" --location "London" --max-results 15
```

Examples:

```bash
run_google_maps_agent --query "plumbers" --location "Manchester" --max-results 20
run_google_maps_agent --query "dentists" --location "Dubai" --max-results 20
run_google_maps_agent --query "cafes" --location "New York" --max-results 20
```

If you do not pass `--output-csv`, the scraper writes to a generated file such as `google_maps_london_takeaway.csv` inside this project folder.

## Run the web UI

```bash
run_google_maps_web
```

Then open the local URL printed in the terminal, usually `http://127.0.0.1:8000` or the next free port.

## Notes

- The scraper uses Playwright to automate the Google Maps website directly.
- No Google Maps API key is used.
- Google may show consent or anti-bot screens, so `--headed` can help for manual runs.
