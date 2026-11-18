/* Configurazione editoriale: modificare qui fonti, temi e filiali. */
const CONFIG = {
  cacheMinutes: 30,
  maxArticlesPerTheme: 5,
  newsProxy: "https://api.rss2json.com/v1/api.json?rss_url=",
  currencies: ["GBP", "USD", "AUD", "PLN", "SEK", "NOK"],
  currencyNames: { GBP: "Regno Unito", USD: "USA", AUD: "Australia", PLN: "Polonia", SEK: "Nordici", NOK: "Nordici" },
  sources: {
    bce: { name: "BCE", priority: 5, query: "site:ecb.europa.eu" },
    eurostat: { name: "Eurostat", priority: 5, query: "site:ec.europa.eu/eurostat" },
    reuters: { name: "Reuters", priority: 4, query: "site:reuters.com" },
    ft: { name: "Financial Times", priority: 4, query: "site:ft.com" },
    official: { name: "Fonti ufficiali", priority: 5, query: "" },
    google: { name: "Google News", priority: 1, query: "" }
  },
  themes: [
    { id: "vertici_societari", title: "Vertici societari", when: "7d", feeds: [] },
    { id: "industria_italiana", title: "Industria italiana", when: "3d", feeds: [] },
    { id: "brand_italiani", title: "Brand italiani", when: "3d", feeds: [] },
    { id: "food_fmcg", title: "Food e FMCG", when: "3d", feeds: [] },
    { id: "retail_consumatori", title: "Retail e consumatori", when: "3d", feeds: [] },
    { id: "materie_prime", title: "Materie prime", when: "3d", feeds: [] },
    { id: "energia_logistica", title: "Energia e logistica", when: "3d", feeds: [] },
    { id: "macro_economia", title: "Macro e geopolitica", when: "2d", feeds: [] },
    { id: "regolamentazione", title: "Regolamentazione", when: "7d", feeds: [] },
    { id: "m_and_a", title: "M&A e private equity", when: "7d", feeds: [] },
    { id: "mercati_internazionali", title: "Mercati internazionali", when: "3d", feeds: [] }
  ],
  branches: [
    { name: "Regno Unito", currencies: ["GBP"], query: "UK economy OR inflation OR Bank of England OR grocery Tesco OR Sainsbury's" },
    { name: "Germania", currencies: [], query: "Germany economy OR inflation OR Bundesbank OR Ifo OR budget" },
    { name: "Francia e Benelux", currencies: [], query: "France OR Netherlands OR Belgium economy OR inflation OR budget OR strike" },
    { name: "Polonia", currencies: ["PLN"], query: "Poland economy OR inflation OR zloty OR NBP" },
    { name: "Paesi nordici", currencies: ["SEK", "NOK"], query: "Sweden OR Norway OR Denmark OR Finland economy OR Riksbank OR Norges Bank OR inflation" },
    { name: "USA", currencies: ["USD"], query: "US economy OR Fed OR inflation OR tariffs OR consumer spending grocery" },
    { name: "Australia", currencies: ["AUD"], query: "Australia economy OR RBA OR inflation OR Woolworths OR Coles" }
  ],
  sports: [
    { title: "Canoa slalom", query: "canoa slalom" },
    { title: "Tennis", query: "ATP Slam OR Masters 1000 OR Sinner OR Cobolli" },
    { title: "WRC", query: "WRC rally mondiale" },
    { title: "Formula 1", query: "Formula 1 F1 mondiale" },
    { title: "MotoGP", query: "MotoGP mondiale" }
  ],
  questions: [
    "Quali costi stanno uscendo dal budget e perché?",
    "Dove vedi pressione sui prezzi o sulla marca del distributore?",
    "Qual è oggi il rischio principale sul forecast del trimestre?",
    "Cosa ti serve da me o dal gruppo questo mese?",
    "Quali segnali anticipano il primo trimestre del prossimo anno?",
    "Che cosa dicono i clienti della distribuzione su promozioni e listini?",
    "Quale decisione stai rimandando e cosa ti serve per prenderla?",
    "Cosa ha funzionato meglio del previsto negli ultimi due mesi?"
  ]
};
