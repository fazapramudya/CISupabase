"""
CrewInspector -> Supabase seafarer statistics scraper.

Collects:
  - seafarer_by_country      : active / inactive / total per country
  - seafarer_by_rank         : active / inactive / total per rank  (global)
  - seafarer_by_country_rank : active / inactive / total per country + rank combo

Usage:
    python scraper.py            # full run  (249 countries x 270 ranks)
    python scraper.py --test     # test run  (5 countries x 5 ranks)

.env must contain:
    CREW_BASE_URL, CREW_USERNAME, CREW_PASSWORD,
    SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import asyncio
import re
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Optional

import pycountry
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page
from supabase import create_client, Client

load_dotenv()

# ── env ────────────────────────────────────────────────────────────────────────
BASE_URL     = os.getenv("CREW_BASE_URL", "").rstrip("/")
CI_USERNAME  = os.getenv("CREW_USERNAME", "")
CI_PASSWORD  = os.getenv("CREW_PASSWORD", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

TEST_MODE     = "--test" in sys.argv
REQUEST_DELAY = 1.5   # seconds between searches
BATCH_SIZE    = 50    # rows per Supabase insert

TEST_COUNTRIES = ["PHILIPPINES", "UKRAINE", "INDONESIA", "RUSSIA", "MYANMAR"]
TEST_RANKS     = ["MASTER", "AB", "BOSUN", "CENG", "COOK"]


# ── country-code lookup ─────────────────────────────────────────────────────────
_COUNTRY_OVERRIDES: dict[str, Optional[str]] = {
    "Curacao":                                   "CUW",
    "CURACAO":                                   "CUW",
    "Guernsey":                                  "GGY",
    "GUERNSEY":                                  "GGY",
    "ISLE OF MAN":                               "IMN",
    "JERSEY":                                    "JEY",
    "SINT MAARTEN":                              "SXM",
    "CONGO, Democratic Republic of (was Zaire)": "COD",
    "CONGO, People s Republic of":               "COG",
    "KOREA, DEMOCRATIC PEOPLE S REPUBLIC OF":   "PRK",
    "KOREA, REPUBLIC OF":                       "KOR",
    "IRAN (ISLAMIC REPUBLIC OF)":               "IRN",
    "LIBYAN ARAB JAMAHIRIYA":                    "LBY",
    "MOLDOVA":                                   "MDA",
    "MACAU":                                     "MAC",
    "VIET NAM":                                  "VNM",
    "TANZANIA, UNITED REPUBLIC OF":             "TZA",
    "FRANCE, METROPOLITAN":                     "FXX",
    "VIRGIN ISLANDS (BRITISH)":                 "VGB",
    "VIRGIN ISLANDS (U.S.)":                    "VIR",
    "MICRONESIA, FEDERATED STATES OF":          "FSM",
    "PALESTINIAN TERRITORY, Occupied":          "PSE",
    "SYRIAN ARAB REPUBLIC":                     "SYR",
    "YUGOSLAVIA":                               "YUG",
    "EAST TIMOR":                               "TLS",
    "NETHERLANDS ANTILLES":                     "ANT",
    "SAINT KITTS AND NEVIS":                    "KNA",
    "SAINT LUCIA":                              "LCA",
    "SAINT VINCENT AND THE GRENADINES":         "VCT",
    "SAO TOME AND PRINCIPE":                    "STP",
    "SVALBARD AND JAN MAYEN ISLANDS":           "SJM",
    "TURKS AND CAICOS ISLANDS":                 "TCA",
    "WALLIS AND FUTUNA ISLANDS":                "WLF",
    "WESTERN SAHARA":                           "ESH",
    "FALKLAND ISLANDS (MALVINAS)":              "FLK",
    "COCOS (KEELING) ISLANDS":                  "CCK",
    "HEARD AND MC DONALD ISLANDS":              "HMD",
    "SOUTH GEORGIA AND THE SOUTH SANDWICH ISLANDS": "SGS",
    "FRENCH SOUTHERN TERRITORIES":              "ATF",
    "SLOVAKIA (Slovak Republic)":               "SVK",
    "TAIWAN":                                   "TWN",
    "HONG KONG":                                "HKG",
    "LAO PEOPLE S DEMOCRATIC REPUBLIC":         "LAO",
    "CAPE VERDE":                               "CPV",
    "BRUNEI DARUSSALAM":                        "BRN",
    "COTE D IVOIRE":                            "CIV",
    "BOSNIA AND HERZEGOWINA":                   "BIH",
    "SWAZILAND":                                "SWZ",
    "BOUVET ISLAND":                            "BVT",
    "BRITISH INDIAN OCEAN TERRITORY":           "IOT",
    "CHRISTMAS ISLAND":                         "CXR",
    "COOK ISLANDS":                             "COK",
    "MARSHALL ISLANDS":                         "MHL",
    "NORFOLK ISLAND":                           "NFK",
    "AMERICAN SAMOA":                           "ASM",
    "NORTHERN MARIANA ISLANDS":                "MNP",
    "FAROE ISLANDS":                            "FRO",
    "GREENLAND":                                "GRL",
    "FRENCH POLYNESIA":                         "PYF",
    "GUADELOUPE":                               "GLP",
    "MARTINIQUE":                               "MTQ",
    "NEW CALEDONIA":                            "NCL",
    "REUNION":                                  "REU",
    "FRENCH GUIANA":                            "GUF",
    "MAYOTTE":                                  "MYT",
    "ST. PIERRE AND MIQUELON":                  "SPM",
    "ST. HELENA":                               "SHN",
    "BERMUDA":                                  "BMU",
    "CAYMAN ISLANDS":                           "CYM",
    "ANGUILLA":                                 "AIA",
    "MONTSERRAT":                               "MSR",
    "PITCAIRN":                                 "PCN",
    "NIUE":                                     "NIU",
    "TOKELAU":                                  "TKL",
    "ANTARCTICA":                               "ATA",
    "MACEDONIA, THE FORMER YUGOSLAV REPUBLIC OF": "MKD",
    "TURKEY":                                   "TUR",
    "VATICAN CITY STATE (HOLY SEE)":            "VAT",
    "EUROPEAN":                                 None,
    "UNKNOWN":                                  None,
}


def get_country_code(name: str) -> Optional[str]:
    if name in _COUNTRY_OVERRIDES:
        return _COUNTRY_OVERRIDES[name]
    if name.upper() in _COUNTRY_OVERRIDES:
        return _COUNTRY_OVERRIDES[name.upper()]
    for key in ("name", "common_name", "official_name"):
        c = pycountry.countries.get(**{key: name})
        if c: return c.alpha_3
        c = pycountry.countries.get(**{key: name.title()})
        if c: return c.alpha_3
    try:
        results = pycountry.countries.search_fuzzy(name)
        if results: return results[0].alpha_3
    except LookupError:
        pass
    return None


# ── rank-map builder ────────────────────────────────────────────────────────────

class _RankParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in  = False
        self._val: Optional[str] = None
        self.ranks: dict[str, int] = {}

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "select" and d.get("id") == "rank_id":
            self._in = True
        if self._in and tag == "option":
            self._val = d.get("value", "0")

    def handle_endtag(self, tag):
        if tag == "select":
            self._in = False

    def handle_data(self, data):
        if self._in and self._val is not None:
            name = data.strip()
            if name and self._val not in ("0", ""):
                self.ranks[name] = int(self._val)
            self._val = None


def build_rank_map(html_path: str) -> dict[str, int]:
    with open(html_path, encoding="utf-8") as f:
        html = f.read()
    p = _RankParser()
    p.feed(html)
    return p.ranks


# ── search helpers ──────────────────────────────────────────────────────────────

def _extract_total(html: str) -> int:
    m = re.search(r"<b>\s*Total:\s*([\d,]+)\s*</b>", html)
    if m:
        return int(m.group(1).replace(",", ""))
    return 0


async def search_count(
    page: Page,
    *,
    rank_id: Optional[int] = None,
    country_code: Optional[str] = None,
    active_only: bool = True,
) -> int:
    """Fill and submit the search form, return the total seafarer count."""
    await page.goto(f"{BASE_URL}/search", wait_until="domcontentloaded", timeout=30_000)
    await asyncio.sleep(0.4)

    rank_val = str(rank_id) if rank_id else "0"
    await page.select_option("select#rank_id", value=rank_val)

    if country_code:
        await page.fill("input#country_code", country_code)
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.2)
    else:
        await page.fill("input#country_code", "")

    cb = page.locator("input#show_active")
    is_checked = await cb.is_checked()
    if active_only and not is_checked:
        await cb.click()
    elif not active_only and is_checked:
        await cb.click()

    try:
        async with page.expect_navigation(wait_until="networkidle", timeout=30_000):
            await page.locator('input[type="submit"][value="Search"]').first.click()
    except Exception:
        try:
            await page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass

    content = await page.content()
    total = _extract_total(content)
    if total == 0:
        await asyncio.sleep(1.5)
        content = await page.content()
        total = _extract_total(content)
    return total


# ── Supabase helpers ────────────────────────────────────────────────────────────

def _batch_insert(client: Client, table: str, rows: list[dict]) -> None:
    for start in range(0, len(rows), BATCH_SIZE):
        client.table(table).insert(rows[start : start + BATCH_SIZE]).execute()


# ── main ────────────────────────────────────────────────────────────────────────

async def main() -> None:
    missing = [k for k, v in {
        "CREW_BASE_URL": BASE_URL, "CREW_USERNAME": CI_USERNAME,
        "CREW_PASSWORD": CI_PASSWORD, "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_SERVICE_KEY": SUPABASE_KEY,
    }.items() if not v]
    if missing:
        sys.exit(f"Missing env vars: {', '.join(missing)}")

    with open("country.txt", encoding="utf-8") as f:
        all_countries = [l.strip() for l in f if l.strip()]
    with open("rank.txt", encoding="utf-8") as f:
        all_rank_names = [l.strip() for l in f if l.strip()]
    rank_map = build_rank_map("search.html")

    if TEST_MODE:
        countries  = TEST_COUNTRIES
        rank_names = TEST_RANKS
        print("*** TEST MODE - 5 countries x 5 ranks ***")
    else:
        countries  = all_countries
        rank_names = all_rank_names

    print(f"Countries : {len(countries)}")
    print(f"Ranks     : {len(rank_names)}")
    print(f"Max combos: {len(countries) * len(rank_names):,}  (zero-count combos are skipped)\n")

    sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    run_resp = sb.table("scrape_runs").insert({
        "status":     "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    run_id: int = run_resp.data[0]["id"]
    print(f"Started scrape run #{run_id}  ({'TEST' if TEST_MODE else 'FULL'})\n")

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=False, slow_mo=80)
            ctx     = await browser.new_context(viewport={"width": 1280, "height": 800})
            page    = await ctx.new_page()

            # ── Login ─────────────────────────────────────────────────────────
            print("[1/3] Logging in ...")
            await page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
            await page.fill('input[name="login"]',    CI_USERNAME)
            await page.fill('input[name="password"]', CI_PASSWORD)

            async with page.expect_navigation(wait_until="domcontentloaded", timeout=20_000):
                await page.click('input[name="submit_bttn"]')
            await page.wait_for_load_state("networkidle", timeout=15_000)

            try:
                await page.wait_for_selector('a[href="/logout"]', timeout=8_000)
                print("  Logged in OK.\n")
            except Exception:
                await page.screenshot(path="login_debug.png")
                raise RuntimeError("Login failed - logout link not found.")

            # ── Build valid country list (skip entries with no ISO code) ───────
            country_list: list[tuple[str, str]] = []  # (name, code)
            for cname in countries:
                code = get_country_code(cname)
                if code:
                    country_list.append((cname, code))
                else:
                    print(f"  SKIP country {cname!r} - no ISO code")

            # ── Build valid rank list (skip entries not in the dropdown) ───────
            rank_list: list[tuple[str, int]] = []  # (name, id)
            for rname in rank_names:
                rid = rank_map.get(rname)
                if rid:
                    rank_list.append((rname, rid))
                else:
                    print(f"  SKIP rank {rname!r} - not in dropdown")

            total_combos = len(country_list) * len(rank_list)
            print(f"\n[2/3] Per-country counts ({len(country_list)} countries) ...")
            country_rows: list[dict] = []

            for i, (cname, code) in enumerate(country_list, 1):
                active = await search_count(page, country_code=code, active_only=True)
                await asyncio.sleep(REQUEST_DELAY)
                total  = await search_count(page, country_code=code, active_only=False)
                inactive = max(0, total - active)

                print(f"  [{i:3}/{len(country_list)}] {cname:<45} ({code})"
                      f"  active={active:>6,}  inactive={inactive:>6,}  total={total:>6,}")

                country_rows.append({
                    "run_id":         run_id,
                    "country_name":   cname,
                    "country_code":   code,
                    "active_count":   active,
                    "inactive_count": inactive,
                    "total_count":    total,
                })
                await asyncio.sleep(REQUEST_DELAY)

            _batch_insert(sb, "seafarer_by_country", country_rows)
            print(f"  -> Saved {len(country_rows)} country rows.\n")

            # ── Per rank (global) ──────────────────────────────────────────────
            print(f"[3/3a] Per-rank global counts ({len(rank_list)} ranks) ...")
            rank_rows:    list[dict] = []
            zero_ranks:   list[str]  = []

            for i, (rname, rid) in enumerate(rank_list, 1):
                active = await search_count(page, rank_id=rid, active_only=True)
                await asyncio.sleep(REQUEST_DELAY)
                total  = await search_count(page, rank_id=rid, active_only=False)
                inactive = max(0, total - active)

                if total == 0:
                    zero_ranks.append(rname)
                    print(f"  [{i:3}/{len(rank_list)}] ZERO  {rname!r}")
                    await asyncio.sleep(REQUEST_DELAY)
                    continue

                print(f"  [{i:3}/{len(rank_list)}] {rname:<30} (id={rid:>4})"
                      f"  active={active:>6,}  inactive={inactive:>6,}  total={total:>6,}")

                rank_rows.append({
                    "run_id":         run_id,
                    "rank_name":      rname,
                    "rank_id":        rid,
                    "active_count":   active,
                    "inactive_count": inactive,
                    "total_count":    total,
                })
                await asyncio.sleep(REQUEST_DELAY)

            _batch_insert(sb, "seafarer_by_rank", rank_rows)
            print(f"  -> Saved {len(rank_rows)} rank rows "
                  f"({len(zero_ranks)} skipped with zero count).\n")

            # ── Per country x rank ─────────────────────────────────────────────
            # Only process ranks that have at least one seafarer globally.
            active_ranks = [(rname, rid) for rname, rid in rank_list
                            if any(r["rank_name"] == rname for r in rank_rows)]
            print(f"[3/3b] Country x rank cross-table "
                  f"({len(country_list)} countries x {len(active_ranks)} active ranks"
                  f" = up to {len(country_list)*len(active_ranks):,} combos) ...")

            cr_rows:   list[dict] = []
            combo_num  = 0
            total_combos = len(country_list) * len(active_ranks)

            for cname, code in country_list:
                for rname, rid in active_ranks:
                    combo_num += 1
                    # Quick total check first - skip active query if zero
                    total = await search_count(
                        page, rank_id=rid, country_code=code, active_only=False)
                    await asyncio.sleep(REQUEST_DELAY)

                    if total == 0:
                        continue

                    active = await search_count(
                        page, rank_id=rid, country_code=code, active_only=True)
                    inactive = max(0, total - active)

                    print(f"  [{combo_num:5}/{total_combos:5}]"
                          f"  {cname:<25} / {rname:<20}"
                          f"  active={active:>5,}  total={total:>5,}")

                    cr_rows.append({
                        "run_id":         run_id,
                        "country_name":   cname,
                        "country_code":   code,
                        "rank_name":      rname,
                        "rank_id":        rid,
                        "active_count":   active,
                        "inactive_count": inactive,
                        "total_count":    total,
                    })
                    await asyncio.sleep(REQUEST_DELAY)

                    # Flush every BATCH_SIZE rows to avoid large memory build-up
                    if len(cr_rows) >= BATCH_SIZE:
                        _batch_insert(sb, "seafarer_by_country_rank", cr_rows)
                        cr_rows = []

            if cr_rows:
                _batch_insert(sb, "seafarer_by_country_rank", cr_rows)

            cr_count = combo_num  # total processed
            print(f"  -> Country x rank done. Non-zero combos saved.\n")

            # ── Logout ─────────────────────────────────────────────────────────
            print("Logging out ...")
            await page.goto(f"{BASE_URL}/logout", wait_until="domcontentloaded")
            await asyncio.sleep(1.5)
            print("  Logged out.")
            await browser.close()

        sb.table("scrape_runs").update({
            "status":       "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()

        print(f"\n=== Run #{run_id} completed ===")
        print(f"  Countries  : {len(country_rows)}")
        print(f"  Ranks      : {len(rank_rows)}")

    except Exception as exc:
        sb.table("scrape_runs").update({
            "status":       "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()
        print(f"\nRun #{run_id} FAILED: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    asyncio.run(main())
