#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import urllib.parse
from collections import Counter
from pathlib import Path

import requests

BASE_ID = os.getenv("AIRTABLE_PADEL_BASE_ID", "appFiBKeB4uE6os5e")
TABLE_ID = os.getenv("AIRTABLE_PADEL_TABLE_ID", "tblnAtmjNbrHI02OT")
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
TIMEOUT = 25
JOBBOARD_DOMAINS = {
    "linkedin.com",
    "uk.linkedin.com",
    "es.linkedin.com",
    "ae.linkedin.com",
    "id.linkedin.com",
    "computrabajo.com",
    "co.computrabajo.com",
    "indeed.com",
    "es.indeed.com",
    "glassdoor.com",
    "jooble.org",
    "talent.com",
    "jobs.smartrecruiters.com",
    "smartrecruiters.com",
    "mycareersfuture.gov.sg",
    "magneto365.com",
    "leisurejobs.com",
    "empleodeporte.com",
    "fap.es",
}
NOISY_RESULT_DOMAINS = JOBBOARD_DOMAINS | {
    "facebook.com",
    "www.facebook.com",
    "instagram.com",
    "www.instagram.com",
    "linkedin.com",
    "www.linkedin.com",
    "x.com",
    "twitter.com",
    "www.twitter.com",
    "youtube.com",
    "www.youtube.com",
    "tiktok.com",
    "www.tiktok.com",
    "linktr.ee",
    "padelmapusa.com",
    "padeldir.com",
    "padelink.cat",
    "gimnasios.es",
    "padelusa.com",
    "padel-magazine.es",
    "lta.org.uk",
    "rspa.net",
}
SOCIAL_RE = re.compile(r"https?://(?:www\.)?(instagram|facebook|linkedin|x|twitter|tiktok|youtube)\.com/[^\s\"'<>#)]+", re.I)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+\d[\d\s()./-]{6,}\d|\(\+?\d{1,4}\)[\d\s()./-]{5,}\d)")
TOKENS_DROP = {
    "club", "clubs", "hotel", "resort", "padel", "sports", "sport", "the",
    "ltd", "limited", "pte", "sa", "sas", "sl", "llc", "inc", "company",
    "society", "urban", "fitness", "academy", "collective",
}
SKIP_PATTERNS = [
    "client club",
    "client resort",
    "importante empresa del sector",
    "hotel resort en",
]
EXCLUDED_EMAIL_PREFIXES = (
    "noreply", "no-reply", "donotreply", "privacy", "example", "sentry",
)
MANUAL_DOMAINS = {
    "Padel Tree LTD": "https://www.padeltree.co.uk/",
    "Padel Haus": "https://www.padel.haus/",
    "Vall Parc": "https://www.vallparc.com/",
    "DUIN SPORTS CLUBS": "https://www.duinclub.com/",
    "Jungle Padel": "https://junglepadel.com/",
    "Rocket Padel": "https://www.rocketpadel.com/",
    "David Lloyd Clubs": "https://www.davidlloyd.co.uk/",
    "The Gleneagles Hotel": "https://gleneagles.com/",
    "Gleneagles": "https://gleneagles.com/",
    "Federación Andaluza de Pádel": "https://fap.es/",
    "Pádel Acción": "https://www.padelaccion.com/",
    "Padel&": "https://www.padeland.us/",
    "Padel& Syosset": "https://www.padeland.us/",
    "Slazenger Padel Club": "https://www.slazengerpadelclubs.com/",
    "Pulse Padel Club": "https://www.pulsepadel.us/",
    "Park Padel": "https://parkpadel.com/",
    "the Padel Collective": "https://www.thepadelcollective.club/",
    "Social Sports Society (S3 Padel)": "https://www.socialsportssociety.com/",
    "MyPT": "https://mypt.ae/",
    "Mad Swans": "https://www.madswans.com/",
    "UFIT - URBAN FITNESS PTE. LTD.": "https://www.ufit.com.sg/",
}


def load_env() -> None:
    env_path = Path.home() / ".hermes" / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def airtable_headers() -> dict[str, str]:
    token = os.getenv("AIRTABLE_PAT") or os.getenv("AIRTABLE_API_KEY")
    if not token:
        raise SystemExit("Missing AIRTABLE_PAT/AIRTABLE_API_KEY")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def api_get(url: str) -> dict:
    resp = requests.get(url, headers=airtable_headers(), timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def api_patch(records: list[dict]) -> dict:
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}"
    payload = {"typecast": True, "records": records}
    resp = requests.patch(url, headers=airtable_headers(), json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_rows() -> list[dict]:
    formula = "OR({EMAIL SENT?}=0, {EMAIL SENT?}=FALSE(), {EMAIL SENT?}='')"
    base_url = (
        f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}?pageSize=100"
        f"&filterByFormula={urllib.parse.quote(formula, safe='')}"
    )
    rows = []
    url = base_url
    while True:
        data = api_get(url)
        rows.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            return rows
        url = base_url + f"&offset={urllib.parse.quote(offset)}"


def registrable_domain(url: str | None) -> str | None:
    if not url:
        return None
    host = urllib.parse.urlsplit(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return None
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "gov", "ac"}:
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def tokenize(text: str) -> list[str]:
    raw = re.findall(r"[A-Za-zÀ-ÿ0-9]+", (text or "").lower())
    tokens = [t for t in raw if len(t) >= 3 and t not in TOKENS_DROP]
    return tokens


def is_hidden_or_intermediary(club: str) -> bool:
    text = (club or "").lower()
    return any(pat in text for pat in SKIP_PATTERNS)


def ddg_links(query: str) -> list[str]:
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    html = resp.text
    links = []
    for href in re.findall(r'<a[^>]+class="result__a"[^>]+href="(.*?)"', html):
        href = href.replace("&amp;", "&")
        if href.startswith("//duckduckgo.com/l/?"):
            parsed = urllib.parse.urlsplit("https:" + href)
            target = urllib.parse.parse_qs(parsed.query).get("uddg", [None])[0]
            if target:
                href = target
        links.append(href)
    return links


def domain_matches_any(domain: str | None, blocked: set[str]) -> bool:
    if not domain:
        return False
    for candidate in blocked:
        if domain == candidate or domain.endswith("." + candidate):
            return True
    return False


def score_candidate(url: str, club_name: str) -> int:
    domain = registrable_domain(url) or ""
    if domain_matches_any(domain, NOISY_RESULT_DOMAINS):
        return -100
    path = urllib.parse.urlsplit(url).path.lower()
    score = 0
    club_tokens = tokenize(club_name)
    domain_text = domain.replace(".", " ")
    for token in club_tokens:
        if token in domain_text:
            score += 3
    if path in {"", "/", "/en", "/en/"}:
        score += 2
    if any(word in path for word in ["contact", "about", "home"]):
        score += 1
    if url.startswith("https://"):
        score += 1
    return score


def pick_official_seed(row: dict) -> tuple[str | None, str]:
    fields = row.get("fields", {})
    club = fields.get("Club Name") or ""
    if club in MANUAL_DOMAINS:
        return MANUAL_DOMAINS[club], "manual"

    candidates = []
    for source_url in [fields.get("Canonical URL"), fields.get("Job URL")]:
        domain = registrable_domain(source_url)
        if source_url and domain and not domain_matches_any(domain, JOBBOARD_DOMAINS | NOISY_RESULT_DOMAINS):
            root = f"https://{domain}/"
            base_score = score_candidate(root, club)
            if base_score >= 4:
                candidates.append((base_score + 2, root, "job_url_domain"))

    queries = [
        f'"{club}" official website',
        f'"{club}" padel',
        f'"{club}" contact',
    ]
    for query in queries:
        try:
            links = ddg_links(query)[:6]
        except Exception:
            continue
        for link in links:
            score = score_candidate(link, club)
            if score > 0:
                candidates.append((score, link, f"search:{query}"))
        if candidates:
            break

    if not candidates:
        return None, "no_candidate"

    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[0]
    return best[1], best[2]


def absolute_links(base_url: str, html: str) -> list[str]:
    hrefs = []
    for href in re.findall(r'href=["\'](.*?)["\']', html, re.I):
        hrefs.append(urllib.parse.urljoin(base_url, href))
    return hrefs


def clean_email(email: str, allowed_domain: str | None) -> str | None:
    email = email.strip().lower().strip('.,;:')
    if "@" not in email:
        return None
    if not email or any(email.startswith(prefix) for prefix in EXCLUDED_EMAIL_PREFIXES):
        return None
    local, host = email.split("@", 1)
    if not local or not host:
        return None
    if allowed_domain and registrable_domain("https://" + host) != allowed_domain:
        return None
    return email


def clean_phone(phone: str) -> str | None:
    raw = phone.strip()
    if "*" in raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 9 or len(digits) > 15:
        return None
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    return re.sub(r"\s+", " ", raw)


def extract_contacts(seed_url: str) -> dict:
    domain = registrable_domain(seed_url)
    queue = [seed_url]
    seen = set()
    mailto_emails = []
    visible_emails = []
    tel_phones = []
    visible_phones = []
    socials = []
    fetched_pages = []

    while queue and len(seen) < 6:
        url = queue.pop(0)
        norm = url.split("#", 1)[0]
        if norm in seen:
            continue
        if registrable_domain(norm) != domain:
            continue
        seen.add(norm)
        try:
            resp = requests.get(norm, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code >= 400 or "text/html" not in resp.headers.get("Content-Type", ""):
                continue
        except Exception:
            continue
        html = resp.text
        fetched_pages.append(norm)

        for href in re.findall(r'href=["\']mailto:([^"\'#?]+)', html, re.I):
            email = clean_email(urllib.parse.unquote(href), domain)
            if email:
                mailto_emails.append(email)
        for found in EMAIL_RE.findall(html):
            email = clean_email(found, domain)
            if email:
                visible_emails.append(email)

        for href in re.findall(r'href=["\']tel:([^"\']+)', html, re.I):
            phone = clean_phone(urllib.parse.unquote(href))
            if phone:
                tel_phones.append(phone)
        for found in PHONE_RE.findall(html):
            phone = clean_phone(found)
            if phone:
                visible_phones.append(phone)

        for social in SOCIAL_RE.finditer(html):
            link = social.group(0).rstrip('.,;')
            socials.append(link)

        for link in absolute_links(norm, html):
            parsed = urllib.parse.urlsplit(link)
            if registrable_domain(link) != domain:
                continue
            path = parsed.path.lower()
            if any(key in path for key in ["contact", "about", "team", "club", "location"]):
                queue.append(link)

    email = choose_best_email(mailto_emails, visible_emails)
    phone = choose_best_phone(tel_phones, visible_phones)
    instagram, facebook, other = choose_social_buckets(socials)
    return {
        "seed_domain": domain,
        "fetched_pages": fetched_pages,
        "Email": email,
        "Phone Number": phone,
        "Instagram": instagram,
        "Facebook": facebook,
        "Other": other,
    }


def choose_best_email(mailto_emails: list[str], visible_emails: list[str]) -> str | None:
    generic_prefixes = ("info@", "hello@", "contact@", "enquiries@", "enquiry@", "office@", "admin@", "reception@", "bookings@", "reservations@")
    candidates = mailto_emails or visible_emails
    if not candidates:
        return None
    ranked = sorted(Counter(candidates).items(), key=lambda x: (0 if x[0].startswith(generic_prefixes) else 1, -x[1], len(x[0]), x[0]))
    return ranked[0][0]


def choose_best_phone(tel_phones: list[str], visible_phones: list[str]) -> str | None:
    candidates = tel_phones or visible_phones
    if not candidates:
        return None
    ranked = sorted(Counter(candidates).items(), key=lambda x: (-x[1], -len(re.sub(r'\D', '', x[0])), x[0]))
    return ranked[0][0]


def choose_social_buckets(socials: list[str]) -> tuple[str | None, str | None, str | None]:
    cleaned = []
    for url in socials:
        u = url.replace("\\/", "/")
        u = u.split("?", 1)[0].rstrip("/").rstrip("\\")
        if u.startswith("http://"):
            u = "https://" + u[len("http://"):]
        parsed = urllib.parse.urlsplit(u)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        path = parsed.path.lower()
        if host not in {"instagram.com", "facebook.com", "linkedin.com", "x.com", "twitter.com", "tiktok.com", "youtube.com"}:
            continue
        if any(bad in path for bad in ["/sharer", "/dialog/", "/intent/tweet", "/reel/", "/p/", "/tv/", "/in/", "/profile.php", "/people/", "/tr", "/watch", "/2008/fbml"]):
            continue
        if host == "linkedin.com" and not path.startswith("/company/"):
            continue
        if host == "youtube.com" and not (path.startswith("/@") or path.startswith("/channel/") or path.startswith("/c/") or path.startswith("/user/")):
            continue
        cleaned.append((host, u))
    if not cleaned:
        return None, None, None
    unique = []
    seen = set()
    for host, url in cleaned:
        if url not in seen:
            seen.add(url)
            unique.append((host, url))
    instagram = next((url for host, url in unique if host == "instagram.com"), None)
    facebook = next((url for host, url in unique if host == "facebook.com"), None)
    other_urls = [url for host, url in unique if host not in {"instagram.com", "facebook.com"}]
    other = "; ".join(other_urls[:4]) if other_urls else None
    return instagram, facebook, other


def build_patch(row: dict, found: dict) -> dict | None:
    record_id = row["id"]
    existing_fields = row.get("fields", {})
    fields = {}
    for key in ["Email", "Phone Number", "Instagram", "Facebook", "Other"]:
        value = found.get(key)
        existing_value = existing_fields.get(key)
        if value and not existing_value:
            fields[key] = value
    if not fields:
        return None
    return {"id": record_id, "fields": fields}


def main() -> None:
    load_env()
    dry_run = "--dry-run" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 >= len(sys.argv):
            raise SystemExit("--limit requires an integer value")
        limit = int(sys.argv[idx + 1])
    rows = fetch_rows()
    if limit is not None:
        rows = rows[:limit]
    results = []
    patches = []

    for row in rows:
        fields = row.get("fields", {})
        club = fields.get("Club Name") or ""
        if is_hidden_or_intermediary(club):
            results.append({
                "id": row["id"],
                "club": club,
                "status": "skipped_hidden_or_intermediary",
            })
            continue
        seed, reason = pick_official_seed(row)
        if not seed:
            results.append({
                "id": row["id"],
                "club": club,
                "status": "no_official_seed",
                "seed_reason": reason,
            })
            continue
        try:
            found = extract_contacts(seed)
        except Exception as e:
            results.append({
                "id": row["id"],
                "club": club,
                "status": "extract_error",
                "seed": seed,
                "error": str(e),
            })
            continue
        patch = build_patch(row, found)
        status = "patched_candidate" if patch else "no_contacts_found"
        results.append({
            "id": row["id"],
            "club": club,
            "status": status,
            "seed": seed,
            "seed_reason": reason,
            "email": found.get("Email"),
            "phone": found.get("Phone Number"),
            "instagram": found.get("Instagram"),
            "facebook": found.get("Facebook"),
            "other": found.get("Other"),
            "pages": found.get("fetched_pages"),
        })
        if patch:
            patches.append(patch)
        time.sleep(0.4)

    update_batches = []
    if not dry_run:
        for i in range(0, len(patches), 10):
            batch = patches[i:i+10]
            if not batch:
                continue
            update_batches.append(api_patch(batch))
            time.sleep(0.3)

    summary = {
        "dry_run": dry_run,
        "rows_seen": len(rows),
        "patch_candidates": len(patches),
        "updated_batches": len(update_batches),
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
