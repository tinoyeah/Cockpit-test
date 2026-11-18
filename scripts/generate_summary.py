import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def clean_json(text):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("La risposta del modello non contiene JSON valido")
    return json.loads(text[start:end + 1])


def generate():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY non configurata")

    with open("data/news.json", encoding="utf-8") as file:
        news = json.load(file).get("items", [])[:50]
    with open("data/market.json", encoding="utf-8") as file:
        market = json.load(file)

    prompt = """Sei il responsabile Group Business Controlling di un gruppo FMCG alimentare.
Prepara un briefing manageriale in italiano usando esclusivamente i dati forniti.
Non inventare fatti, numeri, collegamenti causali o implicazioni. Ogni elemento deve
riportare cosa è successo, perché è rilevante e quale mercato/area riguarda. Usa solo
informazioni contenute nei dati. Se un dato non è disponibile, non colmare il vuoto.
Il briefing deve anticipare le sezioni News, Filiali, Sport, Prezzi e scenario macro.
Deve essere concreto, leggibile in circa 4-5 minuti e non deve trasformarsi in un
elenco di titoli senza spiegazione. Inserisci il link originale quando disponibile.
Restituisci esclusivamente JSON valido, con questa struttura:
{"updated_at":"ISO 8601 UTC","headline":"headline generale della giornata","intro":"3-5 frasi introduttive","sections":[{"title":"Aziende, vertici e M&A","items":[{"title":"titolo","text":"cosa è successo e perché è importante","market":"mercato o area","link":"URL oppure stringa vuota"}]}],"watchlist":["elemento da monitorare"]}

Le sezioni devono essere esattamente queste, nello stesso ordine:
1. Aziende, vertici e M&A
2. Industria italiana e brand italiani
3. Food, FMCG e retail
4. Mercati e filiali internazionali
5. Materie prime, energia e logistica
6. Macro e regolamentazione
7. Sport
Puoi lasciare vuota una sezione se nei dati non c'è nulla di rilevante. Non scrivere
frasi generiche per riempirla. Dai priorità agli elementi più importanti e limita
ogni sezione a 2-5 elementi.

DATI DI MERCATO:
""" + json.dumps(market, ensure_ascii=False) + "\n\nNOTIZIE:\n" + json.dumps(news, ensure_ascii=False)

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={urllib.parse.quote(api_key)}"
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
    request = urllib.request.Request(endpoint, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.loads(response.read())

    output = clean_json(result["candidates"][0]["content"]["parts"][0]["text"])
    if not isinstance(output, dict):
        raise ValueError("Formato summary non valido")
    output["headline"] = str(output.get("headline") or "Briefing del giorno")
    output["intro"] = str(output.get("intro") or "")
    output["watchlist"] = output.get("watchlist", []) if isinstance(output.get("watchlist", []), list) else []
    expected = ["Aziende, vertici e M&A", "Industria italiana e brand italiani", "Food, FMCG e retail", "Mercati e filiali internazionali", "Materie prime, energia e logistica", "Macro e regolamentazione", "Sport"]
    raw_sections = output.get("sections", []) if isinstance(output.get("sections", []), list) else []
    by_title = {str(x.get("title")): x for x in raw_sections if isinstance(x, dict)}
    sections = []
    for title in expected:
        source = by_title.get(title, {})
        items = source.get("items", []) if isinstance(source.get("items", []), list) else []
        clean_items = []
        for item in items[:5]:
            if not isinstance(item, dict):
                continue
            clean_items.append({"title": str(item.get("title") or ""), "text": str(item.get("text") or ""), "market": str(item.get("market") or ""), "link": str(item.get("link") or "")})
        sections.append({"title": title, "items": clean_items})
    output["sections"] = sections
    output["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    output = {"updated_at": output["updated_at"], "headline": output["headline"], "intro": output["intro"], "sections": output["sections"], "watchlist": [str(x) for x in output["watchlist"][:8]]}
    with open("data/summary.json", "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")


if __name__ == "__main__":
    generate()
