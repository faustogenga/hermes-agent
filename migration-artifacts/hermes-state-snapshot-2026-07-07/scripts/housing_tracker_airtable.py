#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

MAIN_ENV = Path.home() / '.hermes' / '.env'
PROFILE_ENV = Path.home() / '.hermes' / 'profiles' / 'lead-hunter-brussels' / '.env'
AIRTABLE_API = 'https://api.airtable.com/v0'
AIRTABLE_META_API = 'https://api.airtable.com/v0/meta'
SUMMARY_TABLE = 'Housing Run Summaries'
COVERAGE_TABLE = 'Housing Run Coverage'
LISTING_KEY = 'Listing Key'
SUMMARY_KEY = 'Run Key'
COVERAGE_KEY = 'Run Key'


def load_env_file(path: Path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith('#') or '=' not in s:
            continue
        key, value = s.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env_file(MAIN_ENV)
load_env_file(PROFILE_ENV)


def env(name: str, default: str = '') -> str:
    return os.getenv(name, default).strip()


def need(name: str) -> str:
    value = env(name)
    if not value:
        print(json.dumps({'error': f'Missing {name}'}))
        sys.exit(2)
    return value


def airtable_base_id() -> str:
    value = env('AIRTABLE_BASE_ID')
    if value:
        return value
    print(json.dumps({'error': 'Missing AIRTABLE_BASE_ID'}))
    sys.exit(2)


def request_json(method: str, url: str, payload=None):
    headers = {
        'Authorization': f"Bearer {need('AIRTABLE_PAT')}",
        'Content-Type': 'application/json',
        'User-Agent': 'HermesHousingHunter-Airtable/1.1',
    }
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(url, method=method, headers=headers, data=data)
    try:
        with urlopen(req, timeout=60) as response:
            body = response.read().decode('utf-8', errors='replace')
            return json.loads(body) if body else {}
    except HTTPError as e:
        body = e.read().decode('utf-8', errors='replace') if e.fp else ''
        print(json.dumps({'error': f'HTTP {e.code}', 'url': url, 'body': body[:4000]}))
        sys.exit(1)
    except URLError as e:
        print(json.dumps({'error': f'URL error: {e.reason}', 'url': url}))
        sys.exit(1)


def chunked(items, size=10):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def list_tables():
    base_id = airtable_base_id()
    url = f"{AIRTABLE_META_API}/bases/{quote(base_id)}/tables"
    return request_json('GET', url).get('tables', [])


def find_table(name: str):
    for table in list_tables():
        if table.get('name') == name:
            return table
    return None


def ensure_listings_table(name: str):
    existing = find_table(name)
    if existing:
        return {'created': False, 'table_id': existing.get('id'), 'table_name': name}

    payload = {
        'name': name,
        'fields': [
            {'name': LISTING_KEY, 'type': 'singleLineText'},
            {'name': 'Run Key', 'type': 'singleLineText'},
            {'name': 'Recorded At', 'type': 'dateTime', 'options': {'dateFormat': {'name': 'iso', 'format': 'YYYY-MM-DD'}, 'timeFormat': {'name': '24hour', 'format': 'HH:mm'}, 'timeZone': 'utc'}},
            {'name': 'Job Name', 'type': 'singleLineText'},
            {'name': 'City', 'type': 'singleLineText'},
            {'name': 'Household Size', 'type': 'number', 'options': {'precision': 0}},
            {'name': 'Title', 'type': 'singleLineText'},
            {'name': 'Source', 'type': 'singleLineText'},
            {'name': 'Listing URL', 'type': 'url'},
            {'name': 'Area', 'type': 'singleLineText'},
            {'name': 'Address', 'type': 'singleLineText'},
            {'name': 'Bedrooms', 'type': 'number', 'options': {'precision': 0}},
            {'name': 'Furnished', 'type': 'singleLineText'},
            {'name': 'Monthly Rent EUR', 'type': 'number', 'options': {'precision': 2}},
            {'name': 'Price Per Person EUR', 'type': 'number', 'options': {'precision': 2}},
            {'name': 'Available From', 'type': 'singleLineText'},
            {'name': 'Lease Type', 'type': 'singleLineText'},
            {'name': 'Score', 'type': 'number', 'options': {'precision': 1}},
            {'name': 'Fit Summary', 'type': 'multilineText'},
            {'name': 'Concerns', 'type': 'multilineText'},
        ],
    }
    base_id = airtable_base_id()
    url = f"{AIRTABLE_META_API}/bases/{quote(base_id)}/tables"
    created = request_json('POST', url, payload)
    return {'created': True, 'table_id': created.get('id'), 'table_name': name}


def ensure_summary_table():
    existing = find_table(SUMMARY_TABLE)
    if existing:
        return {'created': False, 'table_id': existing.get('id'), 'table_name': SUMMARY_TABLE}

    payload = {
        'name': SUMMARY_TABLE,
        'fields': [
            {'name': SUMMARY_KEY, 'type': 'singleLineText'},
            {'name': 'Recorded At', 'type': 'dateTime', 'options': {'dateFormat': {'name': 'iso', 'format': 'YYYY-MM-DD'}, 'timeFormat': {'name': '24hour', 'format': 'HH:mm'}, 'timeZone': 'utc'}},
            {'name': 'Job Name', 'type': 'singleLineText'},
            {'name': 'Table Name', 'type': 'singleLineText'},
            {'name': 'Household Size', 'type': 'number', 'options': {'precision': 0}},
            {'name': 'Reviewed Count', 'type': 'number', 'options': {'precision': 0}},
            {'name': 'New Count', 'type': 'number', 'options': {'precision': 0}},
            {'name': 'Sent Count', 'type': 'number', 'options': {'precision': 0}},
            {'name': 'Summary Message', 'type': 'multilineText'},
            {'name': 'Blocker', 'type': 'multilineText'},
        ],
    }
    base_id = airtable_base_id()
    url = f"{AIRTABLE_META_API}/bases/{quote(base_id)}/tables"
    created = request_json('POST', url, payload)
    return {'created': True, 'table_id': created.get('id'), 'table_name': SUMMARY_TABLE}


def ensure_coverage_table():
    existing = find_table(COVERAGE_TABLE)
    if existing:
        return {'created': False, 'table_id': existing.get('id'), 'table_name': COVERAGE_TABLE}

    payload = {
        'name': COVERAGE_TABLE,
        'fields': [
            {'name': COVERAGE_KEY, 'type': 'singleLineText'},
            {'name': 'Recorded At', 'type': 'dateTime', 'options': {'dateFormat': {'name': 'iso', 'format': 'YYYY-MM-DD'}, 'timeFormat': {'name': '24hour', 'format': 'HH:mm'}, 'timeZone': 'utc'}},
            {'name': 'Job Name', 'type': 'singleLineText'},
            {'name': 'Table Name', 'type': 'singleLineText'},
            {'name': 'Household Size', 'type': 'number', 'options': {'precision': 0}},
            {'name': 'Attempted Sources', 'type': 'multilineText'},
            {'name': 'Accessible Sources', 'type': 'multilineText'},
            {'name': 'Shortlisted Sources', 'type': 'multilineText'},
            {'name': 'Blocked Sources', 'type': 'multilineText'},
            {'name': 'Coverage Notes', 'type': 'multilineText'},
        ],
    }
    base_id = airtable_base_id()
    url = f"{AIRTABLE_META_API}/bases/{quote(base_id)}/tables"
    created = request_json('POST', url, payload)
    return {'created': True, 'table_id': created.get('id'), 'table_name': COVERAGE_TABLE}


def list_records(table_name: str, key_field: str):
    base_id = airtable_base_id()
    url = f"{AIRTABLE_API}/{quote(base_id)}/{quote(table_name)}?pageSize=100&fields%5B%5D={quote(key_field)}"
    records = []
    while True:
        payload = request_json('GET', url)
        records.extend(payload.get('records', []))
        offset = payload.get('offset')
        if not offset:
            break
        url = f"{AIRTABLE_API}/{quote(base_id)}/{quote(table_name)}?pageSize=100&fields%5B%5D={quote(key_field)}&offset={quote(offset)}"
    index = {}
    for record in records:
        value = (record.get('fields') or {}).get(key_field)
        if value:
            index[str(value)] = record['id']
    return index


def normalize_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_number(value):
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_joined_list(value):
    if value is None:
        return None
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
        return '\n'.join(items) if items else None
    return normalize_text(value)


def load_payload(path: str | None):
    if path:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    return json.load(sys.stdin)


def validate_listings_payload(payload: dict):
    required = ['run_key', 'recorded_at', 'job_name', 'city', 'household_size']
    missing = [field for field in required if not normalize_text(payload.get(field))]
    if missing:
        print(json.dumps({'error': 'Missing required payload fields', 'missing': missing}))
        sys.exit(2)
    listings = payload.get('listings')
    if not isinstance(listings, list):
        print(json.dumps({'error': 'Payload must contain a listings list'}))
        sys.exit(2)


def validate_summary_payload(payload: dict):
    required = ['run_key', 'recorded_at', 'job_name', 'table_name']
    missing = [field for field in required if not normalize_text(payload.get(field))]
    if missing:
        print(json.dumps({'error': 'Missing required summary payload fields', 'missing': missing}))
        sys.exit(2)


def validate_coverage_payload(payload: dict):
    required = ['run_key', 'recorded_at', 'job_name', 'table_name']
    missing = [field for field in required if not normalize_text(payload.get(field))]
    if missing:
        print(json.dumps({'error': 'Missing required coverage payload fields', 'missing': missing}))
        sys.exit(2)


def listing_to_fields(payload: dict, listing: dict):
    listing_key = normalize_text(listing.get('listing_key')) or normalize_text(listing.get('listing_url'))
    if not listing_key:
        print(json.dumps({'error': 'Each listing requires listing_key or listing_url'}))
        sys.exit(2)
    return {
        LISTING_KEY: listing_key,
        'Run Key': normalize_text(payload.get('run_key')),
        'Recorded At': normalize_text(payload.get('recorded_at')),
        'Job Name': normalize_text(payload.get('job_name')),
        'City': normalize_text(payload.get('city')),
        'Household Size': normalize_number(payload.get('household_size')),
        'Title': normalize_text(listing.get('title')),
        'Source': normalize_text(listing.get('source')),
        'Listing URL': normalize_text(listing.get('listing_url')),
        'Area': normalize_text(listing.get('area')),
        'Address': normalize_text(listing.get('address')),
        'Bedrooms': normalize_number(listing.get('bedrooms')),
        'Furnished': normalize_text(listing.get('furnished')),
        'Monthly Rent EUR': normalize_number(listing.get('monthly_rent_eur')),
        'Price Per Person EUR': normalize_number(listing.get('price_per_person_eur')),
        'Available From': normalize_text(listing.get('available_from')),
        'Lease Type': normalize_text(listing.get('lease_type')),
        'Score': normalize_number(listing.get('score')),
        'Fit Summary': normalize_text(listing.get('fit_summary')),
        'Concerns': normalize_text(listing.get('concerns')),
    }


def summary_to_fields(payload: dict):
    return {
        SUMMARY_KEY: normalize_text(payload.get('run_key')),
        'Recorded At': normalize_text(payload.get('recorded_at')),
        'Job Name': normalize_text(payload.get('job_name')),
        'Table Name': normalize_text(payload.get('table_name')),
        'Household Size': normalize_number(payload.get('household_size')),
        'Reviewed Count': normalize_number(payload.get('reviewed_count')),
        'New Count': normalize_number(payload.get('new_count')),
        'Sent Count': normalize_number(payload.get('sent_count')),
        'Summary Message': normalize_text(payload.get('summary_message')),
        'Blocker': normalize_text(payload.get('blocker')),
    }


def coverage_to_fields(payload: dict):
    return {
        COVERAGE_KEY: normalize_text(payload.get('run_key')),
        'Recorded At': normalize_text(payload.get('recorded_at')),
        'Job Name': normalize_text(payload.get('job_name')),
        'Table Name': normalize_text(payload.get('table_name')),
        'Household Size': normalize_number(payload.get('household_size')),
        'Attempted Sources': normalize_joined_list(payload.get('attempted_sources')),
        'Accessible Sources': normalize_joined_list(payload.get('accessible_sources')),
        'Shortlisted Sources': normalize_joined_list(payload.get('shortlisted_sources')),
        'Blocked Sources': normalize_joined_list(payload.get('blocked_sources')),
        'Coverage Notes': normalize_text(payload.get('coverage_notes')),
    }


def upsert_records(table_name: str, key_field: str, materialized_records: list[dict]):
    existing = list_records(table_name, key_field)
    create_records = []
    update_records = []
    for fields in materialized_records:
        key = fields[key_field]
        if key in existing:
            update_records.append({'id': existing[key], 'fields': fields})
        else:
            create_records.append({'fields': fields})

    base_id = airtable_base_id()
    created = 0
    updated = 0
    if create_records:
        url = f"{AIRTABLE_API}/{quote(base_id)}/{quote(table_name)}"
        for batch in chunked(create_records, 10):
            result = request_json('POST', url, {'records': batch, 'typecast': True})
            created += len(result.get('records', []))
    if update_records:
        url = f"{AIRTABLE_API}/{quote(base_id)}/{quote(table_name)}"
        for batch in chunked(update_records, 10):
            result = request_json('PATCH', url, {'records': batch, 'typecast': True})
            updated += len(result.get('records', []))
    return {'created': created, 'updated': updated, 'total': len(materialized_records)}


def cmd_ensure_table(args):
    print(json.dumps(ensure_listings_table(args.table)))


def cmd_ensure_summary_table(args):
    print(json.dumps(ensure_summary_table()))


def cmd_ensure_coverage_table(args):
    print(json.dumps(ensure_coverage_table()))


def cmd_upsert_listings(args):
    payload = load_payload(args.payload_file)
    validate_listings_payload(payload)
    ensure = ensure_listings_table(args.table)
    records = []
    for listing in payload.get('listings', []):
        fields = {k: v for k, v in listing_to_fields(payload, listing).items() if v is not None}
        records.append(fields)
    result = upsert_records(args.table, LISTING_KEY, records) if records else {'created': 0, 'updated': 0, 'total': 0}
    print(json.dumps({'table': args.table, 'ensured': ensure, **result}))


def cmd_upsert_summary(args):
    payload = load_payload(args.payload_file)
    validate_summary_payload(payload)
    ensure = ensure_summary_table()
    fields = {k: v for k, v in summary_to_fields(payload).items() if v is not None}
    result = upsert_records(SUMMARY_TABLE, SUMMARY_KEY, [fields])
    print(json.dumps({'table': SUMMARY_TABLE, 'ensured': ensure, **result}))


def cmd_upsert_coverage(args):
    payload = load_payload(args.payload_file)
    validate_coverage_payload(payload)
    ensure = ensure_coverage_table()
    fields = {k: v for k, v in coverage_to_fields(payload).items() if v is not None}
    result = upsert_records(COVERAGE_TABLE, COVERAGE_KEY, [fields])
    print(json.dumps({'table': COVERAGE_TABLE, 'ensured': ensure, **result}))


def build_parser():
    parser = argparse.ArgumentParser(description='Airtable sync for Brussels housing tracking')
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('ensure-table')
    p.add_argument('--table', required=True)
    p.set_defaults(func=cmd_ensure_table)

    p = sub.add_parser('ensure-summary-table')
    p.set_defaults(func=cmd_ensure_summary_table)

    p = sub.add_parser('ensure-coverage-table')
    p.set_defaults(func=cmd_ensure_coverage_table)

    p = sub.add_parser('upsert-listings')
    p.add_argument('--table', required=True)
    p.add_argument('--payload-file')
    p.set_defaults(func=cmd_upsert_listings)

    p = sub.add_parser('upsert-summary')
    p.add_argument('--payload-file')
    p.set_defaults(func=cmd_upsert_summary)

    p = sub.add_parser('upsert-coverage')
    p.add_argument('--payload-file')
    p.set_defaults(func=cmd_upsert_coverage)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
