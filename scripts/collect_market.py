import datetime as dt
import json
import urllib.parse
import urllib.request

YAHOO = [
    ("Zucchero", "SB=F", "USD/lb"),
    ("Caffè", "KC=F", "USD/lb"),
    ("Cacao", "CC=F", "USD/t"),
    ("Grano", "ZW=F", "USD/bu"),
    ("Rame", "HG=F", "USD/lb"),
    ("Alluminio", "ALI=F", "USD/t"),
]


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 CFO-Cockpit/2.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def collect():
    items = []
    try:
        values = get_json("https://energyindex.it/api/v1/today").get("values", {})
        for key, name, unit in [("PUN", "PUN", "€/MWh"), ("TTF", "Gas TTF", "€/MWh"), ("Brent", "Brent", "USD/bbl"), ("PSV", "Gas PSV", "€/MWh"), ("CO2", "CO₂", "€/tCO₂")]:
            value = values.get(key)
            if value:
                items.append({"name": name, "value": round(float(value.get("value_native", value.get("value"))), 2), "unit": value.get("unit_native", unit), "date": value.get("date", ""), "source": value.get("source", "Energy Index")})
    except Exception as exc:
        print(f"Energy Index non disponibile: {exc}")

    for name, symbol, unit in YAHOO:
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(symbol) + "?range=5d&interval=1d"
            chart = get_json(url)["chart"]["result"][0]
            meta = chart["meta"]
            value = meta.get("regularMarketPrice")
            if value is not None:
                date = dt.datetime.fromtimestamp(meta["regularMarketTime"], dt.timezone.utc).date().isoformat() if meta.get("regularMarketTime") else ""
                items.append({"name": name, "value": round(float(value), 2), "unit": unit, "date": date, "source": "Yahoo Finance"})
        except Exception as exc:
            print(f"{name} non disponibile: {exc}")

    items.append({"name": "Pomodoro industriale", "value": None, "unit": "", "date": "", "source": "Quotazione pubblica giornaliera non disponibile"})
    return items


def main():
    items = collect()
    if not items:
        print("Nessun prezzo disponibile: mantengo il file precedente")
        return
    output = {"updated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "items": items}
    with open("data/market.json", "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"Salvati {len(items)} prezzi")


if __name__ == "__main__":
    main()
