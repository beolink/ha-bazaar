// The website around <bazaar-catalog>: language, counts and the links that
// point back to this project's own repository.

const SOURCE = "beolink/ha-bazaar";

const TEXT = {
  sv: {
    eyebrow: "Inofficiell katalog över HACS-färdiga repon för Home Assistant",
    nav_how: "Så fungerar det",
    nav_panel: "I Home Assistant",
    title: "Det som HACS kan installera men inte listar än",
    lead:
      "Integrationer, dashboardkort och teman för Home Assistant som är redo för HACS, de flesta i kö för granskning där. Varje kort visar hur repot klarar HACS egna kontroller och vad en första läsning av koden hittade.",
    notice:
      "Inget här är granskat av HACS. Det är andras kod som läggs till i din Home Assistant som ett anpassat repo. Titta på kontrollerna och flaggorna på varje kort, och på koden om du är osäker.",
    loading: "Laddar katalogen…",
    how_title: "Så fungerar det",
    how_1:
      "Varje natt läser katalogen de öppna pull requesterna till hacs/default och söker igenom GitHub efter varje hacs.json. Det som HACS redan listar, eller har tagit bort, lämnas utanför, liksom arkiverade repon och forkar.",
    how_2:
      "Varje repo prövas mot de kontroller HACS kör innan det listar något. För repon i kön visas också resultatet av HACS egen kontroll på pull requesten. En integration vars domän redan används av en i HACS eller i Home Assistant markeras, eftersom bara den ena kan installeras.",
    how_3:
      "Pythonkoden i varje integration läses som kod, inte som text, efter sådant som är värt en andra titt, som att köra text som kod eller starta program. En flagga är ett skäl att läsa, inte en dom.",
    how_4:
      "Öppna i HACS tar dig till din egen Home Assistant via My Home Assistant. HACS frågar om repot ska läggas till, och sedan installerar och uppdaterar HACS det som vilket annat som helst.",
    panel_title: "Bazaar i Home Assistant",
    panel_body:
      "Följeintegrationen lägger katalogen i Home Assistants sidomeny, visar vad HACS redan har och lägger till ett repo i HACS med ett klick. Installera den via HACS som vilket anpassat repo som helst.",
    panel_button: "Lägg till Bazaar i HACS",
    footer: "Inte knutet till HACS eller Home Assistant.",
    source: "Källkod och anmälningar",
  },
};

const stats = {
  en: (c, when) =>
    `${c.total.toLocaleString("en")} repositories, ${c.pending.toLocaleString("en")} of them in the HACS queue. Catalog built ${when}.`,
  sv: (c, when) =>
    `${c.total.toLocaleString("sv")} repon, varav ${c.pending.toLocaleString("sv")} i HACS-kön. Katalogen byggd ${when}.`,
};

const english = new Map();
let lang = "en";
let catalog = null;

function pickLanguage() {
  let stored = null;
  try {
    stored = localStorage.getItem("bazaar-lang");
  } catch {
    // Private windows and blocked storage: the browser's language decides.
  }
  if (stored === "sv" || stored === "en") return stored;
  return (navigator.languages || [navigator.language]).some((l) => String(l).toLowerCase().startsWith("sv"))
    ? "sv"
    : "en";
}

function applyLanguage() {
  document.documentElement.lang = lang;
  for (const el of document.querySelectorAll("[data-t]")) {
    if (!english.has(el)) english.set(el, el.textContent);
    const key = el.dataset.t;
    el.textContent = lang === "en" ? english.get(el) : TEXT[lang][key] ?? english.get(el);
  }
  const toggle = document.getElementById("lang");
  toggle.textContent = lang === "en" ? "SV" : "EN";
  toggle.setAttribute("aria-label", lang === "en" ? "Svenska" : "English");
  document.getElementById("catalog").lang = lang;
  showStats();
}

function showStats() {
  if (!catalog) return;
  const when = new Intl.DateTimeFormat(lang, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(catalog.generated),
  );
  document.getElementById("stats").textContent = stats[lang](catalog.counts, when);
}

function reportUrl(entry) {
  const params = new URLSearchParams({
    title: `Report: ${entry.repo}`,
    labels: "report",
    body: `Repository: https://github.com/${entry.repo}\n\nWhat is wrong with it:\n`,
  });
  return `https://github.com/${SOURCE}/issues/new?${params}`;
}

async function main() {
  lang = pickLanguage();
  const element = document.getElementById("catalog");
  element.mode = "site";
  element.reportUrl = reportUrl;
  const [owner, repository] = SOURCE.split("/");
  document.getElementById("self-link").href =
    `https://my.home-assistant.io/redirect/hacs_repository/?${new URLSearchParams({ owner, repository, category: "integration" })}`;
  document.getElementById("source").href = `https://github.com/${SOURCE}`;
  document.getElementById("lang").addEventListener("click", () => {
    lang = lang === "en" ? "sv" : "en";
    try {
      localStorage.setItem("bazaar-lang", lang);
    } catch {
      // Not remembered; the toggle still works for this visit.
    }
    applyLanguage();
  });
  applyLanguage();

  const loading = document.getElementById("loading");
  try {
    const response = await fetch("catalog.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    catalog = await response.json();
    await customElements.whenDefined("bazaar-catalog");
    element.lang = lang;
    element.catalog = catalog;
    loading.remove();
    showStats();
  } catch (err) {
    loading.textContent = lang === "sv" ? `Katalogen gick inte att ladda (${err.message}).` : `The catalog could not be loaded (${err.message}).`;
  }
}

main();
