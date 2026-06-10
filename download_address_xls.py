"""
CrewInspector – download Address XLS per country (active + inactive).

For each country in country.txt the script:
  1. Opens the /search page.
  2. Fills the country-code field (3-letter ISO code).
  3. Unchecks the "Only active" checkbox so ALL seafarers are included.
  4. Sets form_action = 'address_xls' and submits the form.
  5. Saves the downloaded .xls file to  downloads/<COUNTRY_CODE>.xls

Usage:
    python download_address_xls.py            # all countries in country.txt
    python download_address_xls.py --test     # first 5 countries only
    python download_address_xls.py --country PHL,IDN   # specific ISO codes

.env must contain:
    CREW_BASE_URL, CREW_USERNAME, CREW_PASSWORD
"""

import asyncio
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from typing import Optional

import pycountry
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page

load_dotenv()

BASE_URL    = os.getenv("CREW_BASE_URL", "").rstrip("/")
CI_USERNAME = os.getenv("CREW_USERNAME", "")
CI_PASSWORD = os.getenv("CREW_PASSWORD", "")

TEST_MODE   = "--test" in sys.argv
DOWNLOAD_DIR = Path("downloads")
REQUEST_DELAY = 2.0   # seconds between downloads

# Parse --country PHL,IDN,MMR   (optional filter)
_COUNTRY_ARG: list[str] = []
for _i, _a in enumerate(sys.argv):
    if _a == "--country" and _i + 1 < len(sys.argv):
        _COUNTRY_ARG = [c.strip().upper() for c in sys.argv[_i + 1].split(",")]

TEST_COUNTRIES = ["PHILIPPINES", "UKRAINE", "INDONESIA", "RUSSIA", "MYANMAR"]

# Countries too large to download as a single file.
# These must be handled by their dedicated per-rank scripts instead.
# download_spain_by_rank.py → ESP
LARGE_COUNTRIES = {"ESP"}

# ── country-code lookup (same overrides as scraper.py) ─────────────────────────
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
        if c:
            return c.alpha_3
        c = pycountry.countries.get(**{key: name.title()})
        if c:
            return c.alpha_3
    try:
        results = pycountry.countries.search_fuzzy(name)
        if results:
            return results[0].alpha_3
    except LookupError:
        pass
    return None


# ── download helper ─────────────────────────────────────────────────────────────

_BTN = 'input[type="button"][value="Address xls"]'


async def download_xls(page: Page, country_code: str, dest: Path) -> str:
    """
    Navigate to /search, run the search for all seafarers (active + inactive)
    filtered by country_code, then click 'Address xls' if it appears.

    Returns:
        "ok"        – file downloaded successfully
        "no_button" – search returned no results / button not present
        "failed"    – button was present but download errored
    """
    await page.goto(f"{BASE_URL}/search", wait_until="domcontentloaded", timeout=30_000)
    await asyncio.sleep(0.5)

    # Set country code
    await page.fill("input#country_code", country_code)
    await page.keyboard.press("Escape")
    await asyncio.sleep(0.3)

    # Uncheck "Only active" so we get all seafarers
    cb = page.locator("input#show_active")
    if await cb.is_checked():
        await cb.click()
    await asyncio.sleep(0.2)

    # Run the normal search first so results are rendered
    try:
        async with page.expect_navigation(wait_until="networkidle", timeout=30_000):
            await page.locator('input[type="submit"][value="Search"]').first.click()
    except Exception:
        try:
            await page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass

    # Only proceed if the "Address xls" button is present and visible
    btn = page.locator(_BTN)
    if not await btn.is_visible():
        return "no_button"

    # Click the button and capture the resulting file download
    try:
        async with page.expect_download(timeout=60_000) as dl_info:
            await btn.click()
        download = await dl_info.value
        await download.save_as(str(dest))
        return "ok"
    except Exception as exc:
        print(f"    WARNING: download failed for {country_code}: {exc}", file=sys.stderr)
        return "failed"


# ── main ────────────────────────────────────────────────────────────────────────

async def main() -> None:
    missing = [k for k, v in {
        "CREW_BASE_URL": BASE_URL,
        "CREW_USERNAME": CI_USERNAME,
        "CREW_PASSWORD": CI_PASSWORD,
    }.items() if not v]
    if missing:
        sys.exit(f"Missing env vars: {', '.join(missing)}")

    with open("country.txt", encoding="utf-8") as f:
        all_countries = [line.strip() for line in f if line.strip()]

    if TEST_MODE:
        country_names = TEST_COUNTRIES
        print("*** TEST MODE – first 5 countries ***")
    else:
        country_names = all_countries

    # Build (name, code) list, skip entries with no ISO code
    country_list: list[tuple[str, str]] = []
    for cname in country_names:
        code = get_country_code(cname)
        if code:
            country_list.append((cname, code))
        else:
            print(f"  SKIP {cname!r} – no ISO code")

    # Optional --country filter
    if _COUNTRY_ARG:
        country_list = [(n, c) for n, c in country_list if c in _COUNTRY_ARG]
        print(f"Filtered to {len(country_list)} countries by --country arg")

    DOWNLOAD_DIR.mkdir(exist_ok=True)
    print(f"Saving downloads to: {DOWNLOAD_DIR.resolve()}")
    print(f"Countries to process: {len(country_list)}\n")

    ok_count      = 0
    skip_count    = 0
    no_btn_count  = 0
    fail_count    = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, slow_mo=80)
        ctx     = await browser.new_context(
            accept_downloads=True,
            viewport={"width": 1280, "height": 800},
        )
        page = await ctx.new_page()

        # ── Login ──────────────────────────────────────────────────────────────
        print("Logging in ...")
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
            raise RuntimeError("Login failed – logout link not found.")

        # ── Download loop ──────────────────────────────────────────────────────
        for i, (cname, code) in enumerate(country_list, 1):
            dest = DOWNLOAD_DIR / f"{code}.xls"

            if code in LARGE_COUNTRIES:
                print(f"  [{i:3}/{len(country_list)}] SKIP  {cname:<40} ({code}) – too large, use dedicated script")
                skip_count += 1
                continue

            if dest.exists():
                print(f"  [{i:3}/{len(country_list)}] SKIP  {cname:<40} ({code}) – already downloaded")
                skip_count += 1
                continue

            print(f"  [{i:3}/{len(country_list)}] {cname:<40} ({code}) ...", end=" ", flush=True)
            result = await download_xls(page, code, dest)

            if result == "ok":
                size_kb = dest.stat().st_size // 1024
                print(f"OK  ({size_kb} KB)")
                ok_count += 1
            elif result == "no_button":
                print("NO RESULTS – button not shown, skipped")
                no_btn_count += 1
            else:
                print("FAILED")
                fail_count += 1

            await asyncio.sleep(REQUEST_DELAY)

        # ── Logout ─────────────────────────────────────────────────────────────
        print("\nLogging out ...")
        await page.goto(f"{BASE_URL}/logout", wait_until="domcontentloaded")
        await asyncio.sleep(1.0)
        await browser.close()

    print(f"\n=== Done ===")
    print(f"  Downloaded : {ok_count}")
    print(f"  Skipped    : {skip_count}  (file already existed)")
    print(f"  No results : {no_btn_count}  (button not shown)")
    print(f"  Failed     : {fail_count}")
    print(f"  Saved to   : {DOWNLOAD_DIR.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
