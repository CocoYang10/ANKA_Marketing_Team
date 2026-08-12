# Basecamp-ready weekly Marketing Report requirement

Confirmed workflow: **generate → review → copy/paste**. The Agent must not call
the Basecamp API or publish the report automatically.

## Current reference

`/Users/cocoyang/Downloads/2026-07-20_Marketing-Report-Week-29 (1).html`

The reference uses a narrow, readable HTML layout designed to survive copying
into a Basecamp message.

## Required output

- one dated HTML file for the completed reporting week;
- a clear report title and reporting date range;
- link to the current Marketing Agent dashboard/demo;
- Executive Summary that leads with decisions and important changes;
- Channel Scorecard;
- GA4 website/commerce section with a visible data-quality warning when needed;
- channel sections for only the sources that are connected or manually
  supplied;
- recommendations with priority, action, owner and Done Means;
- compact tables, status colors and simple indicators rather than complex
  interactive charts;
- copy/paste-compatible fonts, tables and inline/self-contained styling.

## Evidence rules

- report the latest complete week, never a partial current week;
- distinguish `CONNECTED`, `MANUAL_EXPORT`, `STALE`, `REVIEW` and
  `NOT_CONNECTED`;
- missing connector data must appear as unavailable, never as zero;
- every comparison must name its baseline and event context;
- no CAC, ROAS or channel-revenue conclusion while purchase attribution is
  unavailable;
- Vanessa reviews the final text before it is copied to Basecamp.

## Locked V1 template decision

V1 uses the shorter, decision-first Week 32 structure: Executive Summary,
Channel Scorecard, Website & Commerce, Data Health, Recommended Actions,
Questions to Close, and Caveats & Assumptions. It intentionally excludes
non-copyable charts. `generate_basecamp_report.py` renders the reviewed Agent
snapshot into this format and provides a rich-text Copy report button.
