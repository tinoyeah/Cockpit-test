"""Raccoglie news recenti e pertinenti per le filiali internazionali."""

import datetime as dt
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "branches.json"
MAX_AGE_DAYS = 4
MAX_ITEMS_PER_QUERY = 10

BRANCHES = {
    "UK": [
        "UK food FMCG grocery retailer brands competitors Tesco Sainsbury's Aldi Lidl prices inflation",
        "UK grocery market consumer spending private label food brand strategy",
    ],
    "GER": [
        "Germany food FMCG grocery retailer brands competitors Aldi Lidl Rewe Edeka prices inflation",
        "Germany grocery market consumer spending private label food brand strategy",
    ],
    "FRA&BNL": [
        "France Benelux food FMCG grocery retailer brands competitors Carrefour Leclerc Delhaize prices inflation",
        "France Belgium Netherlands grocery market consumer spending private label food brand strategy",
    ],
    "POL": [
        "Poland food FMCG grocery retailer brands competitors Biedronka Lidl prices inflation",
        "Poland grocery market consumer spending private label food brand strategy",
    ],
    "SCAND": [
        "Nordic Sweden Norway Denmark Finland food FMCG grocery retailer brands competitors ICA Coop Salling prices inflation",
        "Nordic grocery market consumer spending private label food brand strategy",
    ],
    "USA": [
        "US food FMCG grocery retailer brands competitors Walmart Costco Kroger private label prices inflation",
        "US grocery market consumer spending food brand strategy retailer results",
    ],
    "ANZ": [
        "Australia New Zealand food FMCG grocery retailer brands competitors Woolworths Coles Aldi prices inflation",
        "Australia New Zealand grocery market consumer spending private label food brand strategy",
    ],
}


def parse_date(value):
    try:
        return dt.datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def clean_key(title):
    return re.sub(r"[^a-z0-9]", "", title.lower())[:180]


def get_feed(branch, query):
    full_query = f"{query} when:3d"
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(full_query) + "&hl=en&gl=GB&ceid=GB:en"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 CFO-Cockpit/3.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read())

    now = dt.datetime.now(dt.timezone.utc)
    result = []
    for item in root.findall("./channel/item")[:MAX_ITEMS_PER_QUERY]:
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        raw_date = item.findtext("pubDate", "").strip()
        published = parse_date(raw_date)
        if not title or not link or not published:
            continue
        age = now - published
        if age.total_seconds() < 0 or age.days > MAX_AGE_DAYS:
            continue
        source_node = item.find("source")
        source = source_node.text.strip() if source_node is not None and source_node.text else "Google News"
        result.append({
            "branch": branch,
            "title": title,
            "link": link,
            "pubDate": published.isoformat(),
            "topic": "Mercato, consumatori, retailer, brand e competitor",
            "source": source,
        })
    return result


def main():
    items = []
    jobs = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        for branch, queries in BRANCHES.items():
            for query in queries:
                jobs[executor.submit(get_feed, branch, query)] = branch
        for job in as_completed(jobs):
            try:
                items.extend(job.result())
            except Exception as error:
                print(f"Query filiale non disponibile ({jobs[job]}): {error}", flush=True)

    unique = {}
    for item in items:
        unique.setdefault((item["branch"], clean_key(item["title"])), item)
    ordered = sorted(unique.values(), key=lambda x: x["pubDate"], reverse=True)
    output = {"updated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "items": ordered}
    with OUTPUT.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"Salvate {len(ordered)} news filiali", flush=True)


if __name__ == "__main__":
    main()
