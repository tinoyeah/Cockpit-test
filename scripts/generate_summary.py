import datetime as dt
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

MODEL = "gemini-3.8-flash"


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

    print(f"Modello Gemini utilizzato: {MODEL}")

    with open("data/news.json", encoding="utf-8") as file:
        news = json.load(file).get("items", [])[:50]

    with open("data/market.json", encoding="utf-8") as file:
        market = json.load(file)

    prompt = """Sei il responsabile Group Business Controlling di un gruppo FMCG alimentare.

Prepara un briefing manageriale in italiano usando esclusivamente i dati forniti.
Non inventare fatti, numeri, collegamenti causali o implicazioni.

Il briefing deve:
- spiegare cosa è successo;
- chiarire perché è importante;
- indicare il mercato o l’area interessata;
- includere il link originale quando disponibile;
- anticipare le sezioni News, Filiali, Sport, Prezzi e scenario macro;
- essere leggibile in circa 4-5 minuti.

Restituisci esclusivamente JSON valido con questa struttura:

{
  "headline": "headline generale della giornata",
  "intro": "3-5 frasi introduttive",
  "sections": [
    {
      "title": "Aziende, vertici e M&A",
      "items": [
        {
          "title": "titolo",
          "text": "cosa è successo e perché è importante",
          "market": "mercato o area",
          "link": "URL oppure stringa vuota"
        }
      ]
    }
  ],
  "watchlist": [
    "elemento da monitorare"
  ]
}

Le sezioni devono essere esattamente queste:

1. Aziende, vertici e M&A
2. Industria italiana e brand italiani
3. Food, FMCG e retail
4. Mercati e filiali internazionali
5. Materie prime, energia e logistica
6. Macro e regolamentazione
7. Sport

Puoi lasciare vuota una sezione se non ci sono informazioni rilevanti.
Non inserire frasi generiche per riempirla.
Limita ogni sezione a un massimo di 5 elementi.

DATI DI MERCATO:
""" + json.dumps(market, ensure_ascii=False) + """

NOTIZIE:
""" + json.dumps(news, ensure_ascii=False)

    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent?key={urllib.parse.quote(api_key)}"
    )

    body = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        print(f"Errore Gemini HTTP {error.code}:")
        print(details)
        raise

    except urllib.error.URLError as error:
        raise RuntimeError(f"Errore di connessione a Gemini: {error}") from error

    try:
        response_text = result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(f"Risposta Gemini inattesa: {json.dumps(result, ensure_ascii=False)}") from error

    output = clean_json(response_text)

    if not isinstance(output, dict):
        raise ValueError("Formato summary non valido")

    output["headline"] = str(
        output.get("headline") or "Briefing del giorno"
    )

    output["intro"] = str(output.get("intro") or "")

    watchlist = output.get("watchlist", [])
    if not isinstance(watchlist, list):
        watchlist = []

    expected_sections = [
        "Aziende, vertici e M&A",
        "Industria italiana e brand italiani",
        "Food, FMCG e retail",
        "Mercati e filiali internazionali",
        "Materie prime, energia e logistica",
        "Macro e regolamentazione",
        "Sport"
    ]

    raw_sections = output.get("sections", [])
    if not isinstance(raw_sections, list):
        raw_sections = []

    by_title = {
        str(section.get("title")): section
        for section in raw_sections
        if isinstance(section, dict)
    }

    sections = []

    for title in expected_sections:
        source = by_title.get(title, {})
        items = source.get("items", [])

        if not isinstance(items, list):
            items = []

        clean_items = []

        for item in items[:5]:
            if not isinstance(item, dict):
                continue

            clean_items.append({
                "title": str(item.get("title") or ""),
                "text": str(item.get("text") or ""),
                "market": str(item.get("market") or ""),
                "link": str(item.get("link") or "")
            })

        sections.append({
            "title": title,
            "items": clean_items
        })

    output = {
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "headline": output["headline"],
        "intro": output["intro"],
        "sections": sections,
        "watchlist": [str(item) for item in watchlist[:8]]
    }

    with open("data/summary.json", "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")


if __name__ == "__main__":
    generate()
