class HacsStubPanel extends HTMLElement {
  set route(route) {
    this.innerHTML = `<div style="padding:24px;font:16px system-ui;color:var(--primary-text-color)">
      <h1>HACS stub</h1><p>Route: <code id="route">${route.path}</code></p></div>`;
  }
  set hass(h) {}
}
customElements.define("hacs-stub-panel", HacsStubPanel);
