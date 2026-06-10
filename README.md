# CrewInspector → Supabase Seafarer Data

Playwright automation that logs into CrewInspector, scrapes seafarer statistics, downloads address data per country, and stores everything in Supabase.

## What it collects

### Headcount statistics (Supabase)

| Table | Description |
|---|---|
| `seafarer_by_country` | Active / inactive / total per nationality |
| `seafarer_by_rank` | Active / inactive / total per rank (global) |
| `seafarer_by_country_rank` | Active / inactive / total per country + rank combination |
| `seafarer_addresses` | Full address & contact details per seafarer |

Each scrape creates a row in `scrape_runs` (status: `running` → `completed` / `failed`). All child rows reference it via `run_id`.

### Address downloads (local files)

| Output | Script |
|---|---|
| `downloads/<ISO>.xls` | One file per country — all countries except Spain |
| `downloads/spain/<RANK>.xls` | Per-rank files for Spain (too large for a single download) |
| `downloads/ESP.xlsx` | Combined, deduplicated Excel for Spain |

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure `.env`

```
CREW_BASE_URL=https://candina.crewinspector.com
CREW_USERNAME=your_username
CREW_PASSWORD=your_password
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
```

### 3. Create Supabase tables

**Fresh install** — run `schema.sql` in the Supabase SQL Editor.

**Add address table only** — run `schema_address.sql`.

**Existing v1 install** — run `schema_add_country_rank.sql` instead of `schema.sql`.

---

## Usage

### Scrape headcount statistics

```bash
python scraper.py           # full run — 249 countries × 270 ranks
python scraper.py --test    # test run — 5 countries × 5 ranks
```

The browser opens visibly so you can watch progress. Expect several hours for a full run (~67,000 combinations).

### Download address files

```bash
# Step 1 — all countries except Spain
python download_address_xls.py

# Step 2 — Spain (split by rank, then merged into downloads/ESP.xlsx)
python download_spain_by_rank.py

# Both scripts are safe to resume — already-downloaded files are skipped
```

#### Options for download_address_xls.py

```bash
python download_address_xls.py --test               # first 5 countries only
python download_address_xls.py --country PHL,IDN    # specific ISO codes
```

#### Options for download_spain_by_rank.py

```bash
python download_spain_by_rank.py --download-only    # download rank files only
python download_spain_by_rank.py --merge-only       # merge existing rank files only
```

### Import address data to Supabase

```bash
# Import all downloaded files (both .xls and ESP.xlsx)
python import_address_xls.py

python import_address_xls.py --test         # first 3 files only
python import_address_xls.py PHL IDN ESP    # specific ISO codes
```

If both `ESP.xls` and `ESP.xlsx` exist, `ESP.xlsx` is used (the clean deduplicated version).

### Recommended run order

```bash
python download_address_xls.py      # 1. download all countries (skips ESP)
python download_spain_by_rank.py    # 2. download + merge Spain
python import_address_xls.py        # 3. push everything to Supabase
```

### Clean up bad scrape runs

```bash
python cleanup_runs.py
```

Edit the `BAD_RUN_IDS` list in the file before running.

---

## Files

| File | Purpose |
|---|---|
| `scraper.py` | Scrapes headcount stats into Supabase |
| `download_address_xls.py` | Downloads Address XLS per country (skips ESP) |
| `download_spain_by_rank.py` | Downloads Spain by rank, merges into `ESP.xlsx` |
| `import_address_xls.py` | Imports downloaded files into `seafarer_addresses` |
| `cleanup_runs.py` | Deletes bad scrape runs from Supabase |
| `country.txt` | 249 country names |
| `rank.txt` | 270 rank names |
| `search.html` | Saved CrewInspector search form (used to extract rank IDs) |
| `schema.sql` | Full Supabase schema (fresh install) |
| `schema_address.sql` | Creates the `seafarer_addresses` table |
| `schema_add_country_rank.sql` | Migration for v1 installs |
| `requirements.txt` | Python dependencies |
| `info.txt` | Plain-English description of every script |
