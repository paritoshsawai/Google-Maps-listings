from __future__ import annotations

import argparse
import json
import queue
import socket
import threading
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from job_monitor.google_maps_agent import (
    GoogleMapsAgentConfig,
    GoogleMapsNoWebsiteAgent,
    default_output_csv_path,
)


HTML_PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Google Maps Lead Scraper</title>
    <style>
      :root {
        --bg: #f5efe4;
        --card: rgba(255, 252, 246, 0.92);
        --ink: #1f2933;
        --muted: #667085;
        --line: rgba(31, 41, 51, 0.12);
        --accent: #14532d;
        --accent-2: #d97706;
        --danger: #b42318;
        --shadow: 0 18px 48px rgba(31, 41, 51, 0.12);
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(217, 119, 6, 0.18), transparent 28%),
          radial-gradient(circle at top right, rgba(20, 83, 45, 0.14), transparent 26%),
          linear-gradient(180deg, #f8f3ea 0%, #efe5d5 100%);
      }

      .shell {
        max-width: 1180px;
        margin: 0 auto;
        padding: 32px 20px 56px;
      }

      .hero {
        display: grid;
        gap: 20px;
        margin-bottom: 24px;
      }

      .eyebrow {
        margin: 0;
        font-size: 12px;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: var(--accent);
      }

      h1 {
        margin: 0;
        font-size: clamp(32px, 6vw, 64px);
        line-height: 0.95;
        font-weight: 600;
      }

      .subcopy {
        max-width: 720px;
        margin: 0;
        font-size: 18px;
        line-height: 1.5;
        color: var(--muted);
      }

      .card {
        background: var(--card);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.45);
        border-radius: 24px;
        box-shadow: var(--shadow);
      }

      .controls {
        padding: 22px;
      }

      form {
        display: grid;
        gap: 16px;
      }

      .grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
      }

      label {
        display: grid;
        gap: 8px;
        font-size: 14px;
        color: var(--muted);
      }

      input {
        width: 100%;
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 14px 16px;
        font-size: 16px;
        color: var(--ink);
        background: rgba(255, 255, 255, 0.88);
      }

      input:focus {
        outline: 2px solid rgba(20, 83, 45, 0.18);
        border-color: rgba(20, 83, 45, 0.4);
      }

      .actions {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
      }

      button {
        border: 0;
        border-radius: 999px;
        padding: 14px 22px;
        font-size: 15px;
        font-weight: 600;
        color: white;
        background: linear-gradient(135deg, var(--accent), #1f7a44);
        cursor: pointer;
      }

      .secondary {
        background: rgba(31, 41, 51, 0.08);
        color: var(--ink);
      }

      button[disabled] {
        cursor: wait;
        opacity: 0.7;
      }

      .hint {
        margin: 0;
        font-size: 14px;
        color: var(--muted);
      }

      .status {
        margin-top: 18px;
        padding: 14px 16px;
        border-radius: 16px;
        font-size: 15px;
        display: none;
      }

      .status.visible {
        display: block;
      }

      .status.info {
        background: rgba(20, 83, 45, 0.08);
        color: var(--accent);
      }

      .status.error {
        background: rgba(180, 35, 24, 0.08);
        color: var(--danger);
      }

      .results {
        margin-top: 24px;
        padding: 22px;
      }

      .results-head {
        display: flex;
        justify-content: space-between;
        gap: 16px;
        align-items: end;
        flex-wrap: wrap;
        margin-bottom: 16px;
      }

      .results-head h2 {
        margin: 0;
        font-size: 28px;
      }

      .results-head p {
        margin: 6px 0 0;
        color: var(--muted);
      }

      .meta {
        font-size: 14px;
        color: var(--muted);
      }

      .table-wrap {
        overflow: auto;
        border: 1px solid var(--line);
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.9);
      }

      table {
        width: 100%;
        border-collapse: collapse;
      }

      th, td {
        text-align: left;
        padding: 14px 16px;
        border-bottom: 1px solid var(--line);
        vertical-align: top;
      }

      th {
        font-size: 13px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
        background: rgba(31, 41, 51, 0.03);
      }

      td {
        font-size: 15px;
      }

      a {
        color: var(--accent);
      }

      .empty {
        padding: 28px 8px 8px;
        color: var(--muted);
        font-size: 16px;
      }

      .modal {
        position: fixed;
        inset: 0;
        display: none;
        place-items: center;
        padding: 20px;
        z-index: 50;
      }

      .modal.open {
        display: grid;
      }

      .modal-backdrop {
        position: absolute;
        inset: 0;
        background: rgba(31, 41, 51, 0.42);
        backdrop-filter: blur(8px);
        animation: fadeIn 220ms ease;
      }

      .modal-card {
        position: relative;
        width: min(760px, 100%);
        max-height: min(82vh, 820px);
        overflow: hidden;
        border-radius: 28px;
        background:
          radial-gradient(circle at top right, rgba(217, 119, 6, 0.12), transparent 28%),
          linear-gradient(180deg, rgba(255, 252, 246, 0.98), rgba(247, 241, 230, 0.98));
        box-shadow: 0 32px 90px rgba(16, 24, 40, 0.26);
        border: 1px solid rgba(255, 255, 255, 0.75);
        animation: popIn 260ms ease;
      }

      .modal-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 16px;
        padding: 22px 22px 0;
      }

      .modal-head h3 {
        margin: 0;
        font-size: 30px;
        line-height: 1;
      }

      .modal-head p {
        margin: 8px 0 0;
        color: var(--muted);
      }

      .close-button {
        width: 42px;
        height: 42px;
        padding: 0;
        border-radius: 50%;
      }

      .modal-body {
        padding: 20px 22px 22px;
      }

      .progress-chip {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        border-radius: 999px;
        padding: 10px 14px;
        background: rgba(20, 83, 45, 0.08);
        color: var(--accent);
        font-size: 14px;
        margin-bottom: 16px;
      }

      .pulse {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: var(--accent);
        box-shadow: 0 0 0 rgba(20, 83, 45, 0.45);
        animation: pulse 1.4s infinite;
      }

      .stats {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
        margin-bottom: 18px;
      }

      .stat {
        padding: 16px;
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.72);
        border: 1px solid var(--line);
      }

      .stat-label {
        display: block;
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
        margin-bottom: 8px;
      }

      .stat strong {
        font-size: 26px;
      }

      .activity {
        border: 1px solid var(--line);
        border-radius: 20px;
        background: rgba(255, 255, 255, 0.88);
        overflow: hidden;
      }

      .activity-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 16px 18px;
        border-bottom: 1px solid var(--line);
      }

      .activity-head h4 {
        margin: 0;
        font-size: 18px;
      }

      .activity-feed {
        max-height: 340px;
        overflow: auto;
      }

      .activity-item {
        padding: 14px 18px;
        border-bottom: 1px solid var(--line);
        animation: slideUp 220ms ease;
      }

      .activity-item:last-child {
        border-bottom: 0;
      }

      .activity-kind {
        display: inline-block;
        margin-bottom: 6px;
        font-size: 11px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--accent-2);
      }

      .activity-item strong {
        display: block;
        font-size: 18px;
        margin-bottom: 4px;
      }

      .activity-item p {
        margin: 0;
        color: var(--muted);
        font-size: 14px;
        line-height: 1.45;
      }

      .modal-foot {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: center;
        margin-top: 16px;
        flex-wrap: wrap;
      }

      .modal-message {
        color: var(--muted);
        font-size: 14px;
      }

      .hidden {
        display: none;
      }

      @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
      }

      @keyframes popIn {
        from { opacity: 0; transform: translateY(14px) scale(0.98); }
        to { opacity: 1; transform: translateY(0) scale(1); }
      }

      @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(20, 83, 45, 0.4); }
        70% { box-shadow: 0 0 0 12px rgba(20, 83, 45, 0); }
        100% { box-shadow: 0 0 0 0 rgba(20, 83, 45, 0); }
      }

      @keyframes slideUp {
        from { opacity: 0; transform: translateY(6px); }
        to { opacity: 1; transform: translateY(0); }
      }

      @media (max-width: 900px) {
        .grid {
          grid-template-columns: 1fr 1fr;
        }
      }

      @media (max-width: 640px) {
        .shell {
          padding: 20px 14px 40px;
        }

        .grid,
        .stats {
          grid-template-columns: 1fr;
        }

        h1 {
          line-height: 1;
        }
      }
    </style>
  </head>
  <body>
    <main class="shell">
      <section class="hero">
        <p class="eyebrow">Lead Finder</p>
        <h1>Scrape Google Maps listings without websites.</h1>
        <p class="subcopy">
          Enter a business type and any location in the world, run the scraper,
          and review the matching listings right here in the browser.
        </p>
      </section>

      <section class="card controls">
        <form id="scrape-form">
          <div class="grid">
            <label>
              Business Type
              <input id="query" name="query" value="takeaway" placeholder="takeaway, plumbers, dentists" required>
            </label>
            <label>
              Location
              <input id="location" name="location" value="London" placeholder="London, Dubai, New York" required>
            </label>
            <label>
              Max Results
              <input id="max_results" name="max_results" type="number" min="1" max="100" value="15" required>
            </label>
            <label>
              Output File Name
              <input id="output_csv" name="output_csv" placeholder="Optional custom CSV path">
            </label>
          </div>
          <div class="actions">
            <button id="submit-button" type="submit">Run Scraper</button>
            <p class="hint">Tip: focused categories usually work better than broad searches like "businesses".</p>
          </div>
        </form>
        <div id="status" class="status info"></div>
      </section>

      <section class="card results">
        <div class="results-head">
          <div>
            <h2>Listings</h2>
            <p id="summary">No scrape has been run yet.</p>
          </div>
          <div id="meta" class="meta"></div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Category</th>
                <th>Address</th>
                <th>Phone</th>
                <th>Maps</th>
              </tr>
            </thead>
            <tbody id="results-body">
              <tr><td class="empty" colspan="5">Run a scrape to see listings here.</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </main>

    <div id="progress-modal" class="modal" aria-hidden="true">
      <div class="modal-backdrop"></div>
      <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div class="modal-head">
          <div>
            <h3 id="modal-title">Scraping in progress</h3>
            <p id="modal-subtitle">Watching Google Maps and collecting live results.</p>
          </div>
          <button id="modal-close" class="secondary close-button" type="button">×</button>
        </div>
        <div class="modal-body">
          <div class="progress-chip">
            <span class="pulse"></span>
            <span id="modal-stage">Preparing scrape...</span>
          </div>

          <div class="stats">
            <div class="stat">
              <span class="stat-label">Scanned</span>
              <strong id="stat-scanned">0</strong>
            </div>
            <div class="stat">
              <span class="stat-label">Accepted</span>
              <strong id="stat-accepted">0</strong>
            </div>
            <div class="stat">
              <span class="stat-label">Candidates</span>
              <strong id="stat-candidates">0</strong>
            </div>
          </div>

          <div class="activity">
            <div class="activity-head">
              <h4>Live activity</h4>
              <span id="activity-count" class="modal-message">No listings yet.</span>
            </div>
            <div id="activity-feed" class="activity-feed">
              <div class="activity-item">
                <span class="activity-kind">Waiting</span>
                <strong>Starting scrape</strong>
                <p>The first live updates will appear here.</p>
              </div>
            </div>
          </div>

          <div class="modal-foot">
            <span id="modal-message" class="modal-message">The final table will update automatically when the scrape completes.</span>
            <button id="modal-dismiss" class="secondary hidden" type="button">Close</button>
          </div>
        </div>
      </div>
    </div>

    <script>
      const form = document.getElementById("scrape-form");
      const status = document.getElementById("status");
      const summary = document.getElementById("summary");
      const meta = document.getElementById("meta");
      const resultsBody = document.getElementById("results-body");
      const submitButton = document.getElementById("submit-button");
      const modal = document.getElementById("progress-modal");
      const modalClose = document.getElementById("modal-close");
      const modalDismiss = document.getElementById("modal-dismiss");
      const modalStage = document.getElementById("modal-stage");
      const modalMessage = document.getElementById("modal-message");
      const modalSubtitle = document.getElementById("modal-subtitle");
      const activityFeed = document.getElementById("activity-feed");
      const activityCount = document.getElementById("activity-count");
      const statScanned = document.getElementById("stat-scanned");
      const statAccepted = document.getElementById("stat-accepted");
      const statCandidates = document.getElementById("stat-candidates");

      let currentRunId = null;
      let currentSource = null;
      let finalPayload = null;
      let canCloseModal = false;

      function setStatus(message, kind) {
        status.textContent = message;
        status.className = `status visible ${kind}`;
      }

      function clearResults(message) {
        resultsBody.innerHTML = `<tr><td class="empty" colspan="5">${message}</td></tr>`;
      }

      function renderRows(rows) {
        if (!rows.length) {
          clearResults("No matching listings were found for this search.");
          return;
        }

        resultsBody.innerHTML = rows.map((row) => `
          <tr>
            <td>${escapeHtml(row.name)}</td>
            <td>${escapeHtml(row.category || "")}</td>
            <td>${escapeHtml(row.address || "")}</td>
            <td>${escapeHtml(row.phone || "")}</td>
            <td><a href="${row.google_maps_url}" target="_blank" rel="noreferrer">Open</a></td>
          </tr>
        `).join("");
      }

      function escapeHtml(value) {
        return String(value)
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#39;");
      }

      function openModal(query, location) {
        modal.classList.add("open");
        modal.setAttribute("aria-hidden", "false");
        modalStage.textContent = "Preparing scrape...";
        modalSubtitle.textContent = `Watching Google Maps for ${query} in ${location}.`;
        modalMessage.textContent = "The final table will update automatically when the scrape completes.";
        statScanned.textContent = "0";
        statAccepted.textContent = "0";
        statCandidates.textContent = "0";
        activityCount.textContent = "No listings yet.";
        activityFeed.innerHTML = `
          <div class="activity-item">
            <span class="activity-kind">Waiting</span>
            <strong>Starting scrape</strong>
            <p>The first live updates will appear here.</p>
          </div>
        `;
        modalDismiss.classList.add("hidden");
        canCloseModal = false;
      }

      function closeModal(force = false) {
        if (!force && !canCloseModal) {
          return;
        }
        modal.classList.remove("open");
        modal.setAttribute("aria-hidden", "true");
      }

      function prependActivity(kind, title, description) {
        const item = document.createElement("div");
        item.className = "activity-item";
        item.innerHTML = `
          <span class="activity-kind">${escapeHtml(kind)}</span>
          <strong>${escapeHtml(title)}</strong>
          <p>${escapeHtml(description)}</p>
        `;
        activityFeed.prepend(item);
      }

      function updateCounters(event) {
        if (typeof event.scanned_count === "number") {
          statScanned.textContent = String(event.scanned_count);
        }
        if (typeof event.accepted_count === "number") {
          statAccepted.textContent = String(event.accepted_count);
        }
        if (typeof event.candidate_count === "number") {
          statCandidates.textContent = String(event.candidate_count);
        }
      }

      function finishRun() {
        submitButton.disabled = false;
        currentRunId = null;
        if (currentSource) {
          currentSource.close();
          currentSource = null;
        }
      }

      function handleStreamEvent(event) {
        if (event.event === "started") {
          modalStage.textContent = `Starting ${event.query} in ${event.location}`;
          prependActivity("Started", "Scrape launched", `Targeting ${event.query} in ${event.location}.`);
          return;
        }

        if (event.event === "stage") {
          modalStage.textContent = event.message || "Scraping...";
          updateCounters(event);
          modalMessage.textContent = event.message || "Working through Google Maps results.";
          if (event.stage === "results_ready") {
            prependActivity("Results", "Candidate list ready", `${event.candidate_count || 0} map results queued for inspection.`);
          }
          return;
        }

        if (event.event === "listing_found") {
          updateCounters(event);
          const listing = event.listing || {};
          activityCount.textContent = `${event.accepted_count || 0} live listing${event.accepted_count === 1 ? "" : "s"} found`;
          prependActivity(
            "Found",
            listing.name || "Unnamed listing",
            [listing.address, listing.phone].filter(Boolean).join(" • ") || "No extra details yet."
          );
          return;
        }

        if (event.event === "listing_skipped") {
          updateCounters(event);
          return;
        }

        if (event.event === "completed") {
          finalPayload = event;
          modalStage.textContent = "Scrape completed";
          modalMessage.textContent = `Saved ${event.count} listing${event.count === 1 ? "" : "s"} to ${event.output_csv}`;
          activityCount.textContent = `${event.count} listing${event.count === 1 ? "" : "s"} found`;
          renderRows(event.listings || []);
          summary.textContent = `${event.count} listing${event.count === 1 ? "" : "s"} found for ${event.query} in ${event.location}.`;
          meta.textContent = `CSV saved to ${event.output_csv}`;
          setStatus("Scrape completed successfully.", "info");
          canCloseModal = true;
          modalDismiss.classList.remove("hidden");
          finishRun();
          window.setTimeout(() => closeModal(), 1400);
          return;
        }

        if (event.event === "error") {
          modalStage.textContent = "Scrape failed";
          modalMessage.textContent = event.error || "Something went wrong while scraping.";
          prependActivity("Error", "Scrape failed", event.error || "Unknown error");
          setStatus(event.error || "Scrape failed", "error");
          summary.textContent = "No results available.";
          meta.textContent = "";
          clearResults("The scrape failed. Try again with a more specific search.");
          canCloseModal = true;
          modalDismiss.classList.remove("hidden");
          finishRun();
        }
      }

      async function startScrape(payload) {
        const response = await fetch("/api/scrape/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "Unable to start scrape");
        }
        return data;
      }

      function connectStream(runId) {
        currentSource = new EventSource(`/api/scrape/stream?id=${encodeURIComponent(runId)}`);
        currentSource.onmessage = (messageEvent) => {
          const payload = JSON.parse(messageEvent.data);
          if (payload.run_id !== currentRunId) {
            return;
          }
          handleStreamEvent(payload);
        };
        currentSource.onerror = () => {
          if (!currentRunId) {
            return;
          }
          setStatus("The live progress connection was interrupted.", "error");
          modalStage.textContent = "Connection interrupted";
          modalMessage.textContent = "The scrape may still be running, but live updates stopped.";
          canCloseModal = true;
          modalDismiss.classList.remove("hidden");
          finishRun();
        };
      }

      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        finalPayload = null;
        submitButton.disabled = true;
        setStatus("Starting scrape...", "info");
        summary.textContent = "Working...";
        meta.textContent = "";
        clearResults("Scrape in progress...");

        const payload = {
          query: document.getElementById("query").value.trim(),
          location: document.getElementById("location").value.trim(),
          max_results: Number(document.getElementById("max_results").value || 15),
          output_csv: document.getElementById("output_csv").value.trim(),
        };

        openModal(payload.query, payload.location);

        try {
          const data = await startScrape(payload);
          currentRunId = data.run_id;
          modalStage.textContent = "Connecting to live progress...";
          modalMessage.textContent = "Waiting for the first scrape events.";
          connectStream(currentRunId);
        } catch (error) {
          setStatus(error.message || "Scrape failed", "error");
          summary.textContent = "No results available.";
          meta.textContent = "";
          clearResults("The scrape failed. Try again with a more specific search.");
          modalStage.textContent = "Unable to start scrape";
          modalMessage.textContent = error.message || "The scrape could not be started.";
          canCloseModal = true;
          modalDismiss.classList.remove("hidden");
          submitButton.disabled = false;
        }
      });

      modalClose.addEventListener("click", () => closeModal());
      modalDismiss.addEventListener("click", () => closeModal(true));
    </script>
  </body>
</html>
"""


@dataclass
class ScrapeRun:
    run_id: str
    payload: dict[str, Any]
    event_queue: queue.Queue[dict[str, Any]] = field(default_factory=queue.Queue)
    completed: bool = False
    final_result: dict[str, Any] | None = None


SCRAPE_RUNS: dict[str, ScrapeRun] = {}
SCRAPE_RUNS_LOCK = threading.Lock()


def serialize_lead(lead: Any) -> dict[str, str]:
    return {
        "name": lead.name,
        "category": lead.category,
        "address": lead.address,
        "phone": lead.phone,
        "website": lead.website,
        "google_maps_url": lead.google_maps_url,
        "query": lead.query,
        "location": lead.location,
    }


def validate_scrape_inputs(query: str, location: str, max_results: int) -> tuple[str, str, int]:
    query = query.strip()
    location = location.strip()
    if not query:
        raise ValueError("Business type is required.")
    if not location:
        raise ValueError("Location is required.")
    if max_results < 1 or max_results > 100:
        raise ValueError("Max results must be between 1 and 100.")
    return query, location, max_results


def scrape_listings(query: str, location: str, max_results: int, output_csv: str | None) -> dict[str, Any]:
    query, location, max_results = validate_scrape_inputs(query, location, max_results)
    output_path = Path(output_csv).expanduser() if output_csv else default_output_csv_path(query, location)
    config = GoogleMapsAgentConfig(
        query=query,
        location=location,
        max_results=max_results,
        output_csv_path=output_path,
    )
    leads = GoogleMapsNoWebsiteAgent(config).run()
    return {
        "query": query,
        "location": location,
        "count": len(leads),
        "output_csv": str(output_path),
        "listings": [serialize_lead(lead) for lead in leads],
    }


def create_scrape_run(query: str, location: str, max_results: int, output_csv: str | None) -> ScrapeRun:
    query, location, max_results = validate_scrape_inputs(query, location, max_results)
    run_id = uuid.uuid4().hex[:12]
    payload = {
        "query": query,
        "location": location,
        "max_results": max_results,
        "output_csv": output_csv,
    }
    run = ScrapeRun(run_id=run_id, payload=payload)
    with SCRAPE_RUNS_LOCK:
        SCRAPE_RUNS[run_id] = run
    return run


def enqueue_progress_event(run: ScrapeRun, payload: dict[str, Any]) -> None:
    payload = dict(payload)
    payload["run_id"] = run.run_id
    run.event_queue.put(payload)


def finalize_scrape_run(run: ScrapeRun, result: dict[str, Any] | None = None) -> None:
    run.completed = True
    run.final_result = result


def run_scrape_in_background(run: ScrapeRun) -> None:
    payload = run.payload
    output_csv = payload["output_csv"]
    output_path = Path(output_csv).expanduser() if output_csv else default_output_csv_path(
        payload["query"],
        payload["location"],
    )
    config = GoogleMapsAgentConfig(
        query=payload["query"],
        location=payload["location"],
        max_results=payload["max_results"],
        output_csv_path=output_path,
    )
    try:
        leads = GoogleMapsNoWebsiteAgent(config, progress_callback=lambda event: enqueue_progress_event(run, event)).run()
        result = {
            "event": "completed",
            "query": payload["query"],
            "location": payload["location"],
            "count": len(leads),
            "output_csv": str(output_path),
            "listings": [serialize_lead(lead) for lead in leads],
        }
        finalize_scrape_run(run, result)
    except Exception as exc:  # pragma: no cover - defensive thread boundary
        error_payload = {"event": "error", "error": f"Scrape failed: {exc}"}
        enqueue_progress_event(run, error_payload)
        finalize_scrape_run(run, error_payload)


def start_scrape_run(query: str, location: str, max_results: int, output_csv: str | None) -> dict[str, Any]:
    run = create_scrape_run(query, location, max_results, output_csv)
    worker = threading.Thread(target=run_scrape_in_background, args=(run,), daemon=True)
    worker.start()
    return {"run_id": run.run_id}


def get_scrape_run(run_id: str) -> ScrapeRun | None:
    with SCRAPE_RUNS_LOCK:
        return SCRAPE_RUNS.get(run_id)


class GoogleMapsWebHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = HTML_PAGE.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/scrape/stream":
            query = parse_qs(parsed.query)
            run_id = query.get("id", [""])[0]
            run = get_scrape_run(run_id)
            if run is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown scrape run."})
                return
            self._stream_scrape_events(run)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length or 0)
            payload = json.loads(raw_body.decode("utf-8") or "{}")
            if parsed.path == "/api/scrape":
                result = scrape_listings(
                    query=str(payload.get("query", "")),
                    location=str(payload.get("location", "")),
                    max_results=int(payload.get("max_results", 15)),
                    output_csv=str(payload.get("output_csv", "")).strip() or None,
                )
                self._send_json(HTTPStatus.OK, result)
                return
            if parsed.path == "/api/scrape/start":
                result = start_scrape_run(
                    query=str(payload.get("query", "")),
                    location=str(payload.get("location", "")),
                    max_results=int(payload.get("max_results", 15)),
                    output_csv=str(payload.get("output_csv", "")).strip() or None,
                )
                self._send_json(HTTPStatus.OK, result)
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive server boundary
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Scrape failed: {exc}"})

    def _stream_scrape_events(self, run: ScrapeRun) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        while True:
            try:
                payload = run.event_queue.get(timeout=1)
                self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode("utf-8"))
                self.wfile.flush()
                if payload.get("event") in {"completed", "error"}:
                    break
            except queue.Empty:
                if run.completed and run.event_queue.empty():
                    break
                try:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                except BrokenPipeError:
                    break
            except BrokenPipeError:
                break

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def find_available_port(host: str, preferred_port: int, attempts: int = 10) -> int:
    for port in range(preferred_port, preferred_port + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
            candidate.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                candidate.bind((host, port))
                return port
            except OSError:
                continue
    raise OSError(f"No free port found between {preferred_port} and {preferred_port + attempts - 1}.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Google Maps lead scraper web UI.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Preferred port to bind to")
    args = parser.parse_args()

    port = find_available_port(args.host, args.port)
    server = ThreadingHTTPServer((args.host, port), GoogleMapsWebHandler)
    print(f"Google Maps web UI running at http://{args.host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
