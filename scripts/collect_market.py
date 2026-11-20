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
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 CFO-Cockpit/2.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def reference_values(timestamps, closes):
    points = []
    for timestamp, close in zip(timestamps or [], closes or []):
        if close is None:
            continue
        points.append((dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).date(), float(close)))
    if not points:
        return None, None

    today = dt.datetime.now(dt.timezone.utc).date()
    year_start = dt.date(today.year, 1, 1)
    week52_start = today - dt.timedelta(days=364)

    def closest_on_or_after(target):
        future = [value for date, value in points if date >= target]
        if future:
            return future[0]
        return points[-1][1]

    return closest_on_or_after(year_start), closest_on_or_after(week52_start)


def collect():
    items = []

    try:
        values = get_json("https://energyindex.it/api/v1/today").get("values", {})
        for key, name, unit in [
            ("PUN", "PUN", "€/MWh"),
            ("TTF", "Gas TTF", "€/MWh"),
            ("Brent", "Brent", "USD/bbl"),
            ("PSV", "Gas PSV", "€/MWh"),
            ("CO2", "CO₂", "€/tCO₂"),
        ]:
            value = values.get(key)
            if value:
                items.append({
                    "name": name,
                    "value": round(float(value.get("value_native", value.get("value"))), 2),
                    "unit": value.get("unit_native", unit),
                    "date": value.get("date", ""),
                    "source": value.get("source", "Energy Index"),
                    "ytd_start": None,
                    "week52_start": None,
                })
    except Exception as exc:
        print(f"Energy Index non disponibile: {exc}")

    for name, symbol, unit in YAHOO:
        try:
            url = (
                "https://query1.finance.yahoo.com/v8/finance/chart/"
                + urllib.parse.quote(symbol)
                + "?range=2y&interval=1d"
            )
            chart = get_json(url)["chart"]["result"][0]
            meta = chart["meta"]
            timestamps = chart.get("timestamp", [])
            closes = chart.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            ytd_start, week52_start = reference_values(timestamps, closes)
            value = meta.get("regularMarketPrice")
            if value is not None:
                regular_time = meta.get("regularMarketTime")
                date = (
                    dt.datetime.fromtimestamp(regular_time, dt.timezone.utc).date().isoformat()
                    if regular_time else ""
                )
                items.append({
                    "name": name,
                    "value": round(float(value), 2),
                    "unit": unit,
                    "date": date,
                    "source": "Yahoo Finance",
                    "ytd_start": round(ytd_start, 2) if ytd_start is not None else None,
                    "week52_start": round(week52_start, 2) if week52_start is not None else None,
                })
        except Exception as exc:
            print(f"{name} non disponibile: {exc}")

    items.append({
        "name": "Pomodoro industriale",
        "value": None,
        "unit": "",
        "date": "",
        "source": "Quotazione pubblica giornaliera non disponibile",
        "ytd_start": None,
        "week52_start": None,
    })
    return items


def main():
    items = collect()
    if not items:
        print("Nessun prezzo disponibile: mantengo il file precedente")
        return
    output = {
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "items": items,
    }
    with open("data/market.json", "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"Salvati {len(items)} prezzi")


if __name__ == "__main__":
    main()
