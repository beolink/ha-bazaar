// <bazaar-panel>: the sidebar page. Fetches the catalog from the integration,
// asks HACS what it already tracks, and adds a repository to HACS over HACS's
// own websocket commands, then opens it in HACS for the download.

const version = new URL(import.meta.url).search;
await import(new URL(`./bazaar-catalog.js${version}`, import.meta.url).href);

const TEXT = {
  en: {
    refresh: "Fetch the catalog again",
    built: (when, fetched) => `Catalog built ${when}, fetched ${fetched}.`,
    counts: (c) => `${c.total ?? 0} repositories, ${c.pending ?? 0} of them in the HACS queue.`,
    notice:
      "Nothing here has been reviewed by HACS. Adding a repository makes it a custom repository in HACS, which then installs and updates it.",
    no_hacs: "HACS is not set up in this Home Assistant. Bazaar adds repositories to HACS, so set up HACS first.",
    load_failed: (msg) => `The catalog could not be loaded: ${msg}`,
    stale: (msg) => `The latest fetch failed, so this is an older copy: ${msg}`,
    added: (name) => `${name} is in HACS now. Download it there.`,
    add_failed: (name) =>
      `HACS did not add ${name}. HACS's own log in Settings, System, Logs says why.`,
    loading: "Loading the catalog…",
  },
  sv: {
    refresh: "Hämta katalogen igen",
    built: (when, fetched) => `Katalogen byggd ${when}, hämtad ${fetched}.`,
    counts: (c) => `${c.total ?? 0} repon, varav ${c.pending ?? 0} i HACS-kön.`,
    notice:
      "Inget här är granskat av HACS. Ett repo som läggs till blir ett anpassat repo i HACS, som sedan installerar och uppdaterar det.",
    no_hacs: "HACS är inte uppsatt i den här Home Assistant. Bazaar lägger till repon i HACS, så sätt upp HACS först.",
    load_failed: (msg) => `Katalogen gick inte att ladda: ${msg}`,
    stale: (msg) => `Senaste hämtningen misslyckades, så det här är en äldre kopia: ${msg}`,
    added: (name) => `${name} finns nu i HACS. Ladda ner det där.`,
    add_failed: (name) =>
      `HACS lade inte till ${name}. HACS egen logg under Inställningar, System, Loggar säger varför.`,
    loading: "Laddar katalogen…",
  },
};

const REFRESH = "M17.65,6.35C16.2,4.9 14.21,4 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20C15.73,20 18.84,17.45 19.73,14H17.65C16.83,16.33 14.61,18 12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6C13.66,6 15.14,6.69 16.22,7.78L13,11H20V4L17.65,6.35Z";

const STYLE = `
:host { display: block; min-height: 100%; background: var(--primary-background-color); }
.toolbar {
  display: flex; align-items: center; gap: 4px;
  height: var(--header-height, 56px); padding: 0 12px 0 4px;
  background: var(--app-header-background-color, var(--primary-color));
  color: var(--app-header-text-color, var(--text-primary-color, #fff));
  border-bottom: var(--app-header-border-bottom, none);
  position: sticky; top: 0; z-index: 2;
  font-family: var(--ha-font-family-body, system-ui, sans-serif);
}
.title { flex: 1; font-size: 20px; font-weight: 400; margin-left: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.content { padding: 16px; max-width: 1400px; margin: 0 auto; box-sizing: border-box; }
.info { font-size: 14px; color: var(--secondary-text-color); margin: 0 0 12px; display: grid; gap: 2px; }
.box {
  display: flex; gap: 10px; align-items: flex-start;
  border-radius: 12px; padding: 12px 14px; margin: 0 0 16px;
  font-size: 14px; line-height: 1.45; color: var(--primary-text-color);
  background: color-mix(in srgb, var(--warning-color, #ffa600) 13%, var(--card-background-color, #fff));
  border: 1px solid color-mix(in srgb, var(--warning-color, #ffa600) 40%, transparent);
}
.box.error {
  background: color-mix(in srgb, var(--error-color, #db4437) 12%, var(--card-background-color, #fff));
  border-color: color-mix(in srgb, var(--error-color, #db4437) 40%, transparent);
}
.box svg { width: 20px; height: 20px; flex: none; fill: var(--warning-color, #ffa600); }
.box.error svg { fill: var(--error-color, #db4437); }
.loading { color: var(--secondary-text-color); padding: 32px 0; font-size: 15px; }
`;

const ALERT = "M13,14H11V10H13M13,18H11V16H13M1,21H23L12,2L1,21Z";

class BazaarPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._started = false;
    this._info = null;
    this._error = null;
    this._hacs = true;
    this._busy = new Set();
  }

  connectedCallback() {
    // Home Assistant may set these before this module has defined the element;
    // such values sit on the instance and hide the setters until moved.
    for (const name of ["panel", "narrow", "route", "hass"]) {
      if (Object.prototype.hasOwnProperty.call(this, name)) {
        const value = this[name];
        delete this[name];
        this[name] = value;
      }
    }
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._build();
    if (this._menu) this._menu.hass = hass;
    if (!this._started) {
      this._started = true;
      this._load();
    }
  }

  set narrow(value) {
    this._narrow = value;
    if (this._menu) this._menu.narrow = value;
  }

  set panel(value) {
    this._panel = value;
  }

  set route(value) {
    this._route = value;
  }

  get _lang() {
    return String(this._hass?.locale?.language || this._hass?.language || "en").toLowerCase().startsWith("sv")
      ? "sv"
      : "en";
  }

  get t() {
    return TEXT[this._lang];
  }

  _build() {
    const t = this.t;
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <div class="toolbar">
        <ha-menu-button></ha-menu-button>
        <div class="title">Bazaar</div>
        <ha-icon-button class="refresh"></ha-icon-button>
      </div>
      <div class="content">
        <div class="info"></div>
        <div class="boxes"></div>
        <div class="loading">${t.loading}</div>
        <bazaar-catalog></bazaar-catalog>
      </div>`;
    this._menu = this.shadowRoot.querySelector("ha-menu-button");
    this._menu.hass = this._hass;
    this._menu.narrow = this._narrow;
    const refresh = this.shadowRoot.querySelector(".refresh");
    refresh.path = REFRESH;
    refresh.label = t.refresh;
    refresh.addEventListener("click", () => this._refresh());
    this._catalogEl = this.shadowRoot.querySelector("bazaar-catalog");
    this._catalogEl.mode = "panel";
    this._catalogEl.reportUrl = (entry) =>
      `https://github.com/beolink/ha-bazaar/issues/new?${new URLSearchParams({
        title: `Report: ${entry.repo}`,
        labels: "report",
        body: `Repository: https://github.com/${entry.repo}\n\nWhat is wrong with it:\n`,
      })}`;
    this._catalogEl.lang = this._lang;
    this._catalogEl.addEventListener("bazaar-add", (ev) => this._add(ev.detail.entry));
    this._catalogEl.addEventListener("bazaar-open", (ev) => this._open(ev.detail.id));
  }

  async _load() {
    try {
      this._info = await this._hass.callWS({ type: "bazaar/info" });
      const response = await this._hass.fetchWithAuth("/api/bazaar/catalog");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const catalog = await response.json();
      await this._loadKnown();
      this._catalogEl.catalog = catalog;
      this._error = null;
    } catch (err) {
      this._error = this.t.load_failed(err?.message || String(err));
    }
    this.shadowRoot.querySelector(".loading")?.remove();
    this._renderInfo();
  }

  async _refresh() {
    try {
      this._info = await this._hass.callWS({ type: "bazaar/refresh" });
    } catch (err) {
      this._error = this.t.load_failed(err?.message || String(err));
      this._renderInfo();
      return;
    }
    await this._load();
  }

  async _loadKnown() {
    try {
      const repos = await this._hass.callWS({ type: "hacs/repositories/list" });
      this._hacs = true;
      this._known = new Map(repos.map((r) => [String(r.full_name).toLowerCase(), r]));
    } catch (err) {
      // unknown_command: HACS is not loaded. Anything else: treat the same, as
      // adding would fail the same way.
      this._hacs = false;
      this._known = new Map();
    }
    this._catalogEl.known = this._known;
  }

  _renderInfo() {
    const t = this.t;
    const info = this._info;
    const esc = (text) =>
      String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
    const fmt = (v) => {
      const when = new Date(v);
      return v && !Number.isNaN(when.getTime())
        ? new Intl.DateTimeFormat(this._lang, { dateStyle: "medium", timeStyle: "short" }).format(when)
        : "?";
    };
    const counts = {
      total: Number(info?.counts?.total) || 0,
      pending: Number(info?.counts?.pending) || 0,
    };
    this.shadowRoot.querySelector(".info").innerHTML = info?.generated
      ? `<span>${esc(`${t.built(fmt(info.generated), fmt(info.fetched))} ${t.counts(counts)}`)}</span>`
      : "";
    const boxes = [];
    const box = (text, error = false) =>
      `<div class="box${error ? " error" : ""}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="${ALERT}"/></svg><span>${esc(text)}</span></div>`;
    if (this._error) boxes.push(box(this._error, true));
    else if (info && !info.last_update_success && info.error) boxes.push(box(t.stale(info.error), true));
    if (!this._hacs) boxes.push(box(t.no_hacs, true));
    boxes.push(box(t.notice));
    this.shadowRoot.querySelector(".boxes").innerHTML = boxes.join("");
  }

  _toast(message) {
    this.dispatchEvent(
      new CustomEvent("hass-notification", { detail: { message }, bubbles: true, composed: true }),
    );
  }

  _navigate(path) {
    history.pushState(null, "", path);
    window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
  }

  _open(id) {
    if (id !== undefined && id !== null) this._navigate(`/hacs/repository/${id}`);
  }

  async _add(entry) {
    const key = entry.repo.toLowerCase();
    if (!this._hacs) {
      this._toast(this.t.no_hacs);
      return;
    }
    this._busy.add(key);
    this._catalogEl.busy = this._busy;
    let found;
    try {
      await this._hass.callWS({ type: "hacs/repositories/add", repository: entry.repo, category: entry.category });
      // HACS answers before an error reaches its log, and lists a repository
      // only once it has been fetched, so look a few times.
      for (let attempt = 0; attempt < 5 && !found; attempt++) {
        await this._loadKnown();
        found = this._known.get(key);
        if (!found) await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    } catch (err) {
      found = undefined;
    }
    this._busy.delete(key);
    this._catalogEl.busy = this._busy;
    if (found) {
      this._toast(this.t.added(entry.name));
      this._open(found.id);
    } else {
      this._toast(this.t.add_failed(entry.name));
    }
  }
}

if (!customElements.get("bazaar-panel")) customElements.define("bazaar-panel", BazaarPanel);
