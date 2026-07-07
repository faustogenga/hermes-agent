#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_TABLE_ID = "tblIdSJxQUJZGsuUE"
MERGE_FIELD_LOGICAL = "Job Key"
ALLOWED_FIELDS = [
    "Job Key",
    "Job Title",
    "Club Name",
    "Role Type",
    "EMAIL SENT?",
    "Location",
    "Country",
    "Source Site",
    "Source Type",
    "Job URL",
    "Canonical URL",
    "Search Query",
    "Posted Text",
    "Posted Date Raw",
    "Added to table at",
    "Summary",
    "Email",
    "Phone Number",
    "Instagram",
    "Facebook",
    "Other",
]
FIELD_ALIASES = {
    "Job Key": ["Job Key", "\ufeffJob Key"],
    "EMAIL SENT?": ["EMAIL SENT?", "Email Sent?"],
    "Added to table at": ["Added to table at", "First Seen At"],
    "Email": ["Email", "email"],
    "Phone Number": ["Phone Number", "Phone", "phonenumber", "phone number"],
    "Instagram": ["Instagram", "instagram"],
    "Facebook": ["Facebook", "facebook"],
    "Other": ["Other", "other"],
}
URL_FIELDS = ("Canonical URL", "Job URL")


def die(msg: str, code: int = 1) -> None:
    print(json.dumps({"success": False, "error": msg}, ensure_ascii=False))
    raise SystemExit(code)


def env(name: str, *fallbacks: str) -> str | None:
    for key in (name, *fallbacks):
        value = os.getenv(key)
        if value:
            return value
    return None


def load_env() -> tuple[str, str, str]:
    pat = env("AIRTABLE_PAT", "AIRTABLE_API_KEY")
    base = env("AIRTABLE_PADEL_BASE_ID", "AIRTABLE_BASE_ID")
    table = env("AIRTABLE_PADEL_TABLE_ID", "AIRTABLE_TABLE_ID") or DEFAULT_TABLE_ID
    if not pat:
        die("Missing AIRTABLE_PAT/AIRTABLE_API_KEY in environment")
    if not base:
        die("Missing AIRTABLE_PADEL_BASE_ID/AIRTABLE_BASE_ID in environment")
    return pat, base, table


def airtable_request(method: str, url: str, pat: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        die(f"Airtable HTTP {e.code}: {body}")


def get_table_schema(pat: str, base: str, table_id: str) -> dict[str, Any]:
    url = f"https://api.airtable.com/v0/meta/bases/{base}/tables"
    data = airtable_request("GET", url, pat)
    for table in data.get("tables", []):
        if table.get("id") == table_id:
            return table
    die(f"Table not found in base schema: {table_id}")


def resolve_field_name(logical_name: str, available_names: set[str]) -> str | None:
    for candidate in FIELD_ALIASES.get(logical_name, [logical_name]):
        if candidate in available_names:
            return candidate
    return logical_name if logical_name in available_names else None


def build_field_name_map(table_schema: dict[str, Any]) -> dict[str, str]:
    available_names = {field["name"] for field in table_schema.get("fields", [])}
    mapping: dict[str, str] = {}
    for logical_name in ALLOWED_FIELDS:
        actual_name = resolve_field_name(logical_name, available_names)
        if actual_name:
            mapping[logical_name] = actual_name
    if MERGE_FIELD_LOGICAL not in mapping:
        die(f"Required merge field missing from target table: {MERGE_FIELD_LOGICAL}")
    return mapping


def normalize_url(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    parsed = urllib.parse.urlsplit(text)
    if parsed.scheme or parsed.netloc:
        netloc = parsed.netloc.lower()
        path = re.sub(r"/+", "/", parsed.path or "/")
        if path != "/":
            path = path.rstrip("/")
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        query = [(k, v) for k, v in query if not k.lower().startswith("utm_")]
        query_text = urllib.parse.urlencode(query, doseq=True)
        normalized = f"https://{netloc}{path}"
        if query_text:
            normalized += f"?{query_text}"
        return normalized
    return text.rstrip("/")


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text or None


def semantic_key(record: dict[str, Any]) -> str | None:
    title = normalize_text(record.get("Job Title"))
    club = normalize_text(record.get("Club Name"))
    location = normalize_text(record.get("Location"))
    if not (title and club and location):
        return None
    return f"{title}|{club}|{location}"


def normalize_identifier_text(value: Any) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [token for token in text.split() if token]
    collapsed: list[str] = []
    i = 0
    while i < len(tokens):
        if len(tokens[i]) == 1:
            j = i
            letters: list[str] = []
            while j < len(tokens) and len(tokens[j]) == 1:
                letters.append(tokens[j])
                j += 1
            if len(letters) > 1:
                collapsed.append("".join(letters))
            else:
                collapsed.extend(letters)
            i = j
            continue
        collapsed.append(tokens[i])
        i += 1
    text = " ".join(collapsed).strip()
    return text or None


def normalized_role_family(record: dict[str, Any]) -> str | None:
    source = record.get("Role Type") or record.get("Job Title")
    text = normalize_identifier_text(source)
    if not text:
        return None

    replacements = {
        "padel academy": "padel",
        "academy coach": "coach",
        "coach de": "coach",
        "director de": "director",
        "profesor": "coach",
        "profesora": "coach",
        "monitor": "coach",
        "monitora": "coach",
        "entrenador": "coach",
        "entrenadora": "coach",
        "instructor": "coach",
        "instructora": "coach",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()

    if "director" in text:
        return "director of padel"
    if "head" in text and "coach" in text:
        return "head padel coach"
    if "senior" in text and "coach" in text:
        return "senior padel coach"
    if "assistant" in text and "coach" in text:
        return "assistant padel coach"
    if "coach" in text:
        return "padel coach"
    return text or None


def overlap_key(record: dict[str, Any]) -> str | None:
    role = normalized_role_family(record)
    club = normalize_identifier_text(record.get("Club Name"))
    location = normalize_identifier_text(record.get("Location"))
    if not (role and club and location):
        return None
    return f"{role}|{club}|{location}"


def deterministic_job_key(record: dict[str, Any]) -> str:
    for field in URL_FIELDS:
        normalized_url = normalize_url(record.get(field))
        if normalized_url:
            return f"url:{normalized_url}"
    semantic = semantic_key(record)
    if semantic:
        return f"sem:{semantic}"
    existing = record.get("Job Key")
    if existing:
        return str(existing).strip()
    die("Unable to derive deterministic Job Key")


def fetch_existing_records(pat: str, base: str, table_id: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset: str | None = None
    while True:
        query = {"pageSize": 100}
        if offset:
            query["offset"] = offset
        url = f"https://api.airtable.com/v0/{base}/{table_id}?{urllib.parse.urlencode(query)}"
        data = airtable_request("GET", url, pat)
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    return records


def build_existing_indexes(existing_records: list[dict[str, Any]], merge_field_actual: str) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str], set[str]]:
    by_canonical: dict[str, str] = {}
    by_job_url: dict[str, str] = {}
    by_semantic: dict[str, str] = {}
    by_overlap: dict[str, str] = {}
    existing_merge_keys: set[str] = set()
    for row in existing_records:
        fields = row.get("fields", {})
        merge_value = fields.get(merge_field_actual)
        if not merge_value:
            continue
        merge_key = str(merge_value).strip()
        existing_merge_keys.add(merge_key)
        canonical = normalize_url(fields.get("Canonical URL"))
        if canonical and canonical not in by_canonical:
            by_canonical[canonical] = merge_key
        job_url = normalize_url(fields.get("Job URL"))
        if job_url and job_url not in by_job_url:
            by_job_url[job_url] = merge_key
        logical_semantic = semantic_key({
            "Job Title": fields.get("Job Title"),
            "Club Name": fields.get("Club Name"),
            "Location": fields.get("Location"),
        })
        if logical_semantic and logical_semantic not in by_semantic:
            by_semantic[logical_semantic] = merge_key
        logical_overlap = overlap_key({
            "Role Type": fields.get("Role Type"),
            "Job Title": fields.get("Job Title"),
            "Club Name": fields.get("Club Name"),
            "Location": fields.get("Location"),
        })
        if logical_overlap and logical_overlap not in by_overlap:
            by_overlap[logical_overlap] = merge_key
    return by_canonical, by_job_url, by_semantic, by_overlap, existing_merge_keys


def normalize_record(record: dict[str, Any], field_name_map: dict[str, str]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for logical_name in ALLOWED_FIELDS:
        actual_name = field_name_map.get(logical_name)
        if not actual_name:
            continue

        value = record.get(logical_name)
        if value is None and logical_name == "Added to table at":
            value = record.get("First Seen At")

        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                continue
        normalized[actual_name] = value
    return {"fields": normalized}


def chunks(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def main() -> None:
    if len(sys.argv) != 2:
        die("Usage: upsert_padel_jobs_airtable.py /path/to/jobs.json")
    path = sys.argv[1]
    if not os.path.exists(path):
        die(f"JSON file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        die("Expected top-level JSON array")

    pat, base, table_id = load_env()
    table_schema = get_table_schema(pat, base, table_id)
    field_name_map = build_field_name_map(table_schema)
    merge_field_actual = field_name_map[MERGE_FIELD_LOGICAL]

    existing_records = fetch_existing_records(pat, base, table_id)
    by_canonical, by_job_url, by_semantic, by_overlap, existing_merge_keys = build_existing_indexes(existing_records, merge_field_actual)

    deduped: dict[str, dict[str, Any]] = {}
    created_keys: set[str] = set()
    updated_keys: set[str] = set()
    matched_existing_by: dict[str, str] = {}

    for item in raw:
        if not isinstance(item, dict):
            continue

        record = dict(item)
        merge_key = None
        canonical = normalize_url(record.get("Canonical URL"))
        job_url = normalize_url(record.get("Job URL"))
        sem_key = semantic_key(record)
        ol_key = overlap_key(record)

        if canonical and canonical in by_canonical:
            merge_key = by_canonical[canonical]
            matched_existing_by[merge_key] = "canonical_url"
        elif job_url and job_url in by_job_url:
            merge_key = by_job_url[job_url]
            matched_existing_by[merge_key] = "job_url"
        elif sem_key and sem_key in by_semantic:
            merge_key = by_semantic[sem_key]
            matched_existing_by[merge_key] = "semantic"
        elif ol_key and ol_key in by_overlap:
            merge_key = by_overlap[ol_key]
            matched_existing_by[merge_key] = "role_club_location"
        else:
            merge_key = deterministic_job_key(record)

        record[MERGE_FIELD_LOGICAL] = merge_key

        if merge_key in existing_merge_keys:
            updated_keys.add(merge_key)
            record.pop("Added to table at", None)
            record.pop("First Seen At", None)
        else:
            created_keys.add(merge_key)
            existing_merge_keys.add(merge_key)
            if not record.get("Added to table at") and not record.get("First Seen At"):
                record["Added to table at"] = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
            if canonical:
                by_canonical.setdefault(canonical, merge_key)
            if job_url:
                by_job_url.setdefault(job_url, merge_key)
            if sem_key:
                by_semantic.setdefault(sem_key, merge_key)
            if ol_key:
                by_overlap.setdefault(ol_key, merge_key)

        normalized = normalize_record(record, field_name_map)
        deduped[merge_key] = normalized

    records = list(deduped.values())

    if not records:
        print(json.dumps({
            "success": True,
            "upserted": 0,
            "created": 0,
            "updated": 0,
            "message": "No records to upsert",
            "base_id": base,
            "table_id": table_id,
            "table_name": table_schema.get("name"),
            "merge_field": merge_field_actual,
        }, ensure_ascii=False))
        return

    url = f"https://api.airtable.com/v0/{base}/{table_id}"

    upserted = 0
    for batch in chunks(records, 10):
        payload = {
            "performUpsert": {"fieldsToMergeOn": [merge_field_actual]},
            "typecast": True,
            "records": batch,
        }
        result = airtable_request("PATCH", url, pat, payload)
        upserted += len(result.get("records", []))
        time.sleep(0.25)

    print(json.dumps({
        "success": True,
        "upserted": upserted,
        "created": len(created_keys),
        "updated": len(updated_keys),
        "base_id": base,
        "table_id": table_id,
        "table_name": table_schema.get("name"),
        "merge_field": merge_field_actual,
        "matched_existing_by": matched_existing_by,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
