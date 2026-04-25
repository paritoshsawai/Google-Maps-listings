# Google Maps Listings

A polished local lead-generation app that scrapes Google Maps for businesses that do not have a website.

Built as a portfolio project, this app combines browser automation, a simple Python backend, a custom web UI, and live streaming progress updates so users can search by business type and location, watch results appear in real time, and export findings to CSV.

## Why This Project Stands Out

- Searches any business category in any location Google Maps understands
- Filters specifically for businesses with no website
- Includes both a CLI scraper and a browser-based interface
- Shows live scrape progress in a modal while listings are being collected
- Streams real discoveries to the UI instead of waiting only for the final response
- Uses no Google Maps API key

## Demo Highlights

- Enter a business type such as `takeaway`, `plumbers`, `dentists`, or `cafes`
- Enter any location such as `London`, `Manchester`, `Dubai`, or `New York`
- Start the scrape from the web UI
- Watch live progress updates:
  - search opening
  - consent handling
  - result scanning
  - individual business inspection
  - newly found no-website listings
- Review the final table and saved CSV output

## Tech Stack

- Python 3.11+
- Playwright
- Built-in Python HTTP server
- Server-Sent Events for live progress streaming
- Vanilla HTML, CSS, and JavaScript

## Project Structure

```text
Google-Maps-listings/
├── job_monitor/
│   ├── google_maps_agent.py
│   ├── google_maps_web.py
│   └── __init__.py
├── tests/
│   ├── test_google_maps_agent.py
│   ├── test_google_maps_web.py
│   └── __init__.py
├── pyproject.toml
├── README.md
└── .gitignore
```

## Setup

```bash
cd /Users/paritoshsawai/Documents/Scraper/Google-Maps-listings
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python3 -m playwright install chromium
```

## Run the Web App

```bash
run_google_maps_web
```

Then open the local URL printed in the terminal, usually:

```text
http://127.0.0.1:8000
```

If that port is busy, the app automatically uses the next available one.

## Run the CLI Scraper

```bash
run_google_maps_agent --query "takeaway" --location "London" --max-results 15
```

More examples:

```bash
run_google_maps_agent --query "plumbers" --location "Manchester" --max-results 20
run_google_maps_agent --query "dentists" --location "Dubai" --max-results 20
run_google_maps_agent --query "cafes" --location "New York" --max-results 20
```

If `--output-csv` is not provided, the app generates a filename from the location and query, for example:

```text
google_maps_london_takeaway.csv
google_maps_manchester_plumbers.csv
google_maps_dubai_dentists.csv
```

## Example Workflow

1. Launch the web UI with `run_google_maps_web`
2. Enter a business type and location
3. Click `Run Scraper`
4. Watch the live progress modal update as listings are discovered
5. Review the final results table
6. Open the generated CSV if needed

## How It Works

The scraper uses Playwright to automate the Google Maps website directly in a browser session.

At a high level:

1. Build a Google Maps search URL from the query and location
2. Open the search page and handle consent screens when needed
3. Collect place result URLs from the search panel
4. Visit each place detail page
5. Extract name, category, address, phone, website, and Maps URL
6. Keep only businesses where the website field is blank
7. Write results to CSV
8. Stream progress events to the web UI while the scrape is running

## Live Progress Experience

One of the strongest parts of this project is the real-time UI.

Instead of showing a static loading spinner, the app streams actual scrape events to the browser:

- scrape started
- current stage
- businesses opened
- listings found
- skipped businesses
- completion or error state

This makes the UI feel active, transparent, and much closer to a real user-facing product.

## No API Key Required

This project does not use:

- Google Maps API keys
- OpenAI API keys
- any paid Maps API integration

It works by automating the public Google Maps web interface through Playwright.

## Notes

- Google may show consent or anti-bot pages depending on region and behavior
- For manual debugging, a headed browser mode can be useful
- Broad queries like `businesses` are noisier than focused categories like `takeaway` or `plumbers`
- This project is best suited for local use, demos, and portfolio presentation

## Portfolio Framing

This project demonstrates:

- practical browser automation
- data extraction from dynamic pages
- live event streaming from backend to frontend
- clean local tooling and packaging
- thoughtful UI/UX for a technical workflow

## License

This project is currently shared as a portfolio/demo project. Add a license if you want to make reuse terms explicit on GitHub.
