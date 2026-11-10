// <bazaar-panel>: the sidebar page. Fetches the catalog from the integration,
// asks the store what it already tracks, and adds a repository over the store's
// own websocket commands, then opens it there for the download. The store is
// the Marketplace built into Home Assistant since 2026.11, or HACS before it.

const version = new URL(import.meta.url).search;
await import(new URL(`./bazaar-catalog.js${version}`, import.meta.url).href);

// The Marketplace first: an upgraded Home Assistant has handed HACS's entry to it.
const STORES = {
  marketplace: {
    list: "marketplace/repositories/list",
    add: "marketplace/repositories/add",
    page: "/marketplace/repository/",
  },
  hacs: {
    list: "hacs/repositories/list",
    add: "hacs/repositories/add",
    page: "/hacs/repository/",
  },
};

const TEXT = {
  en: {
    refresh: "Fetch the catalog again",
    built: (when, fetched) => `Catalog built ${when}, fetched ${fetched}.`,
    counts: (c) => `${c.total ?? 0} repositories, ${c.pending ?? 0} of them in the HACS queue.`,
    stores: { hacs: "HACS", marketplace: "the Marketplace" },
    notice: (store) =>
      `Nothing here has been reviewed by HACS. Adding a repository makes it a custom repository in ${store}, which then installs and updates it.`,
    no_store:
      "Neither the Marketplace nor HACS is running in this Home Assistant. Bazaar adds repositories to one of them, so set it up first.",
    store_down: (store, msg) => `Bazaar cannot reach ${store}: ${msg}`,
    mp_warning: "Open the Marketplace and accept its warning before adding a repository.",
    mp_github: "Connect a GitHub account in the Marketplace before adding a repository.",
    open_store: "Open the Marketplace",
    load_failed: (msg) => `The catalog could not be loaded: ${msg}`,
    stale: (msg) => `The latest fetch failed, so this is an older copy: ${msg}`,
    added: (name, store) => `${name} is in ${store} now. Download it there.`,
    add_failed: (name, store) => `${store} did not add ${name}. Its log in Settings, System, Logs says why.`,
    add_refused: (name, msg) => `${name} was not added: ${msg}`,
    loading: "Loading the catalog…",
  },
  sv: {
    refresh: "Hämta katalogen igen",
    built: (when, fetched) => `Katalogen byggd ${when}, hämtad ${fetched}.`,
    counts: (c) => `${c.total ?? 0} repon, varav ${c.pending ?? 0} i HACS-kön.`,
    stores: { hacs: "HACS", marketplace: "Marknadsplatsen" },
    notice: (store) =>
      `Inget här är granskat av HACS. Ett repo som läggs till blir ett anpassat repo i ${store}, som sedan installerar och uppdaterar det.`,
    no_store:
      "Varken Marknadsplatsen eller HACS är igång i den här Home Assistant. Bazaar lägger till repon i någon av dem, så sätt upp den först.",
    store_down: (store, msg) => `Bazaar når inte ${store}: ${msg}`,
    mp_warning: "Öppna Marknadsplatsen och godkänn dess varning innan du lägger till ett repo.",
    mp_github: "Anslut ett GitHub-konto i Marknadsplatsen innan du lägger till ett repo.",
    open_store: "Öppna Marknadsplatsen",
    load_failed: (msg) => `Katalogen gick inte att ladda: ${msg}`,
    stale: (msg) => `Senaste hämtningen misslyckades, så det här är en äldre kopia: ${msg}`,
    added: (name, store) => `${name} finns nu i ${store}. Ladda ner det där.`,
    add_failed: (name, store) => `${store} lade inte till ${name}. Loggen under Inställningar, System, Loggar säger varför.`,
    add_refused: (name, msg) => `${name} lades inte till: ${msg}`,
    loading: "Laddar katalogen…",
  },
};

const capital = (text) => `${text.charAt(0).toUpperCase()}${text.slice(1)}`;

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
.box button {
  font: inherit; font-size: 14px; margin-left: auto; flex: none; cursor: pointer;
  padding: 4px 10px; border-radius: 8px;
  border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.2)); background: var(--card-background-color, #fff);
  color: var(--primary-text-color);
}
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
    this._store = null;
    this._storeDown = null;
    this._marketplace = null;
    this._known = new Map();
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

  get _storeName() {
    return this.t.stores[this._store || "hacs"];
  }

  // Which store answers, and what it already tracks. A store whose commands
  // exist but fail is named with its reason rather than passed over.
  async _loadKnown() {
    this._store = null;
    this._storeDown = null;
    this._known = new Map();
    for (const [key, store] of Object.entries(STORES)) {
      try {
        const repos = await this._hass.callWS({ type: store.list });
        this._store = key;
        this._known = new Map(repos.map((r) => [String(r.full_name).toLowerCase(), r]));
        break;
      } catch (err) {
        if (err?.code === "unknown_command") continue;
        this._store = key;
        this._storeDown = err?.message || String(err?.code || err);
        break;
      }
    }
    this._marketplace = null;
    if (this._store === "marketplace" && !this._storeDown) {
      try {
        this._marketplace = await this._hass.callWS({ type: "marketplace/info" });
      } catch {
        // Adding still answers with its own reason.
      }
    }
    this._catalogEl.store = this._store || "hacs";
    this._catalogEl.addable = Array.isArray(this._marketplace?.categories) ? this._marketplace.categories : null;
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
    const box = (text, error = false, extra = "") =>
      `<div class="box${error ? " error" : ""}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="${ALERT}"/></svg><span>${esc(text)}</span>${extra}</div>`;
    const open = `<button type="button" data-open-store>${esc(t.open_store)}</button>`;
    if (this._error) boxes.push(box(this._error, true));
    else if (info && !info.last_update_success && info.error) boxes.push(box(t.stale(info.error), true));
    if (!this._store) boxes.push(box(t.no_store, true));
    else if (this._storeDown) boxes.push(box(t.store_down(this._storeName, this._storeDown), true));
    else if (this._marketplace?.warning_accepted === false) boxes.push(box(t.mp_warning, true, open));
    else if (this._marketplace?.github_connected === false) boxes.push(box(t.mp_github, true, open));
    boxes.push(box(t.notice(this._storeName)));
    const holder = this.shadowRoot.querySelector(".boxes");
    holder.innerHTML = boxes.join("");
    holder.querySelector("[data-open-store]")?.addEventListener("click", () => this._navigate("/marketplace"));
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
    if (id !== undefined && id !== null) this._navigate(`${STORES[this._store || "hacs"].page}${encodeURIComponent(id)}`);
  }

  async _add(entry) {
    const t = this.t;
    const key = entry.repo.toLowerCase();
    if (!this._store || this._storeDown) {
      this._toast(this._store ? t.store_down(this._storeName, this._storeDown) : t.no_store);
      return;
    }
    const store = this._storeName;
    this._busy.add(key);
    this._catalogEl.busy = this._busy;
    let found;
    let refused;
    try {
      await this._hass.callWS({ type: STORES[this._store].add, repository: entry.repo, category: entry.category });
      // HACS answers before an error reaches its log, and both list a
      // repository only once it has been fetched, so look a few times.
      for (let attempt = 0; attempt < 5 && !found; attempt++) {
        await this._loadKnown();
        found = this._known.get(key);
        if (!found) await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    } catch (err) {
      // The Marketplace says why, in the language of Home Assistant.
      refused = err?.message;
    }
    this._busy.delete(key);
    this._catalogEl.busy = this._busy;
    this._renderInfo();
    if (found) {
      this._toast(t.added(entry.name, store));
      this._open(found.id);
    } else if (refused) {
      this._toast(t.add_refused(entry.name, refused));
    } else {
      this._toast(t.add_failed(entry.name, capital(store)));
    }
  }
}

if (!customElements.get("bazaar-panel")) customElements.define("bazaar-panel", BazaarPanel);
