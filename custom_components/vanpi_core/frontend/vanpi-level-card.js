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
    // Richtung immer nennen; "eben" nur, wenn wirklich nichts zu sehen ist.
    // Innerhalb der Toleranz kommt "(in Toleranz)" dazu.
    const hint = (v, pos, neg) => {
      if (v === null) return "";
      if (Math.abs(v) < 0.05) return "eben";
      const dir = v > 0 ? pos : neg;
      return Math.abs(v) <= c.tolerance ? `${dir} (in Toleranz)` : dir;
    };
    root.getElementById("ph").textContent = hint(pitch, "vorne höher", "vorne tiefer");
    root.getElementById("rh").textContent = hint(roll, "rechts höher", "rechts tiefer");
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

/* VAN PI CORE: Draufsicht mit Blöcken je Rad.
 *
 * type: custom:vanpi-van-card
 * entity: sensor.xxx_blockempfehlung
 * image: /local/van_top.png   # optional: eigenes Foto von oben, vorne = oben im Bild
 *
 * Ohne Bild wird ein schlichter Van gezeichnet. Ein eigenes Bild legt man
 * unter /config/www/ ab und gibt es hier als /local/<dateiname> an.
 */
class VanPiVanCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) throw new Error("entity (Blockempfehlung) angeben");
    this._config = config;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 7;
  }

  getGridOptions() {
    return { columns: 12, rows: 7, min_rows: 5 };
  }

  static getStubConfig() {
    return { entity: "" };
  }

  _render() {
    const img = this._config.image
      ? `<img class="van" src="${this._config.image}" alt="Van von oben">`
      : `<svg class="van" viewBox="0 0 120 260" aria-hidden="true">
           <rect x="8" y="6" width="104" height="248" rx="34" class="body"/>
           <rect x="18" y="40" width="84" height="38" rx="10" class="glass"/>
           <rect x="18" y="232" width="84" height="12" rx="4" class="glass"/>
           <rect x="0" y="52" width="10" height="34" rx="4" class="tyre"/>
           <rect x="110" y="52" width="10" height="34" rx="4" class="tyre"/>
           <rect x="0" y="190" width="10" height="34" rx="4" class="tyre"/>
           <rect x="110" y="190" width="10" height="34" rx="4" class="tyre"/>
         </svg>`;
    const wheel = (id) => `
      <div class="w ${id}" id="${id}">
        <div class="ic" id="${id}-ic">–</div>
        <div><div class="n" id="${id}-n">–</div><div class="s" id="${id}-s"></div></div>
      </div>`;
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 12px; }
        .stage { position: relative; height: 340px; display: flex; justify-content: center; align-items: center; }
        .van { height: 92%; max-width: 46%; object-fit: contain; }
        svg .body { fill: var(--secondary-background-color, #2a2d33); stroke: var(--divider-color, #555); stroke-width: 2; }
        svg .glass { fill: var(--divider-color, #555); opacity: 0.6; }
        svg .tyre { fill: var(--primary-text-color, #ddd); opacity: 0.7; }
        .front { position: absolute; top: 0; left: 50%; transform: translateX(-50%); font-size: 12px; color: var(--secondary-text-color); }
        .w { position: absolute; display: flex; gap: 8px; align-items: center; min-width: 118px;
             padding: 6px 10px; border-radius: 12px; background: var(--card-background-color, #1c1c1c);
             border: 1px solid var(--divider-color, #444); font-family: var(--ha-font-family-body, sans-serif); }
        .vl { top: 14%; left: 2%; } .vr { top: 14%; right: 2%; }
        .hl { bottom: 8%; left: 2%; } .hr { bottom: 8%; right: 2%; }
        .ic { width: 26px; height: 26px; border-radius: 7px; display: flex; align-items: center; justify-content: center;
              font-weight: 700; font-size: 15px; background: var(--disabled-color, #666); color: #000; }
        .ic.ok { background: var(--success-color, #4caf50); }
        .ic.do { background: var(--warning-color, #ff9800); }
        .n { font-weight: 600; color: var(--primary-text-color); }
        .s { font-size: 12px; color: var(--secondary-text-color); }
        .center { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); padding: 8px 14px;
                  border-radius: 12px; background: var(--card-background-color, #1c1c1c); border: 1px solid var(--divider-color, #444);
                  font-weight: 600; color: var(--primary-text-color); display: none; text-align: center; }
        .center.show { display: block; }
      </style>
      <ha-card>
        <div class="stage">
          <div class="front">▲ vorne</div>
          ${img}
          ${wheel("vl")}${wheel("vr")}${wheel("hl")}${wheel("hr")}
          <div class="center" id="center"></div>
        </div>
      </ha-card>`;
    this._update();
  }

  _update() {
    if (!this.shadowRoot || !this._hass || !this._config) return;
    const root = this.shadowRoot;
    const st = this._hass.states[this._config.entity];
    const center = root.getElementById("center");
    if (!center) return;
    const off = !st || st.state === "unavailable" || st.state === "unknown";
    const a = (st && st.attributes) || {};
    const blocks = a.bloecke || {};
    const lift = a.hubhoehe_cm || {};
    const air = a.luftfederung_cm || {};
    const bh = a.blockhoehe_cm || 0;
    const fmt = (v) => String(v.toFixed(1)).replace(".", ",");
    for (const w of ["vl", "vr", "hl", "hr"]) {
      const ic = root.getElementById(`${w}-ic`);
      const n = blocks[w];
      ic.className = "ic" + (off ? "" : n ? " do" : " ok");
      ic.textContent = off ? "–" : n ? String(n) : "✓";
      root.getElementById(`${w}-n`).textContent = off
        ? "–"
        : `${n || 0} ${n === 1 ? "Block" : "Blöcke"}${n ? ` (${fmt(n * bh)} cm)` : ""}`;
      let sub = off || !(lift[w] >= 0.05) ? "" : `fehlt ${fmt(lift[w])} cm`;
      if (!off && air[w] !== undefined && Math.abs(air[w]) >= 0.05) {
        sub += `${sub ? " · " : ""}Luft ${air[w] > 0 ? "+" : ""}${fmt(air[w])} cm`;
      }
      root.getElementById(`${w}-s`).textContent = sub;
    }
    if (off) {
      center.textContent = "Aus";
      center.classList.add("show");
    } else if (st.state === "Keine Blöcke nötig") {
      center.textContent = "EBEN";
      center.classList.add("show");
    } else {
      center.classList.remove("show");
    }
  }
}

if (!customElements.get("vanpi-van-card")) {
  customElements.define("vanpi-van-card", VanPiVanCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "vanpi-van-card",
    name: "VAN PI CORE Draufsicht",
    description: "Van von oben mit Blöcken je Rad",
  });
}

/* VAN PI CORE: Fahrzeuglage als gekippter Van, seitlich und von hinten.
 *
 * type: custom:vanpi-tilt-card
 * entity_pitch: sensor.xxx_neigung_langs   (+ = vorne höher)
 * entity_roll:  sensor.xxx_neigung_quer    (+ = rechts höher)
 * tolerance: 1.0     # Bodenlinie grün, solange beide Winkel darunter liegen
 * exaggerate: 3      # Neigung im Bild verstärken, damit 1° sichtbar ist
 *
 * Seitenansicht: vorne ist rechts. Heckansicht: Blick von hinten, rechts ist rechts.
 */
class VanPiTiltCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity_pitch || !config.entity_roll) {
      throw new Error("entity_pitch und entity_roll angeben");
    }
    this._config = { tolerance: 1.0, exaggerate: 3, ...config };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return { columns: 12, rows: 6, min_rows: 5 };
  }

  static getStubConfig() {
    return { entity_pitch: "", entity_roll: "", tolerance: 1.0 };
  }

  _view(id, van, label) {
    return `
      <div class="view">
        <svg viewBox="0 0 240 120" role="img" aria-label="${label}">
          <line x1="10" y1="100" x2="230" y2="100" class="ref"/>
          <g id="${id}" class="tilt">
            <line x1="-110" y1="0" x2="110" y2="0" class="ground" id="${id}g"/>
            ${van}
          </g>
        </svg>
        <div class="v" id="${id}v">–</div>
        <div class="hint" id="${id}h"></div>
      </div>`;
  }

  _render() {
    // Eigene, einfache Silhouetten (Kastenwagen), Räder stehen auf y = 0.
    const side = `
      <path class="body" d="M-66,-10 L-66,-58 Q-66,-62 -62,-62 L26,-62 Q30,-62 33,-59 L50,-38
        L64,-32 Q68,-30 68,-25 L68,-10 Z"/>
      <path class="glass" d="M30,-56 L46,-38 L30,-38 Z"/>
      <rect class="glass" x="-52" y="-52" width="22" height="13" rx="2"/>
      <rect class="glass" x="-24" y="-52" width="22" height="13" rx="2"/>
      <rect class="glass" x="4" y="-52" width="20" height="13" rx="2"/>
      <circle class="wheel" cx="-40" cy="-9" r="9"/><circle class="hub" cx="-40" cy="-9" r="3.5"/>
      <circle class="wheel" cx="44" cy="-9" r="9"/><circle class="hub" cx="44" cy="-9" r="3.5"/>`;
    const rear = `
      <path class="body" d="M-38,-12 L-40,-60 Q-40,-66 -34,-66 L34,-66 Q40,-66 40,-60 L38,-12 Z"/>
      <rect class="glass" x="-28" y="-58" width="56" height="18" rx="3"/>
      <rect class="lamp" x="-37" y="-36" width="5" height="12" rx="1"/>
      <rect class="lamp" x="32" y="-36" width="5" height="12" rx="1"/>
      <rect class="wheel" x="-34" y="-14" width="13" height="14" rx="3"/>
      <rect class="wheel" x="21" y="-14" width="13" height="14" rx="3"/>`;
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 16px; }
        .wrap { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
        .view { text-align: center; font-family: var(--ha-font-family-body, sans-serif); }
        svg { width: 100%; max-width: 280px; height: auto; display: block; margin: 0 auto; overflow: visible; }
        .tilt { transition: transform 0.5s ease-out; }
        .ref { stroke: var(--divider-color, #888); stroke-width: 1; stroke-dasharray: 4 4; }
        .ground { stroke-width: 3; stroke-linecap: round; stroke: var(--warning-color, #ff9800); }
        .ground.ok { stroke: var(--success-color, #4caf50); }
        .body { fill: var(--primary-text-color, #222); }
        .glass { fill: var(--card-background-color, #fff); opacity: 0.9; }
        .lamp { fill: var(--card-background-color, #fff); opacity: 0.7; }
        .wheel { fill: var(--primary-text-color, #222); stroke: var(--card-background-color, #fff); stroke-width: 2; }
        .hub { fill: var(--card-background-color, #fff); }
        .v { font-size: 26px; font-weight: 600; color: var(--primary-text-color); margin-top: 4px; }
        .hint { font-size: 13px; color: var(--secondary-text-color); }
        .off { opacity: 0.35; }
      </style>
      <ha-card>
        <div class="wrap">
          ${this._view("side", side, "Seitenansicht, vorne rechts")}
          ${this._view("rear", rear, "Heckansicht")}
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

  _set(id, angle, pos, neg) {
    const c = this._config;
    const root = this.shadowRoot;
    const g = root.getElementById(id);
    const ground = root.getElementById(`${id}g`);
    if (!g) return;
    if (angle === null) {
      g.classList.add("off");
      g.setAttribute("transform", "translate(120 100)");
      root.getElementById(`${id}v`).textContent = "–";
      root.getElementById(`${id}h`).textContent = "";
      return;
    }
    g.classList.remove("off");
    const shown = Math.max(-20, Math.min(20, angle * c.exaggerate));
    // SVG dreht im Uhrzeigersinn: höhere rechte Seite = negative Drehung
    g.setAttribute("transform", `translate(120 100) rotate(${-shown})`);
    ground.classList.toggle("ok", Math.abs(angle) <= c.tolerance);
    root.getElementById(`${id}v`).textContent = `${angle.toFixed(1).replace(".", ",")}°`;
    const dir = Math.abs(angle) < 0.05 ? "eben" : angle > 0 ? pos : neg;
    root.getElementById(`${id}h`).textContent = dir;
  }

  _update() {
    if (!this.shadowRoot || !this._hass || !this._config) return;
    const c = this._config;
    this._set("side", this._num(c.entity_pitch), "vorne höher", "vorne tiefer");
    this._set("rear", this._num(c.entity_roll), "rechts höher", "rechts tiefer");
  }
}

if (!customElements.get("vanpi-tilt-card")) {
  customElements.define("vanpi-tilt-card", VanPiTiltCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "vanpi-tilt-card",
    name: "VAN PI CORE Fahrzeuglage",
    description: "Van seitlich und von hinten, gekippt um Längs- und Querneigung.",
  });
}
