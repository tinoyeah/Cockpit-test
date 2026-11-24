import datetime as dt
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


BRANCHES = {
    "UK": {
        "label": "UK",
        "keywords": ["UK", "United Kingdom", "Britain", "British", "England"],
    },
    "FRA&BNL": {
        "label": "France & Benelux",
        "keywords": [
            "France", "French", "Belgium", "Belgian", "Netherlands",
            "Dutch", "Luxembourg", "Benelux", "Paris", "Brussels",
        ],
    },
    "SCAND": {
        "label": "Scandinavia",
        "keywords": [
            "Scandinavia", "Scandinavian", "Nordics", "Nordic",
            "Sweden", "Swedish", "Denmark", "Danish", "Norway",
            "Norwegian", "Finland", "Finnish",
        ],
    },
    "DACH": {
        "label": "Germany, Austria & Switzerland",
        "keywords": ["Germany", "German", "Austria", "Austrian", "Switzerland", "Swiss"],
    },
    "USA&CAN": {
        "label": "USA & Canada",
        "keywords": ["USA", "United States", "American", "Canada", "Canadian"],
    },
    "OCEANIA": {
        "label": "Oceania",
        "keywords": ["Australia", "Australian", "New Zealand", "Oceania"],
    },
}

SEARCH_TERMS = [
    "company", "brand", "FMCG", "food", "retail", "grocery",
    "supermarket", "CEO", "CFO", "acquisition", "investment",
    "results", "distribution", "pricing", "consumer",
]


def fetch(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 CFO-Cockpit/1.0",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def google_news(query):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    })
    root = ET.fromstring(fetch(url))
    items = []
    for node in root.findall("./channel/item"):
        title = clean(node.findtext("title"))
        link = clean(node.findtext("link"))
        description = clean(node.findtext("description"))
        published = clean(node.findtext("pubDate"))
        if title and link:
            items.append({
                "title": title,
                "description": re.sub(r"<[^>]+>", " ", description).strip(),
                "link": link,
                "published_at": published,
            })
    return items


def main():
    output = {
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "branches": [],
    }

    for code, branch in BRANCHES.items():
        articles = []
        seen = set()
        geography = " OR ".join(f'"{word}"' for word in branch["keywords"])
        business = " OR ".join(f'"{word}"' for word in SEARCH_TERMS)
        query = f"({geography}) ({business}) when:7d"
        try:
            for article in google_news(query):
                if article["link"] in seen:
                    continue
                seen.add(article["link"])
                articles.append(article)
                if len(articles) >= 20:
                    break
        except Exception as exc:
            print(f"{code}: ricerca non disponibile: {exc}")

        output["branches"].append({
            "code": code,
            "name": branch["label"],
            "keywords": branch["keywords"],
            "items": articles,
        })
        print(f"{code}: {len(articles)} risultati")

    Path("data").mkdir(exist_ok=True)
    with open("data/branches.json", "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")


if __name__ == "__main__":
    main()
