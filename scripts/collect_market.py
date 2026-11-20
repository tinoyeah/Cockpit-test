import datetime as dt
import json
import urllib.parse
import urllib.request

YAHOO = [("Zucchero", "SB=F", "USD/lb"), ("Caffè", "KC=F", "USD/lb"), ("Cacao", "CC=F", "USD/t"), ("Grano", "ZW=F", "USD/bu"), ("Rame", "HG=F", "USD/lb"), ("Alluminio", "ALI=F", "USD/t")]
TODAY = dt.datetime.now(dt.timezone.utc).date()


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 CFO-Cockpit/3.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def empty_energy(name, unit, source):
    return {"name": name, "value": None, "unit": unit, "date": "", "source": source, "ytd_start": None, "ytd_start_date": None, "week52_start": None, "week52_start_date": None}


def energy_items():
    # Nessun fallback a futures, forecast o proxy. Se manca una serie coerente,
    # il valore resta n/d invece di mescolare fonti o strumenti diversi.
    items = [
        empty_energy("PUN Index GME", "€/MWh", "GME via Energy Index"),
        empty_energy("IG Index GME", "€/MWh", "GME"),
        empty_energy("TTF spot day-ahead", "€/MWh", "EEX"),
        empty_energy("Ultima asta EUA", "€/tCO₂", "EEX Primary Market Auction"),
    ]
    try:
        data = get_json("https://energyindex.it/api/v1/pun/today")
        value = data.get("value_native", data.get("value"))
        if value is not None:
            items[0].update({"value": round(float(value), 2), "date": str(data.get("date") or "")})
    except Exception as exc:
        print(f"PUN Index GME non disponibile: {exc}")
    return items


def reference_values(timestamps, closes):
    points = sorted((dt.datetime.fromtimestamp(t, dt.timezone.utc).date(), float(v)) for t, v in zip(timestamps or [], closes or []) if v is not None)

    def first_on_or_after(target):
        for date, value in points:
            if date >= target:
                return value, date.isoformat()
        return None, None

    return first_on_or_after(dt.date(TODAY.year, 1, 1)), first_on_or_after(TODAY - dt.timedelta(days=364))


def yahoo_items():
    items = []
    for name, symbol, unit in YAHOO:
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(symbol) + "?range=2y&interval=1d"
            chart = get_json(url)["chart"]["result"][0]
            timestamps = chart.get("timestamp", [])
            closes = chart.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            (ytd, ytd_date), (w52, w52_date) = reference_values(timestamps, closes)
            meta = chart["meta"]
            value = meta.get("regularMarketPrice")
            if value is None:
                continue
            regular_time = meta.get("regularMarketTime")
            date = dt.datetime.fromtimestamp(regular_time, dt.timezone.utc).date().isoformat() if regular_time else ""
            items.append({"name": name, "value": round(float(value), 2), "unit": unit, "date": date, "source": "Yahoo Finance", "ytd_start": round(ytd, 2) if ytd is not None else None, "ytd_start_date": ytd_date, "week52_start": round(w52, 2) if w52 is not None else None, "week52_start_date": w52_date})
        except Exception as exc:
            print(f"{name} non disponibile: {exc}")
    return items


def main():
    items = energy_items() + yahoo_items() + [empty_energy("Pomodoro industriale", "", "Quotazione pubblica giornaliera non disponibile")]
    output = {"updated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "items": items}
    with open("data/market.json", "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"Salvati {len(items)} prezzi")


if __name__ == "__main__":
    main()

