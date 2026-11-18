import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request

MODEL = "gemini-2.5-flash"


def clean_json(text):
    text = re.sub(r"^```json\s*|\s*```$", "", text.strip(), flags=re.I)
    return json.loads(text)


def generate():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY non configurata")

    with open("data/news.json", encoding="utf-8") as file:
        news = json.load(file).get("items", [])[:30]
    with open("data/market.json", encoding="utf-8") as file:
        market = json.load(file)

    prompt = """Sei il responsabile Group Business Controlling di un gruppo FMCG alimentare.
Prepara un briefing manageriale in italiano usando esclusivamente i dati forniti.
Non inventare fatti, numeri o implicazioni. Dai priorità a costi, margini, prezzi,
domanda, supply chain, cambi e rischi. Sii concreto e leggibile in meno di due minuti.
Restituisci esclusivamente JSON valido:
{"summary":"testo breve","key_points":["..."],"risks":["..."],"opportunities":["..."],"sport":"..."}

DATI DI MERCATO:
""" + json.dumps(market, ensure_ascii=False) + "\n\nNOTIZIE:\n" + json.dumps(news, ensure_ascii=False)

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={urllib.parse.quote(api_key)}"
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
    request = urllib.request.Request(endpoint, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.loads(response.read())

    output = clean_json(result["candidates"][0]["content"]["parts"][0]["text"])
    output.update({"date": dt.datetime.now(dt.timezone.utc).date().isoformat(), "cfo": []})
    with open("data/summary.json", "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")


if __name__ == "__main__":
    generate()
