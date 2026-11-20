import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

MODELS = ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-2.5-flash-lite"]


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

    prompt = """Sei il responsabile Group Business Controlling di un gruppo FMCG internazionale.

Leggi e interpreta tutti i dati presenti nei file forniti:
- news;
- mercati internazionali e filiali;
- food, FMCG e retail;
- industria e brand italiani;
- aziende, vertici e M&A;
- materie prime, energia e logistica;
- scenario macroeconomico e regolamentazione;
- sport;
- prezzi e cambi.

Prepara una lettura manageriale complessiva della giornata, con particolare attenzione ai mercati internazionali rilevanti per un gruppo FMCG.

Non creare sezioni, capitoli, elenchi puntati, liste di notizie o blocchi separati. Devi scrivere un unico discorso fluido e continuo, come se stessi facendo un briefing orale a un CFO o a un CEO.

Il testo deve:
- riassumere tutto ciò che è rilevante nei dati;
- trovare un filo rosso che colleghi gli eventi;
- spiegare le dinamiche in corso;
- mettere in relazione mercati, aziende, consumatori, costi, supply chain e scenario macro;
- indicare perché ciò che sta accadendo è importante;
- esprimere un punto di vista manageriale;
- evidenziare le implicazioni più probabili per aziende e mercati;
- dedicare spazio concreto ai mercati e alle filiali: domanda, crescita, inflazione, prezzi, promozioni, canali, retailer, private label, trade-down/trade-up e rischi locali, solo quando supportati dai dati;
- identificare brand, aziende e concorrenti citati nelle notizie e spiegare cosa stanno facendo, quali posizionamenti stanno difendendo e perché questo può essere rilevante competitivamente;
- distinguere tra segnali di mercato strutturali e semplici notizie episodiche;
- indicare, all’interno del discorso, ciò che merita maggiore attenzione.

Non limitarti a ripetere le singole notizie che l’utente troverà nelle altre pagine. Devi spiegare che cosa significano nel loro insieme e quali conseguenze possono avere su vendite, margini, quota, mix, investimenti e rischio competitivo.

Quando i dati lo consentono, collega esplicitamente: mercato -> comportamento del consumatore -> brand/competitor -> implicazione per un gruppo FMCG. Non inventare quote, dimensioni o causalità non presenti nei dati.

Usa esclusivamente le informazioni presenti nei dati. Non inventare fatti, numeri, eventi o relazioni causali. Distingui implicitamente tra fatti e interpretazioni. Quando i dati non consentono una conclusione, usa formule prudenti come “potrebbe indicare”, “sembra emergere” o “sarà importante monitorare”.

Il testo deve essere discorsivo, autorevole, naturale e leggibile in circa 4-5 minuti. Non usare titoletti interni, numerazioni o bullet point.

Restituisci esclusivamente JSON valido con questa struttura:

{
  "headline": "una frase breve che sintetizza la dinamica centrale della giornata",
  "intro": "un unico discorso completo e continuo di circa 4-5 minuti",
  "sections": [],
  "watchlist": []
}

Tutto il contenuto del briefing deve stare dentro il campo "intro".

Aggiungi solo in calce il campo "watchlist" con la lista delle cose da monitorare nel prossimo futuro.

""" + json.dumps(market, ensure_ascii=False) + "\n\nNOTIZIE:\n" + json.dumps(news, ensure_ascii=False)

    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
    result = None
    last_error = None

    for model in MODELS:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={urllib.parse.quote(api_key)}"
        request = urllib.request.Request(endpoint, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
        for attempt in range(3):
            print(f"Tentativo Gemini: modello={model}, tentativo={attempt + 1}/3")
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    result = json.loads(response.read())
                print(f"Gemini disponibile con modello: {model}")
                break
            except urllib.error.HTTPError as error:
                details = error.read().decode("utf-8", errors="replace")
                last_error = error
                print(f"Gemini HTTP {error.code} con {model}: {details}")
                if error.code in (404, 400):
                    break
                if error.code not in (429, 500, 502, 503, 504):
                    raise
                if attempt < 2:
                    time.sleep(10 * (attempt + 1))
        if result is not None:
            break

    if result is None:
        raise RuntimeError(f"Nessun modello Gemini disponibile dopo i tentativi: {last_error}")

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
