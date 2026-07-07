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
LEAD_HUNTER_ENV = Path.home() / '.hermes' / 'profiles' / 'lead-hunter-brussels' / '.env'
AIRTABLE_API = 'https://api.airtable.com/v0'
AIRTABLE_META_API = 'https://api.airtable.com/v0/meta'
DEFAULT_TABLE = 'Flight Observations'
PRIMARY_FIELD = 'Observation Key'


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
load_env_file(LEAD_HUNTER_ENV)


def env(name: str, default: str = '') -> str:
    return os.getenv(name, default).strip()


def need(name: str) -> str:
    value = env(name)
    if not value:
        print(json.dumps({'error': f'Missing {name}'}))
        sys.exit(2)
    return value


def airtable_base_id() -> str:
    base_id = env('AIRTABLE_BASE_ID')
    if base_id:
        return base_id
    print(json.dumps({'error': 'Missing AIRTABLE_BASE_ID. Set it in ~/.hermes/.env or the lead-hunter profile env.'}))
    sys.exit(2)


def flights_table() -> str:
    return env('AIRTABLE_FLIGHTS_TABLE', DEFAULT_TABLE)


def request_json(method: str, url: str, payload=None):
    headers = {
        'Authorization': f"Bearer {need('AIRTABLE_PAT')}",
        'Content-Type': 'application/json',
        'User-Agent': 'HermesFlightFinder-Airtable/1.0',
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


def ensure_table():
    name = flights_table()
    tables = list_tables()
    for table in tables:
        if table.get('name') == name:
            return {'created': False, 'table_id': table.get('id'), 'table_name': name, 'field_count': len(table.get('fields', []))}

    base_id = airtable_base_id()
    payload = {
        'name': name,
        'fields': [
            {'name': PRIMARY_FIELD, 'type': 'singleLineText'},
            {'name': 'Run Key', 'type': 'singleLineText'},
            {'name': 'Recorded At', 'type': 'dateTime', 'options': {'dateFormat': {'name': 'iso', 'format': 'YYYY-MM-DD'}, 'timeFormat': {'name': '24hour', 'format': 'HH:mm'}, 'timeZone': 'utc'}},
            {'name': 'Job Name', 'type': 'singleLineText'},
            {'name': 'Route Key', 'type': 'singleLineText'},
            {'name': 'Route Label', 'type': 'singleLineText'},
            {'name': 'Origin Airport', 'type': 'singleLineText'},
            {'name': 'Destination Airport', 'type': 'singleLineText'},
            {'name': 'Rank', 'type': 'number', 'options': {'precision': 0}},
            {'name': 'Price EUR', 'type': 'number', 'options': {'precision': 2}},
            {'name': 'Currency', 'type': 'singleLineText'},
            {'name': 'Departure Date', 'type': 'singleLineText'},
            {'name': 'Return Date', 'type': 'singleLineText'},
            {'name': 'Airlines', 'type': 'singleLineText'},
            {'name': 'Stops', 'type': 'singleLineText'},
            {'name': 'Duration Summary', 'type': 'singleLineText'},
            {'name': 'Source', 'type': 'singleLineText'},
            {'name': 'Backup Sources', 'type': 'singleLineText'},
            {'name': 'Fare Assessment', 'type': 'singleLineText'},
            {'name': 'Booking URL', 'type': 'url'},
            {'name': 'Notes', 'type': 'multilineText'},
        ],
    }
    url = f"{AIRTABLE_META_API}/bases/{quote(base_id)}/tables"
    created = request_json('POST', url, payload)
    return {'created': True, 'table_id': created.get('id'), 'table_name': name, 'field_count': len(created.get('fields', []))}


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


def load_payload(path: str | None):
    if path:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    return json.load(sys.stdin)


def observation_to_fields(payload: dict, observation: dict, rank: int):
    run_key = normalize_text(payload.get('run_key'))
    route_key = normalize_text(payload.get('route_key'))
    observation_key = normalize_text(observation.get('observation_key')) or f'{run_key}|rank:{rank}'
    payload_notes = payload.get('notes') if isinstance(payload.get('notes'), dict) else {}
    backup_checks = payload_notes.get('backup_checks') if isinstance(payload_notes, dict) else None
    backup_notes = '\n'.join(str(item).strip() for item in (backup_checks or []) if str(item).strip())
    return {
        PRIMARY_FIELD: observation_key,
        'Run Key': run_key,
        'Recorded At': normalize_text(payload.get('recorded_at')),
        'Job Name': normalize_text(payload.get('job_name')),
        'Route Key': route_key,
        'Route Label': normalize_text(payload.get('route_label')),
        'Origin Airport': normalize_text(payload.get('origin_airport')),
        'Destination Airport': normalize_text(payload.get('destination_airport')),
        'Rank': rank,
        'Price EUR': normalize_number(observation.get('price_eur', observation.get('price'))),
        'Currency': normalize_text(observation.get('currency') or payload.get('currency') or 'EUR'),
        'Departure Date': normalize_text(observation.get('departure_date') or observation.get('outbound_date')),
        'Return Date': normalize_text(observation.get('return_date') or observation.get('inbound_date')),
        'Airlines': normalize_text(observation.get('airlines')),
        'Stops': normalize_text(observation.get('stops')),
        'Duration Summary': normalize_text(observation.get('duration_summary') or observation.get('duration')),
        'Source': normalize_text(observation.get('source')),
        'Backup Sources': normalize_text(observation.get('backup_sources') or backup_notes),
        'Fare Assessment': normalize_text(observation.get('fare_assessment') or observation.get('trip_type')),
        'Booking URL': normalize_text(observation.get('booking_url') or observation.get('url')),
        'Notes': normalize_text(observation.get('notes') or observation.get('summary')),
    }


def validate_payload(payload: dict):
    required = ['run_key', 'recorded_at', 'job_name', 'route_key', 'route_label', 'origin_airport', 'destination_airport']
    missing = [field for field in required if not normalize_text(payload.get(field))]
    if missing:
        print(json.dumps({'error': 'Missing required payload fields', 'missing': missing}))
        sys.exit(2)
    observations = payload.get('observations')
    if not isinstance(observations, list) or not observations:
        print(json.dumps({'error': 'Payload must contain a non-empty observations list'}))
        sys.exit(2)
    if len(observations) > 3:
        print(json.dumps({'error': 'Observations list may contain at most 3 entries'}))
        sys.exit(2)


def upsert_payload(payload: dict, dry_run: bool = False):
    validate_payload(payload)
    ensure = ensure_table()
    table = flights_table()
    existing = list_records(table, PRIMARY_FIELD)
    observations = payload['observations'][:3]
    create_records = []
    update_records = []
    materialized = []

    for idx, observation in enumerate(observations, start=1):
        fields = {k: v for k, v in observation_to_fields(payload, observation, idx).items() if v is not None}
        materialized.append(fields)
        key = fields[PRIMARY_FIELD]
        if key in existing:
            update_records.append({'id': existing[key], 'fields': fields})
        else:
            create_records.append({'fields': fields})

    if dry_run:
        return {
            'table': table,
            'ensured': ensure,
            'create_count': len(create_records),
            'update_count': len(update_records),
            'records': materialized,
            'dry_run': True,
        }

    base_id = airtable_base_id()
    created = 0
    updated = 0
    if create_records:
        url = f"{AIRTABLE_API}/{quote(base_id)}/{quote(table)}"
        for batch in chunked(create_records, 10):
            result = request_json('POST', url, {'records': batch, 'typecast': True})
            created += len(result.get('records', []))
    if update_records:
        url = f"{AIRTABLE_API}/{quote(base_id)}/{quote(table)}"
        for batch in chunked(update_records, 10):
            result = request_json('PATCH', url, {'records': batch, 'typecast': True})
            updated += len(result.get('records', []))
    return {
        'table': table,
        'ensured': ensure,
        'create_count': created,
        'update_count': updated,
        'record_count': len(materialized),
        'keys': [row[PRIMARY_FIELD] for row in materialized],
        'dry_run': False,
    }


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd', required=True)

    sub.add_parser('ensure-table')

    upsert = sub.add_parser('upsert')
    upsert.add_argument('--payload-file')
    upsert.add_argument('--dry-run', action='store_true')

    args = parser.parse_args()

    if args.cmd == 'ensure-table':
        print(json.dumps(ensure_table(), indent=2))
        return
    if args.cmd == 'upsert':
        payload = load_payload(args.payload_file)
        print(json.dumps(upsert_payload(payload, dry_run=args.dry_run), indent=2))
        return


if __name__ == '__main__':
    main()
