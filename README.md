# CrewInspector → Supabase Seafarer Stats

Playwright automation that logs into CrewInspector, scrapes seafarer headcount statistics, and stores them in Supabase.

## What it collects

| Table | Description |
|---|---|
| `seafarer_by_country` | Active / inactive / total per nationality |
| `seafarer_by_rank` | Active / inactive / total per rank (global) |
| `seafarer_by_country_rank` | Active / inactive / total per country + rank combination |

Each scrape creates a row in `scrape_runs` (status: `running` → `completed` / `failed`). All child rows reference it via `run_id`.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure `.env`

Copy the example below and fill in your credentials:

```
CREW_BASE_URL=https://candina.crewinspector.com
CREW_USERNAME=your_username
CREW_PASSWORD=your_password
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
```

### 3. Create Supabase tables

Run `schema.sql` in the Supabase SQL Editor (Dashboard → SQL Editor → New query).

If you already have the v1 tables from a previous setup, run `schema_add_country_rank.sql` instead.

## Usage

```bash
# Test run — 5 countries × 5 ranks, browser visible
python scraper.py --test

# Full run — 249 countries × 270 ranks
python scraper.py
```

The browser opens visibly so you can watch progress. The scraper logs out automatically when done.

### Full run time estimate

The full run covers up to ~67,000 country × rank combinations. Zero-count combinations are detected with a single query and skipped. Expect several hours for a complete run.

## Files

| File | Purpose |
|---|---|
| `scraper.py` | Main automation script |
| `country.txt` | 249 country names to scrape |
| `rank.txt` | 270 rank names to scrape |
| `search.html` | Saved copy of the CrewInspector search form (used to extract rank IDs) |
| `schema.sql` | Full database schema (fresh install) |
| `schema_add_country_rank.sql` | Migration — adds `seafarer_by_country_rank`, drops `seafarer_totals` |
| `cleanup_runs.py` | Utility to delete specific scrape runs from Supabase |
| `requirements.txt` | Python dependencies |

## Cleaning up bad runs

```bash
python cleanup_runs.py
```

Edit the `BAD_RUN_IDS` list in the file before running.
