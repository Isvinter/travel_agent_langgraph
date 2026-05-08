# Tab-Redesign: Linkes Ausgabefenster

**Datum:** 2026-05-07
**Status:** approved
**Betrifft:** `frontend/src/App.svelte` (Template + `<style>`-Block)

## Ziel

Die beiden Tab-Ebenen im rechten Content-Panel visuell unterscheidbar machen und ihre Hierarchie verdeutlichen:

- **Ebene 1** (Pipeline / Datenbank): Navigation auf oberster Ebene — schaltet den gesamten Panel-Inhalt um.
- **Ebene 2** (Blogartikel / Fotobücher): Unterauswahl — nur innerhalb "Datenbank" sichtbar, bezieht sich auf den darunter liegenden Inhalt.

## Ebene 1: Tabs auf Linie

Pipeline und Datenbank erhalten kein Button-Styling mehr. Stattdessen eine durchgehende horizontale Trennlinie, auf der die Tabs "stehen".

### HTML-Änderung

`<nav class="right-tabs">` wird ersetzt durch:

```svelte
<div class="top-tab-bar">
  <div class="top-tab-bar-line"></div>
  <button class="top-tab" class:active={rightTab === "pipeline"} ...>Pipeline</button>
  <button class="top-tab" class:active={rightTab === "datenbank"} ...>Datenbank</button>
  <div class="top-tab-bar-spacer"></div>
  <!-- Theme-Toggle unverändert -->
</div>
```

### CSS

```css
.top-tab-bar {
  position: relative;
  display: flex;
  gap: 1.5rem;
  align-items: flex-end;
  margin-bottom: 1.25rem;
  flex-shrink: 0;
}
.top-tab-bar-line {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: var(--border);
}
.top-tab {
  position: relative;
  padding: 0 0 10px 0;
  background: none;
  border: none;
  border-radius: 0;
  color: var(--text-secondary);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
}
.top-tab.active {
  color: var(--text-primary);
  font-weight: 600;
}
.top-tab.active::after {
  content: "";
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--accent);
  border-radius: 1px 1px 0 0;
}
.top-tab:hover:not(.active) {
  color: var(--text-primary);
}
.top-tab-bar-spacer {
  flex: 1;
}
```

- **Kein Hintergrund** auf den Tab-Buttons.
- **Kein Border** auf den Tab-Buttons.
- Die Linie (`top-tab-bar-line`) liegt `absolute` am unteren Rand des Containers.
- Die aktive Unterstreichung wird via `::after`-Pseudoelement realisiert und schließt bündig mit der Linie ab (`bottom: 0`).
- Hover auf inaktivem Tab: Nur Textfarbe wechselt von `--text-secondary` → `--text-primary`.
- `gap: 1.5rem` zwischen den Tabs (statt 0.25rem bisher).

### Theme-Toggle

Bleibt im gleichen Container. Ein `div.top-tab-bar-spacer` mit `flex: 1` schiebt den Toggle nach rechts. Der Toggle selbst behält sein bisheriges Styling (`.theme-toggle`).

## Ebene 2: Segmented Control (Pillen-Design)

Nur sichtbar, wenn `rightTab === "datenbank"`. Ein abgerundeter dunkler Container mit zwei inneren "Pillen".

### HTML-Änderung

```svelte
{#if rightTab === "datenbank"}
  <div class="segmented-control">
    <button class="segment" class:active={dbSubTab === "articles"} ...>Blogartikel</button>
    <button class="segment" class:active={dbSubTab === "photobooks"} ...>Fotobücher</button>
  </div>
{/if}
```

### CSS

```css
.segmented-control {
  display: inline-flex;
  background: var(--panel-2);
  border-radius: var(--radius);
  padding: 3px;
  margin-bottom: 0.5rem;
  flex-shrink: 0;
}
.segment {
  padding: 5px 16px;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
}
.segment.active {
  background: var(--panel);
  color: var(--text-primary);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
}
.segment:hover:not(.active) {
  color: var(--text-primary);
}
```

- **Container:** `display: inline-flex` — nur so breit wie der Inhalt. `--panel-2` als Hintergrund.
- **Aktives Segment:** `--panel` Hintergrund (im Dark-Theme dunkel, im Light-Theme weiß), `box-shadow` für Tiefe, dunkler Text.
- **Inaktives Segment:** Transparent, `--text-secondary` Text. Hover hellt Text auf.
- **margin-bottom: 0.5rem (~8px)** — enger Abstand zum Inhaltscontainer, visuelle Nähe zum Titel "Gespeicherte Artikel".

## Light-Theme-Verhalten

Alle Farben nutzen CSS-Variablen, die bereits in `app.css` für beide Themes definiert sind. Keine zusätzlichen Theme-spezifischen Regeln nötig:

- `--border` wechselt von `#232836` (dark) → `#E6E8EC` (light)
- `--text-primary` wechselt von `#E6EAF2` → `#1F2937`
- `--text-secondary` wechselt von `#9AA3B2` → `#6B7280`
- `--panel` wechselt von `#151922` → `#FFFFFF`
- `--panel-2` wechselt von `#1A1F2B` → `#F1F3F6`
- `--accent` wechselt von `#5B8CFF` → `#4F46E5`

## Keine Logik-Änderungen

TypeScript (`<script>`-Block) bleibt unverändert. Die State-Logik (`rightTab`, `dbSubTab`, `switchRightTab`, `switchDbSubTab`, `$effect`) wird nicht angetastet.

## Umfang

Nur `frontend/src/App.svelte` wird geändert:
- Template: `nav.right-tabs` → `div.top-tab-bar`, `div.sub-tabs` → `div.segmented-control`
- `<style>`: Neue CSS-Klassen, alte entfernt

Keine anderen Dateien betroffen.
