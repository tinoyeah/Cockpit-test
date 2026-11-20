"""Raccoglie news economiche e societarie da Google News RSS.

Le liste editoriali vivono in data/brands.json, data/companies.json e
data/sources.json. Lo script genera query mirate, senza includere lo sport.
Il ranking avanzato verrà applicato in un passaggio successivo.
"""

import datetime as dt
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MAX_ITEMS_PER_FEED = 12
REQUEST_TIMEOUT = 12
MAX_WORKERS = 8
MAX_DYNAMIC_QUERIES = 24


def read_json(filename):
    with (DATA / filename).open(encoding="utf-8") as file:
        return json.load(file)


BRANDS = read_json("brands.json")["brands"]
COMPANIES = read_json("companies.json")["companies"]
SOURCES = read_json("sources.json")["sources"]
SOURCE_BY_DOMAIN = {item["domain"]: item for item in SOURCES}

BRANCH_QUERIES = {
    "UK": ["UK food FMCG grocery market brands competitors Tesco Sainsbury's Aldi Lidl consumer spending prices inflation", "UK food market retailer strategy private label brand growth"],
    "GER": ["Germany food FMCG grocery market brands competitors Aldi Lidl Rewe Edeka consumer spending prices inflation", "Germany food market retailer strategy private label brand growth"],
    "FRA&BNL": ["France Benelux food FMCG grocery market brands competitors Carrefour Leclerc Delhaize consumer spending prices inflation", "France Belgium Netherlands food market retailer strategy private label brand growth"],
    "POL": ["Poland food FMCG grocery market brands competitors Biedronka Lidl consumer spending prices inflation", "Poland food market retailer strategy private label brand growth"],
    "SCAND": ["Nordic food FMCG grocery market brands competitors ICA Coop Salling consumer spending prices inflation", "Sweden Norway Denmark Finland food market retailer strategy private label brand growth"],
    "USA": ["US food FMCG grocery market brands competitors Walmart Costco Kroger private label consumer spending prices inflation", "US food market retailer strategy brand growth consumer trends"],
    "ANZ": ["Australia New Zealand food FMCG grocery market brands competitors Woolworths Coles Aldi consumer spending prices inflation", "Australia New Zealand food market retailer strategy private label brand growth"],
}


CATEGORIES = {
    "vertici_societari": {
        "when": "7d",
        "base_queries": [
            '"nuovo CEO" OR "nuovo CFO" OR "nuovo amministratore delegato"',
            '"CEO appointed" OR "new CFO" OR "executive appointment"',
            '"CEO resigns" OR "CFO resigns" OR "leadership change"',
        ],
        "source_types": ["stampa_verticale", "stampa_economica", "agenzia_stampa"],
    },
    "industria_italiana": {
        "when": "3d",
        "base_queries": [
            '"industria italiana" investimenti OR acquisizioni OR produzione',
            '"manifattura italiana" export OR crescita OR crisi',
            '"aziende italiane" riorganizzazione OR delocalizzazione OR investimento',
        ],
        "source_types": ["stampa_economica", "agenzia_stampa", "stampa_verticale"],
    },
    "brand_italiani": {
        "when": "3d",
        "base_queries": [
            '"brand italiani" acquisizione OR crescita OR risultati',
            '"marchi italiani" espansione OR acquisizione OR investimenti',
            '"Italian brands" growth OR acquisition OR strategy',
        ],
        "source_types": ["stampa_verticale", "stampa_economica", "M&A_specialist"],
    },
    "food_fmcg": {
        "when": "3d",
        "base_queries": [
            'food FMCG company results OR acquisition OR strategy',
            '"food industry" OR FMCG innovation investment',
            '"consumer goods" company outlook OR restructuring',
        ],
        "source_types": ["stampa_food", "stampa_verticale", "stampa_economica"],
    },
    "retail_consumatori": {
        "when": "3d",
        "base_queries": [
            'grocery retail private label consumer spending',
            'supermarket food prices retail strategy',
            'consumer behavior FMCG Europe USA UK',
        ],
        "source_types": ["stampa_retail", "ricerca_mercato", "stampa_economica"],
    },
    "materie_prime": {
        "when": "3d",
        "base_queries": [
            'tomato prices OR tomato paste market',
            'sugar wheat coffee cocoa olive oil prices',
            'food commodities crop outlook supply',
        ],
        "source_types": ["istituzionale", "agenzia_stampa", "stampa_food"],
    },
    "energia_logistica": {
        "when": "3d",
        "base_queries": [
            'European gas electricity prices industry',
            'freight rates shipping logistics food supply chain',
            'oil prices transport costs Europe',
        ],
        "source_types": ["istituzionale", "agenzia_stampa", "stampa_economica"],
    },
    "macro_economia": {
        "when": "2d",
        "base_queries": [
            'Italy Eurozone inflation interest rates consumer spending',
            'ECB economic outlook exchange rates tariffs',
            'geopolitics trade restrictions economic outlook',
        ],
        "source_types": ["istituzionale", "agenzia_stampa", "stampa_economica"],
    },
    "regolamentazione": {
        "when": "7d",
        "base_queries": [
            'EU food regulation packaging EPR sustainability',
            'food tariffs customs duties trade restrictions',
            'Italy food law consumer regulation',
        ],
        "source_types": ["istituzionale", "stampa_economica", "stampa_verticale"],
    },
    "m_and_a": {
        "when": "7d",
        "base_queries": [
            'Italy M&A acquisition sale stake private equity',
            'European consumer food M&A deal rumor',
            '"strategic review" OR "exploring a sale" company',
        ],
        "source_types": ["M&A_specialist", "stampa_verticale", "stampa_finanziaria"],
    },
    "mercati_internazionali": {
        "when": "3d",
        "base_queries": [
            'UK Germany France USA Australia grocery food economy',
            'international markets inflation retail consumer goods',
            'foreign exchange market outlook food companies',
        ],
        "source_types": ["agenzia_stampa", "stampa_economica", "stampa_retail"],
    },
}


def source_domains(source_types, limit=5):
    selected = []
    for source in SOURCES:
        if source.get("type") in source_types and source.get("priority", 0) >= 4:
            selected.append(source["domain"])
    return selected[:limit]


def site_clause(domains):
    if not domains:
        return ""
    return " (" + " OR ".join(f"site:{domain}" for domain in domains) + ")"


def chunks(values, size):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def build_queries():
    queries = []

    for category, config in CATEGORIES.items():
        domains = source_domains(config["source_types"])
        for base in config["base_queries"]:
            queries.append({
                "category": category,
                "query": base + site_clause(domains),
                "when": config["when"],
                "market": "Italia" if category in {"industria_italiana", "brand_italiani"} else "Globale",
            })

    branch_domains = site_clause(source_domains(["agenzia_stampa", "stampa_economica", "stampa_retail"], limit=6))
    for branch, branch_queries in BRANCH_QUERIES.items():
        for base in branch_queries:
            queries.append({
                "category": "filiali",
                "branch": branch,
                "query": base + branch_domains,
                "when": "3d",
                "market": branch,
            })

    # Intercetta nomine, risultati e deal delle società con priorità alta.
    priority_companies = [item["name"] for item in COMPANIES if item.get("priority", 0) >= 4]
    priority_brands = [item["name"] for item in BRANDS if item.get("priority", 0) >= 4]

    company_domains = site_clause(source_domains(
        ["stampa_verticale", "M&A_specialist", "stampa_economica"], limit=6
    ))
    for group in chunks(priority_companies, 8):
        names = " OR ".join(f'"{name}"' for name in group)
        queries.append({
            "category": "vertici_societari",
            "query": f"({names}) (CEO OR CFO OR nomina OR manager OR leadership){company_domains}",
            "when": "14d",
            "market": "Globale",
        })
        if len(queries) >= MAX_DYNAMIC_QUERIES + sum(len(c["base_queries"]) for c in CATEGORIES.values()):
            break

    brand_domains = site_clause(source_domains(["stampa_verticale", "stampa_food", "stampa_retail"], limit=6))
    for group in chunks(priority_brands, 10):
        names = " OR ".join(f'"{name}"' for name in group)
        queries.append({
            "category": "brand_italiani" if any(item["name"] in group and item.get("country") == "Italia" for item in BRANDS) else "food_fmcg",
            "query": f"({names}) (results OR strategy OR acquisition OR investment){brand_domains}",
            "when": "14d",
            "market": "Globale",
        })
        if len(queries) >= MAX_DYNAMIC_QUERIES + sum(len(c["base_queries"]) for c in CATEGORIES.values()):
            break

    return queries


def source_metadata(source_element):
    source_name = source_element.text.strip() if source_element is not None and source_element.text else ""
    source_url = source_element.get("url", "") if source_element is not None else ""
    domain = urlparse(source_url).netloc.replace("www.", "")
    known = SOURCE_BY_DOMAIN.get(domain, {})
    return {
        "source": source_name,
        "source_domain": domain,
        "source_type": known.get("type", "google_news"),
        "source_reliability": known.get("reliability"),
        "source_anticipation": known.get("anticipation"),
    }


def get_feed(query_info):
    query = f'{query_info["query"]} when:{query_info["when"]}'
    rss = "https://news.google.com/rss/search?q=" + urllib.parse.quote(query) + "&hl=it&gl=IT&ceid=IT:it"
    request = urllib.request.Request(rss, headers={"User-Agent": "Mozilla/5.0 CFO-Cockpit/3.0"})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        root = ET.fromstring(response.read())

    result = []
    for item in root.findall("./channel/item")[:MAX_ITEMS_PER_FEED]:
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        pub_date = item.findtext("pubDate", "").strip()
        source_info = source_metadata(item.find("source"))
        if title and link:
            result.append({
                "title": title,
                "link": link,
                "pubDate": pub_date,
                "category": query_info["category"],
                "market": query_info["market"],
                "branch": query_info.get("branch", ""),
                **source_info,
            })
    return result


def deduplicate(items):
    unique = {}
    for item in items:
        key = re.sub(r"[^a-z0-9]", "", item["title"].lower())[:160]
        unique.setdefault(key, item)
    return list(unique.values())


def main():
    items = []
    queries = build_queries()
    print(f"Eseguo {len(queries)} query editoriali", flush=True)

    # Le fonti vengono interrogate in parallelo: una fonte lenta non blocca
    # l'intero aggiornamento quotidiano.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        jobs = {executor.submit(get_feed, query_info): query_info for query_info in queries}
        for job in as_completed(jobs):
            query_info = jobs[job]
            try:
                items.extend(job.result())
            except Exception as exc:
                print(f"Feed non disponibile ({query_info['category']}): {exc}", flush=True)

    unique = deduplicate(items)
    output_path = DATA / "news.json"
    if not unique:
        try:
            with output_path.open(encoding="utf-8") as file:
                json.load(file)
            print("Nessun feed disponibile: mantengo le news precedenti", flush=True)
            return
        except Exception:
            pass

    output = {
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "items": unique,
    }
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"Salvate {len(unique)} news", flush=True)


if __name__ == "__main__":
    main()
