# CFO Cockpit

Mini-app statica per briefing quotidiano, cambi, prezzi, news, filiali, sport e radar.

## Struttura

- `index.html` e `v4.html`: pagine dell’app;
- `app.js`: logica dell’interfaccia;
- `config.js`: temi, query, filiali e sport;
- `styles.css`: grafica;
- `quotes.json`: database della frase del giorno;
- `data/news.json`: news raccolte automaticamente;
- `data/market.json`: cambi e prezzi raccolti automaticamente;
- `data/summary.json`: sintesi AI opzionale;
- `scripts/collect_news.py`: raccolta news;
- `scripts/collect_market.py`: raccolta prezzi;
- `scripts/generate_summary.py`: generazione sintesi con Gemini;
- `.github/workflows/update-data.yml`: aggiornamento automatico giornaliero.

## Pubblicazione

Caricare il contenuto di questa cartella nella root della repository GitHub, inclusa la cartella nascosta `.github`.

In **Settings → Pages** selezionare il branch principale e la cartella `/root`.

## Aggiornamento dati

Il workflow raccoglie ogni giorno news, prezzi e cambi. Se è configurato il secret `GEMINI_API_KEY`, aggiorna anche la sintesi AI. Senza Gemini, news e prezzi vengono aggiornati comunque.

Per avviare manualmente il processo:

`Actions → Aggiorna dati cockpit → Run workflow`

La chiave Gemini, se utilizzata, deve essere salvata in:

`Settings → Secrets and variables → Actions`

con nome `GEMINI_API_KEY`. Non inserire mai chiavi API nei file pubblici.
