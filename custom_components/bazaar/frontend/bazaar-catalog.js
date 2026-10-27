// <bazaar-catalog>: search, filters and a compact list or cards over catalog.json.
//
// One component for both places the catalog is shown. On the website (mode
// "site") the action is a My Home Assistant link, and HACS asks whether to add
// the repository. In the Home Assistant panel (mode "panel") the host element
// adds it over HACS's websocket API and passes back what HACS already has in
// `known`. Colours come from Home Assistant's theme variables, which the
// website defines itself.

const PAGE = 60;
const VIEW_KEY = "bazaar-view";
const MY_LINK = "https://my.home-assistant.io/redirect/hacs_repository/";
const OTHER = new Set(["template", "python_script", "appdaemon"]);
const FIRST_OWNER = "beolink/";
const CHECKS = ["archived", "description", "topics", "issues", "information", "hacsjson", "license"];
const INTEGRATION_CHECKS = [...CHECKS, "integration_manifest", "brands"];

const STRINGS = {
  en: {
    search: "Search name, description or topic",
    category: "Type",
    all: "All",
    integration: "Integrations",
    plugin: "Dashboard",
    theme: "Themes",
    other: "Other",
    status: "Status",
    pending: "In the HACS queue",
    unsubmitted: "Not submitted",
    sort: "Sort",
    sort_score: "Recommended",
    sort_stars: "Most stars",
    sort_updated: "Recently updated",
    sort_queue: "Longest in the HACS queue",
    sort_created: "Newest",
    only_passing: "Passes HACS checks",
    hide_flagged: "Hide red flags",
    has_release: "Has a release",
    hide_clashes: "Hide clashes",
    view: "View",
    compact: "Compact",
    full: "Full",
    clash_short: "Clash",
    today_short: "today",
    checks_failed: (ok, all, names) => `HACS checks ${ok} of ${all}, failed: ${names}`,
    clash_hacs: (repo) => `Same domain as ${repo} in HACS: only one of them can be installed`,
    clash_core: (domain) => `Replaces Home Assistant's built-in ${domain} integration`,
    clash_shared: (n) => (n === 1 ? "1 other repository here uses the same domain" : `${n} other repositories here use the same domain`),
    count: (shown, total) => `${shown} of ${total}`,
    more: "Show more",
    none: "Nothing matches. Loosen a filter or clear the search.",
    cat: {
      integration: "Integration", plugin: "Dashboard", theme: "Theme",
      template: "Template", python_script: "Python script", appdaemon: "AppDaemon",
    },
    queue: (pr, time) => (time ? `In the HACS queue for ${time}, PR #${pr}` : `In the HACS queue since today, PR #${pr}`),
    pr_ok: "PR checks passed",
    pr_failed: (names) => `PR checks failed: ${names}`,
    pr_running: "PR checks running",
    stars: (n, one) => (one ? `${n} star` : `${n} stars`),
    updated: (when) => `updated ${when}`,
    ha_min: (v) => `HA ${v} or later`,
    no_release: "no release",
    fork_of: (p) => `fork of ${p}`,
    checks: (ok, all) => `HACS checks ${ok} of ${all}`,
    scanned: (files, skipped, asset) =>
      `${files} Python files read${asset ? " from the release zip" : ""}${skipped ? `, ${skipped} not` : ""}`,
    not_scanned: "Source not read",
    scan_error: "Source could not be read",
    details: "Details",
    open_hacs: "Open in HACS",
    add_hacs: "Add to HACS",
    adding: "Adding…",
    installed: "Installed",
    added: "In HACS",
    github: "GitHub",
    report: "Report",
    dialog_title: (name) => `Add ${name} to HACS?`,
    dialog_body:
      "HACS has not reviewed this repository. It will be added to HACS as a custom repository, " +
      "and HACS will install and update it like any other. Read the code first if anything below worries you.",
    dialog_flags: "What a first read of the code found",
    dialog_noflags: "A first read of the code found nothing that stands out.",
    dialog_partial: (n) => `Some of the code was not read: ${n} files were too large or too many. Nothing stood out in the rest.`,
    dialog_unscanned: "The code has not been read automatically. Only integrations installed from their source are.",
    dialog_go_site: "Continue in Home Assistant",
    dialog_go_panel: "Add to HACS",
    cancel: "Cancel",
    check: {
      archived: "Not archived", description: "Has a description", topics: "Has topics",
      issues: "Issues enabled", information: "Has a README", hacsjson: "Valid hacs.json",
      license: "OSI-approved licence", integration_manifest: "Complete manifest.json",
      brands: "Brand icon",
    },
    unknown: "not known",
    flag: {
      "dynamic-code": "Runs text as Python code (exec or eval)",
      "obfuscated-exec": "Decodes data and runs it as code",
      marshal: "Loads compiled code from bytes",
      "ha-credentials": "Touches Home Assistant's login data or secrets.yaml",
      shell: "Starts programs on the host",
      "runtime-install": "Installs packages while running",
      "token-minting": "Creates users or access tokens",
      "encoded-blob": "Contains a long encoded string",
      "requirement-url": "Installs a dependency straight from a URL",
      "dynamic-import": "Imports modules by name",
      "native-code": "Calls native code (ctypes)",
      "deletes-files": "Deletes directory trees",
    },
  },
  sv: {
    search: "Sök namn, beskrivning eller ämne",
    category: "Typ",
    all: "Alla",
    integration: "Integrationer",
    plugin: "Dashboard",
    theme: "Teman",
    other: "Övrigt",
    status: "Status",
    pending: "I HACS-kön",
    unsubmitted: "Inte inskickade",
    sort: "Sortera",
    sort_score: "Rekommenderade",
    sort_stars: "Flest stjärnor",
    sort_updated: "Senast uppdaterade",
    sort_queue: "Längst i HACS-kön",
    sort_created: "Nyaste",
    only_passing: "Klarar HACS kontroller",
    hide_flagged: "Dölj röda flaggor",
    has_release: "Har en release",
    hide_clashes: "Dölj krockar",
    view: "Visning",
    compact: "Kompakt",
    full: "Full",
    clash_short: "Krock",
    today_short: "i dag",
    checks_failed: (ok, all, names) => `HACS-kontroller ${ok} av ${all}, föll: ${names}`,
    clash_hacs: (repo) => `Samma domän som ${repo} i HACS: bara den ena kan installeras`,
    clash_core: (domain) => `Ersätter Home Assistants inbyggda integration ${domain}`,
    clash_shared: (n) => (n === 1 ? "1 annat repo här använder samma domän" : `${n} andra repon här använder samma domän`),
    count: (shown, total) => `${shown} av ${total}`,
    more: "Visa fler",
    none: "Inget matchar. Lätta på ett filter eller töm sökningen.",
    cat: {
      integration: "Integration", plugin: "Dashboard", theme: "Tema",
      template: "Mall", python_script: "Pythonskript", appdaemon: "AppDaemon",
    },
    queue: (pr, time) => (time ? `I HACS-kön i ${time}, PR #${pr}` : `I HACS-kön sedan i dag, PR #${pr}`),
    pr_ok: "PR-kontrollerna gick igenom",
    pr_failed: (names) => `PR-kontroller föll: ${names}`,
    pr_running: "PR-kontrollerna körs",
    stars: (n, one) => (one ? `${n} stjärna` : `${n} stjärnor`),
    updated: (when) => `uppdaterad ${when}`,
    ha_min: (v) => `HA ${v} eller senare`,
    no_release: "ingen release",
    fork_of: (p) => `fork av ${p}`,
    checks: (ok, all) => `HACS-kontroller ${ok} av ${all}`,
    scanned: (files, skipped, asset) =>
      `${files} Pythonfiler lästa${asset ? " ur releasens zip" : ""}${skipped ? `, ${skipped} inte` : ""}`,
    not_scanned: "Koden inte läst",
    scan_error: "Koden gick inte att läsa",
    details: "Detaljer",
    open_hacs: "Öppna i HACS",
    add_hacs: "Lägg till i HACS",
    adding: "Lägger till…",
    installed: "Installerad",
    added: "Finns i HACS",
    github: "GitHub",
    report: "Anmäl",
    dialog_title: (name) => `Lägga till ${name} i HACS?`,
    dialog_body:
      "HACS har inte granskat det här repot. Det läggs till i HACS som ett anpassat repo, " +
      "och HACS installerar och uppdaterar det som alla andra. Läs koden först om något nedan oroar dig.",
    dialog_flags: "Det här hittade en första läsning av koden",
    dialog_noflags: "En första läsning av koden hittade inget som sticker ut.",
    dialog_partial: (n) => `En del av koden lästes inte: ${n} filer var för stora eller för många. I resten stack inget ut.`,
    dialog_unscanned: "Koden har inte lästs automatiskt. Det görs bara för integrationer som installeras från sin källkod.",
    dialog_go_site: "Fortsätt i Home Assistant",
    dialog_go_panel: "Lägg till i HACS",
    cancel: "Avbryt",
    check: {
      archived: "Inte arkiverat", description: "Har en beskrivning", topics: "Har ämnen",
      issues: "Ärenden påslagna", information: "Har en README", hacsjson: "Giltig hacs.json",
      license: "OSI-godkänd licens", integration_manifest: "Komplett manifest.json",
      brands: "Varumärkesikon",
    },
    unknown: "okänt",
    flag: {
      "dynamic-code": "Kör text som Pythonkod (exec eller eval)",
      "obfuscated-exec": "Avkodar data och kör den som kod",
      marshal: "Laddar kompilerad kod ur bytes",
      "ha-credentials": "Rör Home Assistants inloggningsdata eller secrets.yaml",
      shell: "Startar program på värden",
      "runtime-install": "Installerar paket medan den körs",
      "token-minting": "Skapar användare eller åtkomsttoken",
      "encoded-blob": "Innehåller en lång kodad sträng",
      "requirement-url": "Installerar ett beroende direkt från en URL",
      "dynamic-import": "Importerar moduler via namn",
      "native-code": "Anropar maskinkod (ctypes)",
      "deletes-files": "Raderar kataloger",
    },
  },
};

const ICON = {
  star: "M12,17.27L18.18,21L16.54,13.97L22,9.24L14.81,8.62L12,2L9.19,8.62L2,9.24L7.45,13.97L5.82,21L12,17.27Z",
  tag: "M5.5,7A1.5,1.5 0 0,1 4,5.5A1.5,1.5 0 0,1 5.5,4A1.5,1.5 0 0,1 7,5.5A1.5,1.5 0 0,1 5.5,7M21.41,11.58L12.41,2.58C12.05,2.22 11.55,2 11,2H4C2.89,2 2,2.89 2,4V11C2,11.55 2.22,12.05 2.59,12.41L11.58,21.41C11.95,21.77 12.45,22 13,22C13.55,22 14.05,21.77 14.41,21.41L21.41,14.41C21.78,14.05 22,13.55 22,13C22,12.44 21.77,11.94 21.41,11.58Z",
  clock: "M12,20A8,8 0 0,0 20,12A8,8 0 0,0 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22C6.47,22 2,17.5 2,12A10,10 0 0,1 12,2M12.5,7V12.25L17,14.92L16.25,16.15L11,13V7H12.5Z",
  queue: "M6,2V8H6V8L10,12L6,16V16H6V22H18V16H18V16L14,12L18,8V8H18V2H6M16,16.5V20H8V16.5L12,12.5L16,16.5M12,11.5L8,7.5V4H16V7.5L12,11.5Z",
  check: "M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z",
  cross: "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z",
  alert: "M13,14H11V10H13M13,18H11V16H13M1,21H23L12,2L1,21Z",
  clash: "M21,9L17,5V8H10V10H17V13M7,11L3,15L7,19V16H14V14H7V11Z",
  chevron: "M7.41,8.58L12,13.17L16.59,8.58L18,10L12,16L6,10L7.41,8.58Z",
  ha: "M12,3L2,12H5V20H19V12H22L12,3M12,8.5C14.34,8.5 16.46,9.43 18,10.94L16.8,12.12C15.58,10.91 13.88,10.17 12,10.17C10.12,10.17 8.42,10.91 7.2,12.12L6,10.94C7.54,9.43 9.66,8.5 12,8.5M12,11.83C13.4,11.83 14.67,12.39 15.6,13.3L14.4,14.47C13.79,13.87 12.94,13.5 12,13.5C11.06,13.5 10.21,13.87 9.6,14.47L8.4,13.3C9.33,12.39 10.6,11.83 12,11.83M12,15.17C12.94,15.17 13.7,15.91 13.7,16.83C13.7,17.75 12.94,18.5 12,18.5C11.06,18.5 10.3,17.75 10.3,16.83C10.3,15.91 11.06,15.17 12,15.17Z",
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const svg = (name, cls = "i") =>
  `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${ICON[name]}"/></svg>`;

const hue = (text) => {
  let h = 0;
  for (const c of text) h = (h * 31 + c.charCodeAt(0)) % 360;
  return h;
};

const STYLE = `
:host {
  container-type: inline-size;
  --bz-fg: var(--primary-text-color, #1d1d1f);
  --bz-muted: var(--secondary-text-color, #5f6368);
  --bz-card: var(--card-background-color, #fff);
  --bz-line: var(--divider-color, rgba(0, 0, 0, 0.12));
  --bz-accent: var(--primary-color, #03a9f4);
  --bz-on-accent: var(--text-primary-color, #fff);
  --bz-chip: var(--secondary-background-color, #eef0f2);
  --bz-high: var(--error-color, #db4437);
  --bz-medium: var(--warning-color, #e08600);
  --bz-ok: var(--success-color, #2e8b3e);
  --bz-radius: var(--ha-card-border-radius, 12px);
  display: block;
  color: var(--bz-fg);
  font-family: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, system-ui, sans-serif));
  -webkit-font-smoothing: antialiased;
}
* { box-sizing: border-box; }
.controls {
  display: grid;
  gap: 12px;
  margin-bottom: 16px;
}
.search {
  width: 100%;
  font: inherit;
  font-size: 16px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--bz-line);
  background: var(--bz-card);
  color: var(--bz-fg);
}
.search:focus-visible, button:focus-visible, a:focus-visible, select:focus-visible, summary:focus-visible, input:focus-visible {
  outline: 2px solid var(--bz-accent);
  outline-offset: 2px;
}
.row { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; }
.seg { display: flex; flex-wrap: wrap; gap: 6px; }
.seg button {
  font: inherit; font-size: 14px;
  padding: 6px 12px; border-radius: 999px;
  border: 1px solid var(--bz-line); background: var(--bz-card); color: var(--bz-fg);
  cursor: pointer;
}
.seg button[aria-pressed="true"] { background: var(--bz-accent); border-color: var(--bz-accent); color: var(--bz-on-accent); }
label.sel { display: inline-flex; gap: 6px; align-items: center; font-size: 14px; color: var(--bz-muted); }
select {
  font: inherit; font-size: 14px; color: var(--bz-fg);
  background: var(--bz-card); border: 1px solid var(--bz-line); border-radius: 8px; padding: 6px 8px;
}
label.tog { display: inline-flex; gap: 6px; align-items: center; font-size: 14px; cursor: pointer; }
label.tog input { accent-color: var(--bz-accent); width: 16px; height: 16px; margin: 0; }
.count { font-size: 14px; color: var(--bz-muted); margin-left: auto; }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 340px), 1fr));
  gap: 12px;
}
.card {
  background: var(--bz-card);
  border: 1px solid var(--bz-line);
  border-radius: var(--bz-radius);
  padding: 16px;
  display: flex; flex-direction: column; gap: 10px;
  min-width: 0;
}
.head { display: flex; gap: 12px; align-items: flex-start; min-width: 0; }
.icon {
  flex: none; width: 44px; height: 44px; border-radius: 10px;
  display: grid; place-items: center; overflow: hidden;
  font-weight: 600; font-size: 20px; color: #fff;
}
.icon img { width: 100%; height: 100%; object-fit: contain; background: transparent; }
.title { min-width: 0; flex: 1; }
.name { font-size: 16px; font-weight: 600; line-height: 1.3; overflow-wrap: anywhere; }
.repo { font-size: 13px; color: var(--bz-muted); overflow-wrap: anywhere; }
.repo a { color: inherit; text-decoration: none; }
.repo a:hover { text-decoration: underline; }
.cat {
  flex: none; font-size: 12px; padding: 2px 8px; border-radius: 999px;
  background: var(--bz-chip); color: var(--bz-muted); white-space: nowrap;
}
.desc {
  font-size: 14px; line-height: 1.45; margin: 0; color: var(--bz-fg);
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  overflow-wrap: anywhere;
}
.meta { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 13px; color: var(--bz-muted); }
.meta span { display: inline-flex; gap: 4px; align-items: center; }
.i { width: 15px; height: 15px; fill: currentColor; flex: none; }
.badges { display: flex; flex-wrap: wrap; gap: 6px; }
.badge {
  display: inline-flex; gap: 4px; align-items: center;
  font-size: 12px; line-height: 1.3; padding: 3px 8px; border-radius: 6px;
  background: var(--bz-chip); color: var(--bz-fg);
}
.badge.queue { background: color-mix(in srgb, var(--bz-accent) 14%, transparent); }
.badge.ok { color: var(--bz-ok); background: color-mix(in srgb, var(--bz-ok) 12%, transparent); }
.badge.high { color: var(--bz-high); background: color-mix(in srgb, var(--bz-high) 12%, transparent); }
.badge.medium { color: var(--bz-medium); background: color-mix(in srgb, var(--bz-medium) 14%, transparent); }
details { font-size: 13px; color: var(--bz-muted); }
summary { cursor: pointer; width: fit-content; }
details ul { margin: 8px 0 0; padding: 0; list-style: none; display: grid; gap: 4px; }
details li { display: flex; gap: 6px; align-items: flex-start; }
details li .i.ok { fill: var(--bz-ok); }
details li .i.bad { fill: var(--bz-high); }
details li .i.mid { fill: var(--bz-medium); }
details a { color: var(--bz-accent); overflow-wrap: anywhere; }
.where { display: block; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: auto; padding-top: 4px; }
.btn {
  font: inherit; font-size: 14px; font-weight: 500;
  display: inline-flex; gap: 6px; align-items: center;
  padding: 8px 14px; border-radius: 8px; cursor: pointer; text-decoration: none;
  border: 1px solid var(--bz-line); background: transparent; color: var(--bz-fg);
}
.btn.primary { background: var(--bz-accent); border-color: var(--bz-accent); color: var(--bz-on-accent); }
.btn[disabled] { opacity: 0.6; cursor: progress; }
.btn .i { width: 18px; height: 18px; }
.link { font-size: 13px; color: var(--bz-muted); text-decoration: none; padding: 8px 4px; }
.link:hover { text-decoration: underline; }
.state { font-size: 13px; color: var(--bz-ok); display: inline-flex; gap: 4px; align-items: center; }
.grid.list { display: block; }
.rows {
  list-style: none; margin: 0; padding: 0;
  background: var(--bz-card); border: 1px solid var(--bz-line); border-radius: var(--bz-radius);
  overflow: hidden;
}
.rows > li + li { border-top: 1px solid var(--bz-line); }
.rows > li.x { border-top: none; }
.r { display: flex; align-items: center; gap: 12px; padding: 6px 12px; min-height: 50px; }
.r:hover { background: color-mix(in srgb, var(--bz-fg) 4%, transparent); }
.icon.sm { width: 28px; height: 28px; border-radius: 7px; font-size: 14px; }
.c-main {
  flex: 1; min-width: 0; display: flex; align-items: baseline; gap: 8px;
  font: inherit; color: inherit; background: none; border: 0; padding: 6px 0; text-align: left; cursor: pointer;
}
.c-main .nm { font-size: 15px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: none; max-width: calc(100% - 26px); }
.c-main .rp { font-size: 13px; color: var(--bz-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; flex: 0 1 auto; }
.c-main .chev { width: 18px; height: 18px; fill: var(--bz-muted); flex: none; align-self: center; transition: transform 0.15s; }
.c-main[aria-expanded="true"] .chev { transform: rotate(180deg); }
.c-main:hover .nm { text-decoration: underline; }
.c-sig { flex: none; width: 160px; display: flex; gap: 8px; align-items: center; overflow: hidden; }
.sg { display: inline-flex; gap: 3px; align-items: center; font-size: 12px; color: var(--bz-muted); white-space: nowrap; }
.sg .i { width: 16px; height: 16px; }
.sg.high { color: var(--bz-high); }
.sg.medium { color: var(--bz-medium); }
.sg.ok { color: var(--bz-ok); }
.c-cat, .c-rel, .c-upd {
  flex: none; font-size: 13px; color: var(--bz-muted);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.c-cat { width: 92px; font-size: 12px; }
.c-rel { width: 96px; }
.c-upd { width: 124px; }
.c-stars { flex: none; width: 64px; display: inline-flex; gap: 4px; align-items: center; justify-content: flex-end; font-size: 13px; color: var(--bz-muted); }
.c-act { flex: none; width: 160px; display: flex; justify-content: flex-end; }
.btn.sm { font-size: 13px; padding: 5px 10px; gap: 5px; }
.btn.sm .i { width: 16px; height: 16px; }
.btn.state { color: var(--bz-ok); }
.x { padding: 2px 12px 14px 52px; }
.x .card { border: none; padding: 0; background: transparent; }
@container (max-width: 1040px) { .c-upd { display: none; } }
@container (max-width: 900px) { .c-cat, .c-rel { display: none; } }
@container (max-width: 640px) {
  .r { gap: 10px; padding: 6px 10px; }
  .c-main { flex-direction: column; align-items: flex-start; gap: 0; padding: 4px 0; }
  .c-main .nm, .c-main .rp { max-width: 100%; }
  .c-main .chev { display: none; }
  .c-stars { display: none; }
  .c-sig { width: auto; max-width: 96px; gap: 6px; }
  .sg .t { display: none; }
  .c-act { width: auto; }
  .c-act .lbl { display: none; }
  .btn.sm { padding: 7px; }
  .x { padding-left: 10px; padding-right: 10px; }
}
.empty { padding: 48px 16px; text-align: center; color: var(--bz-muted); }
.more { display: flex; justify-content: center; margin: 20px 0 8px; }
dialog {
  border: none; border-radius: 16px; padding: 0; max-width: min(520px, calc(100vw - 32px));
  background: var(--bz-card); color: var(--bz-fg);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
}
dialog::backdrop { background: rgba(0, 0, 0, 0.45); }
.dlg { padding: 20px 22px; display: grid; gap: 12px; }
.dlg h2 { margin: 0; font-size: 19px; line-height: 1.3; overflow-wrap: anywhere; }
.dlg p { margin: 0; font-size: 14px; line-height: 1.5; }
.dlg h3 { margin: 4px 0 0; font-size: 14px; }
.dlg ul { margin: 0; padding-left: 0; list-style: none; display: grid; gap: 6px; font-size: 14px; }
.dlg li { display: flex; gap: 6px; align-items: flex-start; }
.dlg .i.bad { fill: var(--bz-high); }
.dlg .i.mid { fill: var(--bz-medium); }
.dlg .i.low { fill: var(--bz-muted); }
.dlg .buttons { display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; margin-top: 6px; }
@media (max-width: 600px) {
  .count { margin-left: 0; width: 100%; }
}
`;

const FLAG_ICON = { high: "bad", medium: "mid", low: "low" };
const REPO = /^[A-Za-z0-9][A-Za-z0-9-]*\/[A-Za-z0-9._-]+$/;

// The catalog is other people's text and may come from an address the user
// chose, so every field is held to the shape this file expects before use.
function normalize(raw) {
  if (!raw || typeof raw !== "object" || typeof raw.repo !== "string" || !REPO.test(raw.repo)) return null;
  const str = (v) => (typeof v === "string" ? v : "");
  const list = (v) => (Array.isArray(v) ? v.filter((x) => typeof x === "string") : []);
  const num = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0);
  const date = (v) => (typeof v === "string" && !Number.isNaN(Date.parse(v)) ? v : null);
  const e = {
    repo: raw.repo,
    category: str(raw.category) || "integration",
    name: str(raw.name) || raw.repo.split("/")[1],
    description: str(raw.description),
    domain: str(raw.domain),
    stars: num(raw.stars),
    score: num(raw.score),
    topics: list(raw.topics),
    updated: date(raw.updated),
    created: date(raw.created),
    homeassistant: str(raw.homeassistant),
    fork_of: str(raw.fork_of),
    icon: typeof raw.icon === "string" && /^https:\/\//.test(raw.icon) ? raw.icon : null,
    failed: list(raw.failed),
    unknown: list(raw.unknown),
    release: raw.release && typeof raw.release === "object" ? { tag: str(raw.release.tag), date: date(raw.release.date) } : null,
    pending: null,
    scan: null,
    conflicts: {},
  };
  if (raw.conflicts && typeof raw.conflicts === "object") {
    const c = raw.conflicts;
    if (typeof c.hacs === "string" && REPO.test(c.hacs)) e.conflicts.hacs = c.hacs;
    if (c.core === true && e.domain) e.conflicts.core = true;
    if (Number.isInteger(c.shared) && c.shared > 0) e.conflicts.shared = c.shared;
  }
  if (raw.pending && typeof raw.pending === "object" && date(raw.pending.since)) {
    e.pending = {
      pr: Math.trunc(num(raw.pending.pr)),
      since: raw.pending.since,
      checks: ["success", "failure", "pending"].includes(raw.pending.checks) ? raw.pending.checks : null,
      failed: list(raw.pending.failed),
    };
  }
  if (raw.scan && typeof raw.scan === "object") {
    e.scan = {
      ref: str(raw.scan.ref),
      error: str(raw.scan.error),
      files: Math.trunc(num(raw.scan.files)),
      skipped: Math.trunc(num(raw.scan.skipped)),
      asset: str(raw.scan.asset),
      flags: (Array.isArray(raw.scan.flags) ? raw.scan.flags : [])
        .filter((f) => f && typeof f.rule === "string")
        .map((f) => ({
          rule: f.rule,
          severity: FLAG_ICON[f.severity] ? f.severity : "low",
          hits: Math.max(1, Math.trunc(num(f.hits))),
          where: list(f.where),
        })),
    };
  }
  return e;
}

class BazaarCatalog extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._catalog = null;
    this._items = [];
    this._known = new Map();
    this._busy = new Set();
    this._lang = "en";
    this._mode = "site";
    this._reportUrl = null;
    this._shown = PAGE;
    this._state = { q: "", cat: "all", status: "all", sort: "score", passing: false, safe: false, release: false, clashes: false };
    this._view = "compact";
    try {
      if (localStorage.getItem(VIEW_KEY) === "full") this._view = "full";
    } catch {
      // Blocked storage: every visit starts compact.
    }
    this._expanded = new Set();
    this._timer = null;
    this.shadowRoot.addEventListener(
      "error",
      (ev) => {
        const img = ev.target;
        if (img instanceof HTMLImageElement) {
          const box = img.parentElement;
          box.textContent = box.dataset.letter || "?";
          box.style.background = box.dataset.color;
        }
      },
      true,
    );
  }

  connectedCallback() {
    // Properties set before the element was defined hide the setters until moved.
    for (const name of ["mode", "lang", "reportUrl", "known", "busy", "catalog"]) {
      if (Object.prototype.hasOwnProperty.call(this, name)) {
        const value = this[name];
        delete this[name];
        this[name] = value;
      }
    }
  }

  set catalog(value) {
    this._catalog = value;
    const repositories = Array.isArray(value?.repositories) ? value.repositories : [];
    this._items = repositories
      .map(normalize)
      .filter(Boolean)
      .map((e) => ({ ...e, _hay: [e.name, e.repo, e.description, e.domain, ...e.topics].join(" ").toLowerCase() }));
    this._render();
  }

  get catalog() {
    return this._catalog;
  }

  // Lowercased full name to {id, installed} for what HACS already tracks.
  set known(value) {
    this._known = value || new Map();
    if (this._catalog) this._renderList();
  }

  set busy(value) {
    this._busy = value || new Set();
    if (this._catalog) this._renderList();
  }

  set lang(value) {
    this._lang = String(value || "en").toLowerCase().startsWith("sv") ? "sv" : "en";
    if (this._catalog) this._render();
  }

  set mode(value) {
    this._mode = value === "panel" ? "panel" : "site";
  }

  set reportUrl(value) {
    this._reportUrl = value;
  }

  get t() {
    return STRINGS[this._lang];
  }

  _filtered() {
    const s = this._state;
    const words = s.q.toLowerCase().split(/\s+/).filter(Boolean);
    const now = Date.now();
    let list = this._items.filter((e) => {
      if (s.cat === "other" ? !OTHER.has(e.category) : s.cat !== "all" && e.category !== s.cat) return false;
      if (s.status === "pending" && !e.pending) return false;
      if (s.status === "unsubmitted" && e.pending) return false;
      if (s.passing && ((e.failed || []).length || e.pending?.checks === "failure")) return false;
      if (s.safe && (e.scan?.flags || []).some((f) => f.severity === "high")) return false;
      if (s.release && !e.release) return false;
      if (s.clashes && (e.conflicts.hacs || e.conflicts.core)) return false;
      return words.every((w) => e._hay.includes(w));
    });
    const time = (v) => (v ? Date.parse(v) : 0);
    const by = {
      score: (a, b) => b.score - a.score,
      stars: (a, b) => b.stars - a.stars,
      updated: (a, b) => time(b.updated) - time(a.updated),
      created: (a, b) => time(b.created) - time(a.created),
      queue: (a, b) => (a.pending ? time(a.pending.since) : now) - (b.pending ? time(b.pending.since) : now),
    }[s.sort];
    const first = (e) => (words.length && e.repo.toLowerCase().startsWith(FIRST_OWNER) ? 0 : 1);
    list = list.slice().sort((a, b) => first(a) - first(b) || by(a, b) || b.score - a.score);
    return list;
  }

  _ago(stamp) {
    if (!stamp) return "";
    const days = Math.round((Date.parse(stamp) - Date.now()) / 86400000);
    const rtf = new Intl.RelativeTimeFormat(this._lang, { numeric: "auto" });
    if (Math.abs(days) < 1) return rtf.format(0, "day");
    if (Math.abs(days) < 45) return rtf.format(days, "day");
    if (Math.abs(days) < 550) return rtf.format(Math.round(days / 30.4), "month");
    return rtf.format(Math.round(days / 365), "year");
  }

  _duration(stamp, display = "long") {
    const days = Math.max(0, Math.floor((Date.now() - Date.parse(stamp)) / 86400000));
    if (days === 0) return null;
    const [n, unit] = days < 60 ? [days, "day"] : [Math.round(days / 30.4), "month"];
    return new Intl.NumberFormat(this._lang, { style: "unit", unit, unitDisplay: display }).format(n);
  }

  _render() {
    if (!this._catalog) return;
    const t = this.t;
    const s = this._state;
    const labels = { cat: t.category, status: t.status, view: t.view };
    const segment = (key, options, current = s[key]) =>
      `<div class="seg" role="group" aria-label="${esc(labels[key])}">${options
        .map((v) => `<button type="button" data-${key}="${v}" aria-pressed="${current === v}">${esc(t[v])}</button>`)
        .join("")}</div>`;
    const sorts = ["score", "stars", "updated", "queue", "created"];
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <div class="controls">
        <input class="search" type="search" placeholder="${esc(t.search)}" aria-label="${esc(t.search)}" value="${esc(s.q)}">
        <div class="row">
          ${segment("cat", ["all", "integration", "plugin", "theme", "other"])}
        </div>
        <div class="row">
          ${segment("status", ["all", "pending", "unsubmitted"])}
          <label class="sel">${esc(t.sort)}
            <select>${sorts
              .map((v) => `<option value="${v}" ${s.sort === v ? "selected" : ""}>${esc(t["sort_" + v])}</option>`)
              .join("")}</select>
          </label>
          ${segment("view", ["compact", "full"], this._view)}
        </div>
        <div class="row">
          <label class="tog"><input type="checkbox" data-tog="passing" ${s.passing ? "checked" : ""}>${esc(t.only_passing)}</label>
          <label class="tog"><input type="checkbox" data-tog="safe" ${s.safe ? "checked" : ""}>${esc(t.hide_flagged)}</label>
          <label class="tog"><input type="checkbox" data-tog="release" ${s.release ? "checked" : ""}>${esc(t.has_release)}</label>
          <label class="tog"><input type="checkbox" data-tog="clashes" ${s.clashes ? "checked" : ""}>${esc(t.hide_clashes)}</label>
          <span class="count" aria-live="polite"></span>
        </div>
      </div>
      <div class="grid"></div>
      <div class="more"></div>
      <dialog></dialog>`;
    const root = this.shadowRoot;
    const search = root.querySelector(".search");
    // Read the field itself when the timer fires: once an event from inside a
    // shadow root has been dispatched, the browser sets its target to null.
    search.addEventListener("input", () => {
      clearTimeout(this._timer);
      this._timer = setTimeout(() => this._update({ q: search.value }), 120);
    });
    root.querySelectorAll("[data-cat]").forEach((b) =>
      b.addEventListener("click", () => this._update({ cat: b.dataset.cat }, true)),
    );
    root.querySelectorAll("[data-status]").forEach((b) =>
      b.addEventListener("click", () => this._update({ status: b.dataset.status }, true)),
    );
    root.querySelectorAll("[data-view]").forEach((b) => b.addEventListener("click", () => this._setView(b.dataset.view)));
    root.querySelector("select").addEventListener("change", (ev) => this._update({ sort: ev.target.value }));
    root.querySelectorAll("[data-tog]").forEach((c) =>
      c.addEventListener("change", () => this._update({ [c.dataset.tog]: c.checked })),
    );
    root.querySelector(".grid").addEventListener("click", (ev) => this._onAction(ev));
    root.querySelector(".more").addEventListener("click", (ev) => {
      if (ev.target.closest("button")) {
        this._shown += PAGE;
        this._renderList();
      }
    });
    this._renderList();
  }

  _update(change, segments = false) {
    Object.assign(this._state, change);
    this._shown = PAGE;
    if (segments) {
      this.shadowRoot.querySelectorAll("[data-cat]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.cat === this._state.cat));
      this.shadowRoot.querySelectorAll("[data-status]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.status === this._state.status));
    }
    this._renderList();
    this.dispatchEvent(new CustomEvent("bazaar-filters", { detail: { ...this._state } }));
  }

  _setView(view) {
    this._view = view === "full" ? "full" : "compact";
    try {
      localStorage.setItem(VIEW_KEY, this._view);
    } catch {
      // Not remembered; the choice still holds for this visit.
    }
    this.shadowRoot.querySelectorAll("[data-view]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.view === this._view));
    this._renderList();
  }

  _renderList() {
    const root = this.shadowRoot;
    const grid = root.querySelector(".grid");
    if (!grid) return;
    const t = this.t;
    const list = this._filtered();
    this._visible = list.slice(0, this._shown);
    root.querySelector(".count").textContent = t.count(
      Math.min(this._shown, list.length).toLocaleString(this._lang),
      list.length.toLocaleString(this._lang),
    );
    const compact = this._view === "compact";
    grid.className = compact ? "grid list" : "grid";
    if (!list.length) grid.innerHTML = `<div class="empty">${esc(t.none)}</div>`;
    else if (compact) grid.innerHTML = `<ul class="rows">${this._visible.map((e, i) => this._row(e, i)).join("")}</ul>`;
    else grid.innerHTML = this._visible.map((e, i) => this._card(e, i)).join("");
    root.querySelector(".more").innerHTML =
      list.length > this._shown ? `<button type="button" class="btn">${esc(t.more)}</button>` : "";
  }

  // One line per repository; the name opens the full card beneath it.
  _row(e, index) {
    const t = this.t;
    const [owner, name] = e.repo.split("/");
    const letter = (e.name || name).trim().charAt(0).toUpperCase();
    const color = `hsl(${hue(e.repo)} 45% 45%)`;
    const icon = e.icon
      ? `<img src="${esc(e.icon)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
      : esc(letter);
    const open = this._expanded.has(e.repo.toLowerCase());
    const known = this._known.get(e.repo.toLowerCase());
    const flags = e.scan?.flags || [];
    const failed = e.failed || [];
    const checkKeys = e.category === "integration" ? INTEGRATION_CHECKS : CHECKS;
    const sig = (cls, iconName, text, label) =>
      `<span class="sg ${cls}" role="img" aria-label="${esc(label)}" title="${esc(label)}">${svg(iconName)}${
        text ? `<span class="t">${esc(text)}</span>` : ""
      }</span>`;
    const byLevel = (level) => flags.filter((f) => f.severity === level);
    const flagSig = (level) => {
      const hits = byLevel(level);
      return hits.length ? sig(level, "alert", String(hits.length), hits.map((f) => t.flag[f.rule] || f.rule).join(", ")) : "";
    };
    const clashes = this._clashes(e);
    const pr = e.pending?.checks;
    const signals = [
      flagSig("high"),
      pr === "failure" ? sig("high", "cross", "PR", t.pr_failed((e.pending.failed || []).join(", "))) : "",
      clashes.length ? sig("medium", "clash", t.clash_short, clashes.join(". ")) : "",
      flagSig("medium"),
      e.pending
        ? sig("", "queue", this._duration(e.pending.since, "short") || t.today_short,
            t.queue(e.pending.pr, this._duration(e.pending.since)))
        : "",
      pr === "success" ? sig("ok", "check", "PR", t.pr_ok) : pr === "pending" ? sig("", "clock", "PR", t.pr_running) : "",
      failed.length
        ? sig("", "cross", `${checkKeys.length - failed.length}/${checkKeys.length}`,
            t.checks_failed(checkKeys.length - failed.length, checkKeys.length, failed.map((k) => t.check[k] || k).join(", ")))
        : "",
    ].join("");

    let action;
    if (this._mode === "panel" && known) {
      const state = known.installed ? t.installed : t.added;
      action = `<button type="button" class="btn sm state" data-open="${index}" title="${esc(t.open_hacs)}" aria-label="${esc(`${state}. ${t.open_hacs}`)}">${svg("check")}<span class="lbl">${esc(state)}</span></button>`;
    } else if (this._mode === "panel") {
      const busy = this._busy.has(e.repo.toLowerCase());
      action = `<button type="button" class="btn sm primary" data-add="${index}" aria-label="${esc(t.add_hacs)}" ${busy ? "disabled" : ""}>${svg("ha")}<span class="lbl">${esc(busy ? t.adding : t.add_hacs)}</span></button>`;
    } else {
      action = `<button type="button" class="btn sm primary" data-add="${index}" aria-label="${esc(t.open_hacs)}">${svg("ha")}<span class="lbl">${esc(t.open_hacs)}</span></button>`;
    }

    return `<li class="r">
        <div class="icon sm" style="${e.icon ? "" : `background:${color}`}" data-letter="${esc(letter)}" data-color="${color}">${icon}</div>
        <button type="button" class="c-main" data-expand="${index}" aria-expanded="${open}">
          <span class="nm">${esc(e.name)}</span><span class="rp">${esc(owner)}/${esc(name)}</span>${svg("chevron", "i chev")}
        </button>
        <span class="c-sig">${signals}</span>
        <span class="c-cat">${esc(t.cat[e.category] || e.category)}</span>
        <span class="c-stars" role="img" aria-label="${esc(t.stars(e.stars.toLocaleString(this._lang), e.stars === 1))}">${svg("star")}${esc(e.stars.toLocaleString(this._lang))}</span>
        <span class="c-rel">${esc(e.release ? e.release.tag : t.no_release)}</span>
        <span class="c-upd">${esc(e.updated ? this._ago(e.updated) : "")}</span>
        <span class="c-act">${action}</span>
      </li>${open ? `<li class="x">${this._card(e, index, true)}</li>` : ""}`;
  }

  _card(e, index, inline = false) {
    const t = this.t;
    const [owner, name] = e.repo.split("/");
    const letter = (e.name || name).trim().charAt(0).toUpperCase();
    const color = `hsl(${hue(e.repo)} 45% 45%)`;
    const icon = e.icon
      ? `<img src="${esc(e.icon)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
      : esc(letter);
    const known = this._known.get(e.repo.toLowerCase());
    const flags = e.scan?.flags || [];
    const failed = e.failed || [];
    const unknown = e.unknown || [];
    const checkKeys = e.category === "integration" ? INTEGRATION_CHECKS : CHECKS;
    const badges = [];
    if (e.pending) {
      badges.push(`<span class="badge queue">${svg("queue")}${esc(t.queue(e.pending.pr, this._duration(e.pending.since)))}</span>`);
      if (e.pending.checks === "success") badges.push(`<span class="badge ok">${svg("check")}${esc(t.pr_ok)}</span>`);
      else if (e.pending.checks === "failure")
        badges.push(`<span class="badge high">${svg("cross")}${esc(t.pr_failed((e.pending.failed || []).join(", ")))}</span>`);
      else if (e.pending.checks === "pending") badges.push(`<span class="badge">${esc(t.pr_running)}</span>`);
    }
    for (const text of this._clashes(e)) badges.push(`<span class="badge medium">${svg("alert")}${esc(text)}</span>`);
    if (e.conflicts.shared) badges.push(`<span class="badge">${esc(t.clash_shared(e.conflicts.shared))}</span>`);
    for (const f of flags.filter((f) => f.severity !== "low")) {
      badges.push(`<span class="badge ${f.severity}">${svg("alert")}${esc(t.flag[f.rule] || f.rule)}</span>`);
    }
    const meta = [
      `<span>${svg("star")}${esc(t.stars(e.stars.toLocaleString(this._lang), e.stars === 1))}</span>`,
      `<span>${svg("tag")}${esc(e.release ? e.release.tag : t.no_release)}</span>`,
      e.updated ? `<span>${svg("clock")}${esc(t.updated(this._ago(e.updated)))}</span>` : "",
      e.homeassistant ? `<span>${esc(t.ha_min(e.homeassistant))}</span>` : "",
      e.fork_of ? `<span>${esc(t.fork_of(e.fork_of))}</span>` : "",
    ].join("");

    const ref = e.scan?.ref || e.release?.tag || "HEAD";
    const checkItems = checkKeys
      .map((k) => {
        const state = failed.includes(k) ? "bad" : unknown.includes(k) ? "mid" : "ok";
        const mark = state === "bad" ? svg("cross", "i bad") : state === "mid" ? svg("alert", "i mid") : svg("check", "i ok");
        return `<li>${mark}<span>${esc(t.check[k])}${state === "mid" ? ` (${esc(t.unknown)})` : ""}</span></li>`;
      })
      .join("");
    const flagItems = flags
      .map((f) => {
        const where = (f.where || [])
          .map((w) => {
            const m = /^(.*):(\d+)$/.exec(w);
            return m && !e.scan.asset
              ? `<a class="where" href="https://github.com/${esc(e.repo)}/blob/${esc(ref)}/${esc(m[1])}#L${m[2]}" target="_blank" rel="noopener">${esc(w)}</a>`
              : `<span class="where">${esc(w)}</span>`;
          })
          .join("");
        return `<li>${svg("alert", `i ${FLAG_ICON[f.severity]}`)}<span>${esc(t.flag[f.rule] || f.rule)}${f.hits > 1 ? ` ×${f.hits}` : ""}${where}</span></li>`;
      })
      .join("");
    const read = e.scan && !e.scan.error && e.scan.files > 0;
    const scanLine = !e.scan ? t.not_scanned : read ? t.scanned(e.scan.files, e.scan.skipped, e.scan.asset) : t.scan_error;
    const summary = `${t.checks(checkKeys.length - failed.length - unknown.length, checkKeys.length)} · ${scanLine}`;

    let action;
    if (this._mode === "panel") {
      if (known) {
        action = `<span class="state">${svg("check")}${esc(known.installed ? t.installed : t.added)}</span>
          <button type="button" class="btn" data-open="${index}">${esc(t.open_hacs)}</button>`;
      } else {
        const busy = this._busy.has(e.repo.toLowerCase());
        action = `<button type="button" class="btn primary" data-add="${index}" ${busy ? "disabled" : ""}>${svg("ha")}${esc(busy ? t.adding : t.add_hacs)}</button>`;
      }
    } else {
      action = `<button type="button" class="btn primary" data-add="${index}">${svg("ha")}${esc(t.open_hacs)}</button>`;
    }
    const report = this._reportUrl
      ? `<a class="link" href="${esc(this._reportUrl(e))}" target="_blank" rel="noopener">${esc(t.report)}</a>`
      : "";

    const head = inline
      ? ""
      : `<div class="head">
        <div class="icon" style="${e.icon ? "" : `background:${color}`}" data-letter="${esc(letter)}" data-color="${color}">${icon}</div>
        <div class="title">
          <div class="name">${esc(e.name)}</div>
          <div class="repo"><a href="https://github.com/${esc(e.repo)}" target="_blank" rel="noopener">${esc(owner)}/${esc(name)}</a></div>
        </div>
        <span class="cat">${esc(t.cat[e.category] || e.category)}</span>
      </div>`;
    return `<article class="card">${head}
      ${e.description ? `<p class="desc">${esc(e.description)}</p>` : ""}
      <div class="meta">${meta}</div>
      ${badges.length ? `<div class="badges">${badges.join("")}</div>` : ""}
      <details><summary>${esc(summary)}</summary>
        <ul>${checkItems}${flagItems}</ul>
      </details>
      <div class="actions">${action}
        <a class="link" href="https://github.com/${esc(e.repo)}" target="_blank" rel="noopener">${esc(t.github)}</a>
        ${report}
      </div>
    </article>`;
  }

  _onAction(ev) {
    const expand = ev.target.closest("[data-expand]");
    if (expand) {
      const key = this._visible[Number(expand.dataset.expand)].repo.toLowerCase();
      if (!this._expanded.delete(key)) this._expanded.add(key);
      this._renderList();
      this.shadowRoot.querySelector(`[data-expand="${expand.dataset.expand}"]`)?.focus();
      return;
    }
    const add = ev.target.closest("[data-add]");
    const open = ev.target.closest("[data-open]");
    if (open) {
      const e = this._visible[Number(open.dataset.open)];
      const known = this._known.get(e.repo.toLowerCase());
      this.dispatchEvent(new CustomEvent("bazaar-open", { detail: { entry: e, id: known?.id } }));
    } else if (add && !add.disabled) {
      this._confirm(this._visible[Number(add.dataset.add)]);
    }
  }

  _clashes(e) {
    const t = this.t;
    const out = [];
    if (e.conflicts.hacs) out.push(t.clash_hacs(e.conflicts.hacs));
    if (e.conflicts.core) out.push(t.clash_core(e.domain));
    return out;
  }

  _myLink(e) {
    const [owner, repository] = e.repo.split("/");
    const params = new URLSearchParams({ owner, repository, category: e.category });
    return `${MY_LINK}?${params}`;
  }

  _confirm(e) {
    const t = this.t;
    const dialog = this.shadowRoot.querySelector("dialog");
    const flags = e.scan?.flags || [];
    let found;
    if (!e.scan || e.scan.error || !e.scan.files) found = `<p>${esc(t.dialog_unscanned)}</p>`;
    else if (!flags.length && e.scan.skipped) found = `<p>${esc(t.dialog_partial(e.scan.skipped))}</p>`;
    else if (!flags.length) found = `<p>${esc(t.dialog_noflags)}</p>`;
    else
      found = `<h3>${esc(t.dialog_flags)}</h3><ul>${flags
        .map((f) => `<li>${svg("alert", `i ${FLAG_ICON[f.severity]}`)}<span>${esc(t.flag[f.rule] || f.rule)}</span></li>`)
        .join("")}</ul>`;
    const go =
      this._mode === "panel"
        ? `<button type="button" class="btn primary" data-go>${esc(t.dialog_go_panel)}</button>`
        : `<a class="btn primary" data-go href="${esc(this._myLink(e))}" target="_blank" rel="noopener">${esc(t.dialog_go_site)}</a>`;
    const clashes = this._clashes(e)
      .map((text) => `<li>${svg("alert", "i mid")}<span>${esc(text)}</span></li>`)
      .join("");
    dialog.innerHTML = `<form method="dialog" class="dlg">
      <h2>${esc(t.dialog_title(e.name))}</h2>
      <p>${esc(t.dialog_body)}</p>
      ${clashes ? `<ul>${clashes}</ul>` : ""}
      ${found}
      <div class="buttons">
        <button type="submit" class="btn" value="cancel">${esc(t.cancel)}</button>
        ${go}
      </div>
    </form>`;
    dialog.querySelector("[data-go]").addEventListener("click", () => {
      if (this._mode === "panel") this.dispatchEvent(new CustomEvent("bazaar-add", { detail: { entry: e } }));
      dialog.close();
    });
    dialog.showModal();
  }
}

if (!customElements.get("bazaar-catalog")) customElements.define("bazaar-catalog", BazaarCatalog);
