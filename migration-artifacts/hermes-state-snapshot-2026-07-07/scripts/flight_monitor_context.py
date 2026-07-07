#!/usr/bin/env python3
import os
from pathlib import Path

MAIN_ENV = Path.home() / '.hermes' / '.env'
PROFILE_ENV = Path.home() / '.hermes' / 'profiles' / 'lead-hunter-brussels' / '.env'


def load_env_file(path: Path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith('#') or '=' not in s:
            continue
        key, value = s.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip())


for env_path in (MAIN_ENV, PROFILE_ENV):
    load_env_file(env_path)


def status_line(label: str, ok: bool, details: str = ""):
    marker = "ok" if ok else "missing"
    tail = f" | {details}" if details else ""
    print(f"{label}: {marker}{tail}")


firecrawl_key = os.getenv('FIRECRAWL_API_KEY', '').strip()
firecrawl_api_url = os.getenv('FIRECRAWL_API_URL', '').strip()
firecrawl_gateway_url = os.getenv('FIRECRAWL_GATEWAY_URL', '').strip()
skyscanner_key = os.getenv('SKYSCANNER_API_KEY', '').strip()
airtable_pat = os.getenv('AIRTABLE_PAT', '').strip()
airtable_base = os.getenv('AIRTABLE_BASE_ID', '').strip()
default_table = os.getenv('AIRTABLE_FLIGHTS_TABLE', '').strip() or 'Flight Observations'

status_line('Firecrawl credential', bool(firecrawl_key), 'web_extract / blocked OTA fallback')
status_line('Firecrawl API URL override', bool(firecrawl_api_url), firecrawl_api_url or 'default cloud')
status_line('Firecrawl gateway override', bool(firecrawl_gateway_url), firecrawl_gateway_url or 'none')
status_line('Skyscanner credential', bool(skyscanner_key), 'dashboard key for future official access / partner workflows')
status_line('Airtable PAT', bool(airtable_pat), 'flight persistence auth')
status_line('Airtable base', bool(airtable_base), airtable_base or 'base id unavailable')
print(f'Flight Airtable default table: {default_table}')
print('Execution policy: Google Flights first and deeply. Use the exact-date results page, date grid, price graph, and calendar before giving up.')
print('Execution policy: If an OTA page is blocked in the browser, prefer Firecrawl-backed extraction first when credits are available, then other fallbacks.')
print('Execution policy: Persist grounded top options to Airtable as soon as they are ready rather than leaving persistence to the very end of the run.')
