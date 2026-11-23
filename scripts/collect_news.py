"""Raccoglie news economiche e societarie da Google News RSS.

Le liste editoriali vivono in data/brands.json, data/companies.json e
data/sources.json. Lo script genera query mirate, senza includere lo sport.
Le news vengono filtrate e ordinate prima del salvataggio, così da non
inquinare la sezione NEWS con articoli generici o poco utili.
"""

import datetime as dt
import email.utils
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
MAX_NEWS_AGE_DAYS = 14


def read_json(filename):
    with (DATA / filename).open(encoding="utf-8") as file:
        return json.load(file)


BRANDS = read_json("brands.json")["brands"]
COMPANIES = read_json("companies.json")["companies"]
SOURCES = read_json("sources.json")["sources"]
SOURCE_BY_DOMAIN = {item["domain"]: item for item in SOURCES}

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
    "food_fmcg": {
        "when": "3d",
        "base_queries": [
            '(food OR alimentare OR FMCG) (results OR earnings OR prices OR volumes OR margin OR outlook)',
            '(food OR beverage OR FMCG) (investment OR acquisition OR restructuring OR capacity)',
            '(food industry OR industria alimentare) (demand OR inflation OR private label OR brand)',
        ],
        "source_types": ["stampa_food", "stampa_verticale", "stampa_economica"],
    },
    "retail_consumatori": {
        "when": "3d",
        "base_queries": [
            '(grocery OR supermarket OR retailer) (food prices OR volumes OR sales OR private label)',
            '(retail OR consumi) (FMCG OR food OR grocery) (promotion OR pricing OR demand)',
            '(consumer spending OR consumer confidence) (food OR grocery OR household)',
        ],
        "source_types": ["stampa_retail", "ricerca_mercato", "stampa_economica"],
    },
    "materie_prime": {
        "when": "3d",
        "base_queries": [
            '(tomato OR pomodoro OR tomato paste OR concentrato) (prices OR crop OR supply OR harvest)',
            '(wheat OR sugar OR olive oil OR corn) (food prices OR crop OR supply OR harvest)',
            '(food commodities OR commodity) (prices OR outlook OR supply chain)',
        ],
        "source_types": ["istituzionale", "agenzia_stampa", "stampa_food"],
    },
    "energia_logistica": {
        "when": "3d",
        "base_queries": [
            '(gas OR electricity OR energy) (food industry OR manufacturing OR industrial prices)',
            '(freight OR shipping OR logistics) (food OR FMCG OR supply chain)',
            '(oil OR fuel OR transport costs) (food OR logistics OR Europe)',
        ],
        "source_types": ["istituzionale", "agenzia_stampa", "stampa_economica"],
    },
    "macro_economia": {
        "when": "2d",
        "base_queries": [
            '(Italy OR Eurozone OR Europe) (inflation OR interest rates OR consumer spending)',
            '(ECB OR Fed OR exchange rates OR currency) (outlook OR economy OR businesses)',
            '(tariffs OR trade restrictions OR geopolitics) (food OR consumer goods OR imports)',
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
    "aziende_competitor": {
        "when": "7d",
        "base_queries": [],
        "source_types": ["stampa_food", "stampa_verticale", "stampa_economica"],
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
                "market": "Globale",
            })

    # Intercetta solo aziende alimentari, beverage e FMCG realmente utili come
    # benchmark o concorrenti. Non vengono più usati gruppi generici di brand.
    priority_companies = [
        item["name"] for item in COMPANIES
        if item.get("priority", 0) >= 4
        and any(term in str(item.get("sector", "")).lower() for term in ("food", "fmcg", "beverage"))
    ][:24]

    company_domains = site_clause(source_domains(
        ["stampa_verticale", "M&A_specialist", "stampa_economica"], limit=6
    ))
    for name in priority_companies:
        queries.append({
            "category": "aziende_competitor",
            "query": f'"{name}" (food OR alimentare OR FMCG OR beverage) (results OR sales OR prices OR strategy OR acquisition OR investment){company_domains}',
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
        published_at = parse_pub_date(pub_date)
        if published_at is None or (dt.datetime.now(dt.timezone.utc) - published_at).total_seconds() > MAX_NEWS_AGE_DAYS * 86400:
            continue
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


def parse_pub_date(value):
    """Converte la data RSS in UTC; le date mancanti o non leggibili vengono escluse."""
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def deduplicate(items):
    unique = {}
    for item in items:
        normalized = re.sub(r"[^a-z0-9 ]", " ", item["title"].lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        tokens = set(normalized.split())
        if not tokens:
            continue

        duplicate = False
        for existing in unique.values():
            other = set(existing.get("_title_tokens", []))
            overlap = len(tokens & other) / max(1, min(len(tokens), len(other)))
            if overlap >= 0.78:
                duplicate = True
                break

        if not duplicate:
            item["_title_tokens"] = sorted(tokens)
            unique[normalized] = item

    result = list(unique.values())
    for item in result:
        item.pop("_title_tokens", None)
    return result


RELEVANCE_TERMS = {
    "vertici_societari": ["ceo", "cfo", "chief executive", "nomina", "dimissioni", "manager", "leadership"],
    "food_fmcg": ["food", "fmcg", "alimentare", "bevande", "consumer goods", "private label", "acquisizione", "risultati", "vendite", "margini"],
    "retail_consumatori": ["grocery", "supermarket", "retail", "retailer", "consumi", "spesa", "private label", "prezzi", "promozioni"],
    "materie_prime": ["pomodoro", "concentrato", "grano", "zucchero", "olio", "commodity", "raccolto", "siccità", "prezzi"],
    "energia_logistica": ["gas", "energia", "elettricità", "trasporto", "freight", "shipping", "logistica", "petrolio", "supply chain"],
    "macro_economia": ["inflazione", "tassi", "bce", "fed", "cambio", "dazi", "commercio", "pil", "economia"],
    "regolamentazione": ["regolamento", "norma", "packaging", "epr", "sostenibilità", "dazi", "dogana", "sicurezza alimentare"],
    "aziende_competitor": ["food", "alimentare", "fmcg", "beverage", "results", "sales", "prices", "strategy", "acquisition", "investment", "vendite", "prezzi"],
}

REQUIRED_SIGNALS = {
    "food_fmcg": ["food", "alimentare", "fmcg", "beverage", "consumer goods", "private label"],
    "retail_consumatori": ["grocery", "supermarket", "retail", "retailer", "private label", "food", "consumi", "spesa"],
    "materie_prime": ["tomato", "pomodoro", "tomato paste", "concentrato", "wheat", "grano", "sugar", "zucchero", "olive oil", "commodity"],
    "energia_logistica": ["gas", "electricity", "energy", "freight", "shipping", "logistics", "oil", "fuel", "supply chain"],
    "macro_economia": ["inflation", "inflazione", "interest rates", "tassi", "ecb", "fed", "exchange rates", "cambio", "tariffs", "dazi", "consumer spending"],
    "regolamentazione": ["food", "packaging", "epr", "sustainability", "sostenibilità", "dazi", "customs", "sicurezza alimentare"],
    "aziende_competitor": ["food", "alimentare", "fmcg", "beverage", "sales", "results", "prices", "strategy", "acquisition", "investment", "vendite", "prezzi"],
}

IRRELEVANT_TERMS = [
    "oroscopo", "lotteria", "cronaca nera", "calcio", "partita", "concerto",
    "ricetta", "come cucinare", "offerta di lavoro", "necrologio", "meteo",
]


def relevance_score(item):
    title = item.get("title", "").lower()
    category = item.get("category", "")
    if any(term in title for term in IRRELEVANT_TERMS):
        return 0

    signals = REQUIRED_SIGNALS.get(category, [])
    if signals and not any(term in title for term in signals):
        return 0

    score = 1
    score += sum(1 for term in RELEVANCE_TERMS.get(category, []) if term in title)
    if item.get("source_reliability"):
        score += min(2, int(item["source_reliability"]))
    if item.get("source_type") in {"istituzionale", "agenzia_stampa", "stampa_economica"}:
        score += 1
    return score


def filter_and_rank(items):
    ranked = []
    for item in items:
        score = relevance_score(item)
        if score < 3:
            continue
        item["relevance"] = "alta" if score >= 7 else "media"
        item["relevance_score"] = score
        ranked.append(item)

    ranked.sort(key=lambda item: (item.get("relevance_score", 0), item.get("pubDate", "")), reverse=True)
    return ranked[:180]


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

    unique = filter_and_rank(deduplicate(items))
    output_path = DATA / "news.json"
    if not unique:
        print("Nessuna news recente disponibile: salvo un archivio vuoto per non mostrare articoli vecchi", flush=True)

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
