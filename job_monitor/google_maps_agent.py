from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlsplit, urlunsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class GoogleMapsAgentConfig:
    query: str = "businesses"
    location: str = "London"
    output_csv_path: Path | None = None
    max_results: int = 50
    headless: bool = True
    timeout_ms: int = 20000
    scroll_limit: int = 25
    user_agent: str = "Mozilla/5.0 (compatible; GoogleMapsNoWebsiteAgent/0.1)"

    @staticmethod
    def from_env() -> "GoogleMapsAgentConfig":
        query = os.getenv("GOOGLE_MAPS_QUERY", "businesses")
        location = os.getenv("GOOGLE_MAPS_LOCATION", "London")
        output_csv_raw = os.getenv("GOOGLE_MAPS_OUTPUT_CSV")
        return GoogleMapsAgentConfig(
            query=query,
            location=location,
            output_csv_path=Path(output_csv_raw) if output_csv_raw else default_output_csv_path(query, location),
            max_results=int(os.getenv("GOOGLE_MAPS_MAX_RESULTS", "50")),
            headless=os.getenv("GOOGLE_MAPS_HEADLESS", "true").lower() != "false",
            timeout_ms=int(os.getenv("GOOGLE_MAPS_TIMEOUT_MS", "20000")),
            scroll_limit=int(os.getenv("GOOGLE_MAPS_SCROLL_LIMIT", "25")),
            user_agent=os.getenv(
                "GOOGLE_MAPS_USER_AGENT",
                "Mozilla/5.0 (compatible; GoogleMapsNoWebsiteAgent/0.1)",
            ),
        )


@dataclass(frozen=True)
class BusinessLead:
    name: str
    category: str
    address: str
    phone: str
    website: str
    google_maps_url: str
    query: str
    location: str

    def csv_row(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


ProgressCallback = Callable[[dict[str, Any]], None]


def build_search_url(query: str, location: str) -> str:
    return f"https://www.google.com/maps/search/{quote(f'{query} in {location}')}"


def slugify_filename_part(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return slug.strip("_") or "results"


def default_output_csv_path(query: str, location: str, base_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    return base_dir / f"google_maps_{slugify_filename_part(location)}_{slugify_filename_part(query)}.csv"


def normalize_place_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def is_missing_website(website: str) -> bool:
    return not website.strip()


class GoogleMapsNoWebsiteAgent:
    def __init__(self, config: GoogleMapsAgentConfig, progress_callback: ProgressCallback | None = None) -> None:
        self._config = config
        self._progress_callback = progress_callback

    def run(self) -> list[BusinessLead]:
        leads: list[BusinessLead] = []
        seen_urls: set[str] = set()
        search_url = build_search_url(self._config.query, self._config.location)
        self._emit_progress(
            {
                "event": "started",
                "query": self._config.query,
                "location": self._config.location,
                "max_results": self._config.max_results,
            }
        )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self._config.headless)
            context = browser.new_context(
                locale="en-GB",
                user_agent=self._config.user_agent,
                viewport={"width": 1440, "height": 1280},
            )
            page = context.new_page()
            page.set_default_timeout(self._config.timeout_ms)
            try:
                self._emit_progress(
                    {
                        "event": "stage",
                        "stage": "opening_search",
                        "message": f"Opening Google Maps for {self._config.query} in {self._config.location}.",
                    }
                )
                page.goto(search_url, wait_until="domcontentloaded")
                self._dismiss_consent_if_present(page)
                page.wait_for_timeout(3000)
                result_urls = self._collect_result_urls(page)
                self._emit_progress(
                    {
                        "event": "stage",
                        "stage": "results_ready",
                        "message": f"Collected {len(result_urls)} place results to inspect.",
                        "candidate_count": len(result_urls),
                    }
                )
                scanned_count = 0
                for result_url in result_urls:
                    normalized_url = normalize_place_url(result_url)
                    if not normalized_url or normalized_url in seen_urls:
                        continue
                    seen_urls.add(normalized_url)
                    scanned_count += 1
                    self._emit_progress(
                        {
                            "event": "stage",
                            "stage": "opening_business",
                            "message": f"Opening business {scanned_count} of {len(result_urls)}.",
                            "scanned_count": scanned_count,
                            "accepted_count": len(leads),
                            "candidate_count": len(result_urls),
                            "google_maps_url": normalized_url,
                        }
                    )
                    lead = self._extract_lead(page, normalized_url)
                    if lead and is_missing_website(lead.website):
                        leads.append(lead)
                        self._emit_progress(
                            {
                                "event": "listing_found",
                                "message": f"Found {lead.name} with no website.",
                                "scanned_count": scanned_count,
                                "accepted_count": len(leads),
                                "candidate_count": len(result_urls),
                                "listing": asdict(lead),
                            }
                        )
                    elif lead:
                        self._emit_progress(
                            {
                                "event": "listing_skipped",
                                "message": f"Skipped {lead.name} because a website is present.",
                                "scanned_count": scanned_count,
                                "accepted_count": len(leads),
                                "candidate_count": len(result_urls),
                                "listing_name": lead.name,
                            }
                        )
                    if len(leads) >= self._config.max_results:
                        break
            finally:
                context.close()
                browser.close()

        self._write_csv(leads)
        self._emit_progress(
            {
                "event": "completed",
                "query": self._config.query,
                "location": self._config.location,
                "count": len(leads),
                "output_csv": str(
                    self._config.output_csv_path
                    or default_output_csv_path(self._config.query, self._config.location)
                ),
                "listings": [asdict(lead) for lead in leads],
            }
        )
        return leads

    def _emit_progress(self, payload: dict[str, Any]) -> None:
        if self._progress_callback is None:
            return
        self._progress_callback(payload)

    def _dismiss_consent_if_present(self, page: Page) -> None:
        button_labels = (
            "Reject all",
            "Accept all",
            "I agree",
        )
        if "consent.google.com" not in page.url and "Before you continue" not in page.title():
            return
        self._emit_progress(
            {
                "event": "stage",
                "stage": "consent",
                "message": "Handling Google consent screen.",
            }
        )
        for label in button_labels:
            try:
                button = page.get_by_role("button", name=label).first
                if button.is_visible(timeout=3000):
                    button.click(force=True)
                    page.wait_for_function(
                        "() => !window.location.hostname.includes('consent.google.com')",
                        timeout=10000,
                    )
                    page.wait_for_load_state("domcontentloaded")
                    page.wait_for_timeout(1500)
                    if "consent.google.com" not in page.url:
                        self._emit_progress(
                            {
                                "event": "stage",
                                "stage": "consent_complete",
                                "message": "Consent handled. Loading map results.",
                            }
                        )
                        return
            except PlaywrightError:
                continue
        try:
            page.locator("form button").last.click(force=True, timeout=3000)
            page.wait_for_function(
                "() => !window.location.hostname.includes('consent.google.com')",
                timeout=10000,
            )
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(1500)
            self._emit_progress(
                {
                    "event": "stage",
                    "stage": "consent_complete",
                    "message": "Consent handled. Loading map results.",
                }
            )
        except PlaywrightError:
            return

    def _collect_result_urls(self, page: Page) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        stagnant_rounds = 0
        warmup_rounds = 0

        for _ in range(self._config.scroll_limit):
            page.wait_for_timeout(1500)
            self._emit_progress(
                {
                    "event": "stage",
                    "stage": "scanning_results",
                    "message": "Scanning Google Maps results.",
                    "candidate_count": len(urls),
                }
            )
            snapshot = page.evaluate(
                """
                () => Array.from(
                  document.querySelectorAll('a[href*="/maps/place/"]')
                ).map((anchor) => anchor.href).filter(Boolean)
                """
            )
            current_urls = [normalize_place_url(item) for item in snapshot if isinstance(item, str)]
            new_items = [item for item in current_urls if item and item not in seen]
            for item in new_items:
                seen.add(item)
                urls.append(item)
                if len(urls) >= self._config.max_results * 3:
                    return urls

            if new_items:
                stagnant_rounds = 0
            else:
                if not urls and warmup_rounds < 4:
                    warmup_rounds += 1
                else:
                    stagnant_rounds += 1
                if stagnant_rounds >= 3:
                    break

            scrolled = page.evaluate(
                """
                () => {
                  const panel = document.querySelector('div[role="feed"]');
                  if (!panel) {
                    return false;
                  }
                  panel.scrollBy(0, panel.clientHeight * 0.9);
                  return true;
                }
                """
            )
            if not scrolled:
                page.mouse.wheel(0, 2500)

        return urls

    def _extract_lead(self, page: Page, result_url: str) -> BusinessLead | None:
        try:
            page.goto(result_url, wait_until="domcontentloaded")
            page.wait_for_timeout(1800)
            details = page.evaluate(
                """
                () => {
                  const text = (value) => (value || "").replace(/\\s+/g, " ").trim();
                  const firstText = (selectors) => {
                    for (const selector of selectors) {
                      const element = document.querySelector(selector);
                      const value = text(element?.innerText || element?.textContent || "");
                      if (value) {
                        return value;
                      }
                    }
                    return "";
                  };
                  const fieldFromAria = (labelPrefix) => {
                    const nodes = Array.from(document.querySelectorAll('button, a, div'));
                    for (const node of nodes) {
                      const label = text(node.getAttribute('aria-label') || "");
                      if (label && label.toLowerCase().startsWith(labelPrefix.toLowerCase())) {
                        return text(label.slice(labelPrefix.length));
                      }
                    }
                    return "";
                  };
                  const websiteElement =
                    document.querySelector('a[data-item-id="authority"]') ||
                    Array.from(document.querySelectorAll('a[href]')).find((node) => {
                      const aria = (node.getAttribute('aria-label') || '').toLowerCase();
                      const href = node.href || '';
                      return aria.startsWith('website:') || (!href.includes('google.') && /^https?:/i.test(href));
                    });
                  const website = websiteElement ? text(websiteElement.href || websiteElement.getAttribute('href') || "") : "";
                  return {
                    name: firstText(['h1', 'div[role="main"] h1']),
                    category: fieldFromAria('Category:') || firstText(['button[jsaction*="pane.rating.category"]', 'div.DkEaL']),
                    address: fieldFromAria('Address:'),
                    phone: fieldFromAria('Phone:'),
                    website,
                  };
                }
                """
            )
        except PlaywrightError:
            return None

        if not isinstance(details, dict):
            return None

        name = str(details.get("name", "")).strip()
        if not name:
            return None

        return BusinessLead(
            name=name,
            category=str(details.get("category", "")).strip(),
            address=str(details.get("address", "")).strip(),
            phone=str(details.get("phone", "")).strip(),
            website=str(details.get("website", "")).strip(),
            google_maps_url=result_url,
            query=self._config.query,
            location=self._config.location,
        )

    def _write_csv(self, leads: list[BusinessLead]) -> None:
        output_csv_path = self._config.output_csv_path or default_output_csv_path(
            self._config.query,
            self._config.location,
        )
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(BusinessLead.__dataclass_fields__.keys())
        with output_csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for lead in leads:
                writer.writerow(lead.csv_row())


def parse_args() -> GoogleMapsAgentConfig:
    env_config = GoogleMapsAgentConfig.from_env()
    parser = argparse.ArgumentParser(
        description="Scrape Google Maps search results and export businesses missing a website."
    )
    parser.add_argument("--query", default=env_config.query, help="Business type to search for, e.g. plumbers")
    parser.add_argument("--location", default=env_config.location, help="Location to search in")
    parser.add_argument(
        "--output-csv",
        default=None,
        help="CSV export path. Defaults to a filename generated from location and query.",
    )
    parser.add_argument("--max-results", type=int, default=env_config.max_results, help="Maximum missing-website leads")
    parser.add_argument("--timeout-ms", type=int, default=env_config.timeout_ms, help="Playwright timeout in ms")
    parser.add_argument("--scroll-limit", type=int, default=env_config.scroll_limit, help="Scroll attempts in results panel")
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run with a visible browser. Helpful if Google shows consent or bot checks.",
    )
    args = parser.parse_args()
    output_csv_path = Path(args.output_csv) if args.output_csv else default_output_csv_path(args.query, args.location)
    return GoogleMapsAgentConfig(
        query=args.query,
        location=args.location,
        output_csv_path=output_csv_path,
        max_results=args.max_results,
        headless=not args.headed,
        timeout_ms=args.timeout_ms,
        scroll_limit=args.scroll_limit,
        user_agent=env_config.user_agent,
    )


def main() -> int:
    config = parse_args()
    leads = GoogleMapsNoWebsiteAgent(config).run()
    print(
        "Completed Google Maps lead scrape: "
        f"query={config.query!r}, "
        f"location={config.location!r}, "
        f"missing_website_leads={len(leads)}, "
        f"output={config.output_csv_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
