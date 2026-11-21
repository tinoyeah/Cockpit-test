import csv
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

YAHOO = [("Zucchero", "SB=F", "USD/lb"), ("Caffè", "KC=F", "USD/lb"), ("Cacao", "CC=F", "USD/t"), ("Grano", "ZW=F", "USD/bu"), ("Rame", "HG=F", "USD/lb"), ("Alluminio", "ALI=F", "USD/t")]
TODAY = dt.datetime.now(dt.timezone.utc).date()
TTF_HISTORY = Path("data/ttf_history.csv")
TTF_URL = "https://www.ice.com/products/27996665/Dutch-TTF-Natural-Gas-Futures/data?marketId=62773908&span=2"

def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 CFO-Cockpit/4.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())

def get_text(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")

def empty_item(name, unit, source):
    return {"name": name, "value": None, "unit": unit, "date": "", "source": source, "ytd_start": None, "ytd_start_date": None, "week52_start": None, "week52_start_date": None}

def number(value):
    text = str(value).strip().replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(",", "")
    else:
        text = text.replace(",", ".")
    return float(text)

def read_ttf_history():
    if not TTF_HISTORY.exists():
        raise FileNotFoundError(f"File storico TTF non trovato: {TTF_HISTORY}")
    points = []
    with TTF_HISTORY.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file, delimiter=";"):
            try:
                date = dt.datetime.strptime((row.get("Data") or "").strip(), "%d/%m/%Y").date()
                points.append((date, number(row.get("Ultimo"))))
            except (ValueError, TypeError):
                print(f"Riga TTF ignorata: {row}")
    return sorted(set(points))

def append_ttf_row(points, date, value):
    if date in {point_date for point_date, _ in points}:
        return points, False
    with TTF_HISTORY.open("a", encoding="utf-8", newline="") as file:
        csv.writer(file, delimiter=";", lineterminator="\n").writerow([date.strftime("%d/%m/%Y"), f"{value:.3f}".replace(".", ",")])
    return sorted(points + [(date, value)]), True

def fetch_ttf_latest():
    html = get_text(TTF_URL)
    pattern = r"(?:Dec|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov)\d{2}[^0-9]{1,150}(\d{1,4}[.,]\d{1,4})[^0-9]{1,150}(\d{1,2})/(\d{1,2})/(\d{4})"
    match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("Nessun prezzo front-month riconoscibile nella pagina ICE")
    value = number(match.group(1))
    date = dt.date(int(match.group(4)), int(match.group(3)), int(match.group(2)))
    if value <= 0 or date > TODAY:
        raise ValueError("Dato ICE non valido")
    return date, value

def reference_values(points):
    def first_on_or_after(target):
        for date, value in points:
            if date >= target:
                return value, date.isoformat()
        return None, None
    return first_on_or_after(dt.date(TODAY.year, 1, 1)), first_on_or_after(TODAY - dt.timedelta(days=364))

def ttf_item():
    points = read_ttf_history()
    if not points:
        raise ValueError("Lo storico TTF è vuoto")
    try:
        latest_date, latest_value = fetch_ttf_latest()
        if latest_date <= TODAY:
            points, added = append_ttf_row(points, latest_date, latest_value)
            print(f"TTF: {'aggiunto' if added else 'già presente'} {latest_date} = {latest_value}")
    except Exception as exc:
        print(f"Aggiornamento ICE TTF non riuscito; uso il CSV: {exc}")
    current_date, current_value = points[-1]
    (ytd, ytd_date), (week, week_date) = reference_values(points)
    return {"name": "Dutch TTF Future", "value": round(current_value, 3), "unit": "€/MWh", "date": current_date.isoformat(), "source": "ICE Endex Dutch TTF Natural Gas Futures", "ytd_start": round(ytd, 3) if ytd is not None else None, "ytd_start_date": ytd_date, "week52_start": round(week, 3) if week is not None else None, "week52_start_date": week_date}

def energy_api_item(name, unit, endpoint, source):
    item = empty_item(name, unit, source)
    try:
        data = get_json(endpoint)
        value = data.get("value_native", data.get("value"))
        if value is not None:
            item.update({"value": round(float(value), 2), "date": str(data.get("date") or "")})
    except Exception as exc:
        print(f"{name} non disponibile: {exc}")
    return item

def energy_items():
    items = [energy_api_item("PUN Index GME", "€/MWh", "https://energyindex.it/api/v1/pun/today", "GME via Energy Index")]
    try:
        items.append(ttf_item())
    except Exception as exc:
        print(f"Dutch TTF Future non disponibile: {exc}")
        items.append(empty_item("Dutch TTF Future", "€/MWh", "ICE Endex Dutch TTF Natural Gas Futures"))
    return items

def yahoo_items():
    items = []
    for name, symbol, unit in YAHOO:
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(symbol) + "?range=2y&interval=1d"
            chart = get_json(url)["chart"]["result"][0]
            timestamps = chart.get("timestamp", [])
            closes = chart.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            points = sorted((dt.datetime.fromtimestamp(t, dt.timezone.utc).date(), float(v)) for t, v in zip(timestamps, closes) if v is not None)
            (ytd, ytd_date), (week, week_date) = reference_values(points)
            meta = chart["meta"]
            value = meta.get("regularMarketPrice")
            if value is None:
                continue
            market_time = meta.get("regularMarketTime")
            date = dt.datetime.fromtimestamp(market_time, dt.timezone.utc).date().isoformat() if market_time else ""
            items.append({"name": name, "value": round(float(value), 2), "unit": unit, "date": date, "source": "Yahoo Finance", "ytd_start": round(ytd, 2) if ytd is not None else None, "ytd_start_date": ytd_date, "week52_start": round(week, 2) if week is not None else None, "week52_start_date": week_date})
        except Exception as exc:
            print(f"{name} non disponibile: {exc}")
    return items

def main():
    items = energy_items() + yahoo_items() + [empty_item("Pomodoro industriale", "", "Quotazione pubblica giornaliera non disponibile")]
    Path("data").mkdir(exist_ok=True)
    with open("data/market.json", "w", encoding="utf-8") as file:
        json.dump({"updated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "items": items}, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"Salvati {len(items)} prezzi")

if __name__ == "__main__":
    main()
