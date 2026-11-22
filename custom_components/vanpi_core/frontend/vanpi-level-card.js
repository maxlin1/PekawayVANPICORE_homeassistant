/* VAN PI CORE: Dosenlibelle (runde Wasserwaage) für die Nivellierung.
 *
 * type: custom:vanpi-level-card
 * entity_pitch: sensor.xxx_neigung_langs   (+ = vorne höher)
 * entity_roll:  sensor.xxx_neigung_quer    (+ = rechts höher)
 * tolerance: 1.0     # grüner Kreis in Grad
 * max_angle: 5       # Rand der Libelle in Grad
 *
 * Wie bei einer echten Libelle wandert die Blase zur höheren Seite.
 * Oben ist vorne, rechts ist rechts (Blick in Fahrtrichtung).
 */
class VanPiLevelCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity_pitch || !config.entity_roll) {
      throw new Error("entity_pitch und entity_roll angeben");
    }
    this._config = { tolerance: 1.0, max_angle: 5, ...config };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 5;
  }

  getGridOptions() {
    return { columns: 12, rows: 5, min_rows: 4 };
  }

  static getStubConfig() {
    return { entity_pitch: "", entity_roll: "", tolerance: 1.0, max_angle: 5 };
  }

  _render() {
    const c = this._config;
    const r = 90;
    const tolR = Math.min(r, (c.tolerance / c.max_angle) * r);
    const rings = [1, 2, 3, 4, 5, 10, 15]
      .filter((a) => a < c.max_angle && a !== c.tolerance)
      .map((a) => `<circle cx="100" cy="100" r="${(a / c.max_angle) * r}" class="ring"/>`)
      .join("");
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 16px; }
        .wrap { display: flex; align-items: center; gap: 20px; }
        svg { width: 100%; max-width: 240px; height: auto; flex: 0 0 auto; }
        .face { fill: var(--secondary-background-color, #222); stroke: var(--divider-color, #555); stroke-width: 2; }
        .ring { fill: none; stroke: var(--divider-color, #555); stroke-width: 1; stroke-dasharray: 3 4; }
        .cross { stroke: var(--divider-color, #555); stroke-width: 1; }
        .tol { fill: rgba(76,175,80,0.12); stroke: var(--success-color, #4caf50); stroke-width: 2; }
        .bubble { transition: transform 0.4s ease-out; }
        .bubble circle { stroke: rgba(255,255,255,0.7); stroke-width: 2; }
        .lbl { fill: var(--secondary-text-color, #aaa); font: 11px sans-serif; text-anchor: middle; }
        .vals { display: grid; gap: 10px; font-family: var(--ha-font-family-body, sans-serif); }
        .k { color: var(--secondary-text-color); font-size: 12px; }
        .v { font-size: 26px; font-weight: 600; color: var(--primary-text-color); }
        .hint { font-size: 12px; color: var(--secondary-text-color); }
        .off { opacity: 0.35; }
      </style>
      <ha-card>
        <div class="wrap">
          <svg viewBox="0 0 200 200" role="img" aria-label="Wasserwaage">
            <circle cx="100" cy="100" r="${r}" class="face"/>
            ${rings}
            <line x1="10" y1="100" x2="190" y2="100" class="cross"/>
            <line x1="100" y1="10" x2="100" y2="190" class="cross"/>
            <circle cx="100" cy="100" r="${tolR}" class="tol"/>
            <text x="100" y="24" class="lbl">vorne</text>
            <text x="100" y="186" class="lbl">hinten</text>
            <text x="22" y="104" class="lbl">L</text>
            <text x="178" y="104" class="lbl">R</text>
            <g class="bubble" id="bubble"><circle cx="100" cy="100" r="13" id="dot"/></g>
          </svg>
          <div class="vals">
            <div><div class="k">Längs</div><div class="v" id="p">–</div><div class="hint" id="ph"></div></div>
            <div><div class="k">Quer</div><div class="v" id="r">–</div><div class="hint" id="rh"></div></div>
          </div>
        </div>
      </ha-card>`;
    this._update();
  }

  _num(id) {
    const s = this._hass && this._hass.states[id];
    if (!s) return null;
    const v = parseFloat(s.state);
    return Number.isFinite(v) ? v : null;
  }

  _update() {
    if (!this.shadowRoot || !this._hass || !this._config) return;
    const c = this._config;
    const root = this.shadowRoot;
    const pitch = this._num(c.entity_pitch);
    const roll = this._num(c.entity_roll);
    const bubble = root.getElementById("bubble");
    const dot = root.getElementById("dot");
    if (!bubble) return;
    const fmt = (v) => (v === null ? "–" : `${v.toFixed(1).replace(".", ",")}°`);
    root.getElementById("p").textContent = fmt(pitch);
    root.getElementById("r").textContent = fmt(roll);
    root.getElementById("ph").textContent =
      pitch === null ? "" : Math.abs(pitch) <= c.tolerance ? "eben" : pitch > 0 ? "vorne höher" : "vorne tiefer";
    root.getElementById("rh").textContent =
      roll === null ? "" : Math.abs(roll) <= c.tolerance ? "eben" : roll > 0 ? "rechts höher" : "rechts tiefer";
    if (pitch === null || roll === null) {
      bubble.classList.add("off");
      bubble.setAttribute("transform", "translate(0 0)");
      dot.setAttribute("fill", "var(--disabled-color, #777)");
      return;
    }
    bubble.classList.remove("off");
    const r = 90 - 13;
    let x = (roll / c.max_angle) * 90;
    let y = (-pitch / c.max_angle) * 90; // vorne höher -> Blase nach oben
    const d = Math.hypot(x, y);
    if (d > r) {
      x = (x / d) * r;
      y = (y / d) * r;
    }
    bubble.setAttribute("transform", `translate(${x.toFixed(1)} ${y.toFixed(1)})`);
    const level = Math.hypot(pitch, roll) <= c.tolerance;
    dot.setAttribute("fill", level ? "var(--success-color, #4caf50)" : "var(--warning-color, #ff9800)");
  }
}

if (!customElements.get("vanpi-level-card")) {
  customElements.define("vanpi-level-card", VanPiLevelCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "vanpi-level-card",
    name: "VAN PI CORE Wasserwaage",
    description: "Runde Wasserwaage für die Nivellierung",
  });
}
