# Frontend: Scroll-Verhalten und Sortierung in Listenansichten

**Datum:** 2026-05-07
**Betroffene Komponenten:** `ArticleList.svelte`, `PhotobookList.svelte`

## Ziel

1. **Scroll-Verhalten**: Nur die Tabellen-Einträge scrollen. Alles oberhalb inklusive der Spaltentitel bleibt fixiert.
2. **Sortierung**: Einträge lassen sich durch Klick auf Spaltentitel sortieren. Erster Klick sortiert absteigend, jeder weitere Klick toggled zwischen auf- und absteigend.

## Betroffene Komponenten

Beide Komponenten sind nahezu identisch aufgebaut und erhalten dieselben Änderungen:

| Komponente | Pfad |
|---|---|
| ArticleList | `frontend/src/lib/ArticleList.svelte` |
| PhotobookList | `frontend/src/lib/PhotobookList.svelte` |

## Scroll-Verhalten

### Vorher

```css
.article-list {
  height: 100%;
  overflow-y: auto;   /* gesamter Container scrollt */
}
```

Header, Filter, Spaltentitel und Datenzeilen scrollen gemeinsam.

### Nachher

Flexbox-Layout mit drei fixierten Zonen + scrollbarem Tabellenbereich:

```
┌──────────────────────────────────┐
│ Header (fix)                     │
├──────────────────────────────────┤
│ Filter-Leiste (fix)              │
├──────────────────────────────────┤
│ Tabellenkopf (sticky, top: 0)    │
├──────────────────────────────────┤
│ Zeile 1  ─┐                      │
│ Zeile 2   │ scrollbar            │
│ ...       │                      │
│ Zeile N  ─┘                      │
└──────────────────────────────────┘
```

### CSS-Änderungen

```css
/* Container: kein eigenes Overflow, Flex-Column */
.article-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 1rem;
  /* overflow-y: auto; ENTFERNT */
}

/* Neuer Wrapper um die Tabelle */
.table-scroll-wrapper {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

/* Thead sticky im Scroll-Container */
th {
  position: sticky;
  top: 0;
  background: var(--panel);
  z-index: 1;
}
```

`.table-container` bleibt unverändert (kümmert sich um horizontales Scrollen).

### Template-Änderung

```svelte
<!-- Nur der {:else}-Zweig (Daten vorhanden) ändert sich: -->
<div class="table-scroll-wrapper">
  <div class="table-container">
    <table>
      <!-- ... unverändert ... -->
    </table>
  </div>
</div>
```

Status-Meldungen (Lade/Fehler/Leer) bleiben direkte Kinder des Flex-Containers, ausserhalb des Scroll-Wrappers.

## Sortierung

### Ansatz

Client-seitig: die bereits vom Server geladenen Daten werden im Browser sortiert. Kein API-Umbau nötig.

### State

```typescript
let sortColumn: string | null = $state(null);
let sortDirection: 'asc' | 'desc' = $state('asc');
```

### Sortierte Liste ($derived)

```typescript
let displayedArticles = $derived(
  sortColumn
    ? [...articles].sort((a, b) => {
        let va = (a as any)[sortColumn];
        let vb = (b as any)[sortColumn];
        if (va == null) return 1;
        if (vb == null) return -1;
        const cmp = typeof va === 'string'
          ? va.localeCompare(String(vb))
          : Number(va) - Number(vb);
        return sortDirection === 'desc' ? -cmp : cmp;
      })
    : articles
);
```

- Null-Werte landen immer am Ende (unabhängig von Sortierrichtung).
- String-Felder werden mit `localeCompare` sortiert, numerische Felder per Subtraktion.
- Richtungsumkehr erfolgt über Vorzeichenwechsel des Vergleichsergebnisses.

### Click-Handler

```typescript
function handleSort(column: string) {
  if (sortColumn === column) {
    sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
  } else {
    sortColumn = column;
    sortDirection = 'desc';  // Erster Klick = absteigend
  }
}
```

### Sortierbare Spalten

**ArticleList:**

| Spaltentitel | Feldname | Typ |
|---|---|---|
| Titel | `title` | string |
| Tour-Datum | `tour_date` | string (ISO) |
| Dauer | `tour_duration_hours` | number |
| Distanz | `total_distance_km` | number |
| Höhenmeter | `elevation_gain_m` | number |
| Bilder | `image_count` | number |

**PhotobookList** (zusätzlich):

| Spaltentitel | Feldname | Typ |
|---|---|---|
| Grösse | `photobook_size` | string |

**Nicht sortierbar:** Checkbox-Spalte, Ansehen-Button, Löschen-Button.

### Visuelle Indikatoren

Aktive Sortierspalte zeigt ▲ (aufsteigend) oder ▼ (absteigend) im `<th>`:

```svelte
<th class="sortable" onclick={() => handleSort('title')}>
  Titel {sortColumn === 'title' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}
</th>
```

Inaktive Spalten zeigen keinen Indikator.

### Styling

```css
th.sortable {
  cursor: pointer;
  user-select: none;
}
th.sortable:hover {
  color: var(--text-primary);
}
```

Nicht-sortierbare `<th>` (Checkbox, Buttons) erhalten die Klasse `sortable` nicht und bleiben unverändert.

### Template-Änderung

`{#each articles as a}` → `{#each displayedArticles as a}` (analog für PhotobookList).

## Nicht-Ziele

- Keine Server-seitige Sortierung (API bleibt unverändert)
- Keine Paginierung
- Sortierstatus bleibt nicht über Daten-Neuladen hinweg erhalten
- Keine separate Sortierlogik pro Komponente (identische Implementierung in beiden)

## Verifikation

1. Frontend starten mit `cd frontend && npm run dev`
2. Prüfen: Header + Filter + Spaltentitel bleiben beim Scrollen fixiert
3. Prüfen: Klick auf jeden Spaltentitel sortiert die Liste
4. Prüfen: Erster Klick sortiert absteigend, zweiter Klick aufsteigend
5. Prüfen: Pfeil-Indikator erscheint nur in der aktiven Sortierspalte
6. Prüfen: Checkbox-Spalte und Button-Spalten sind nicht sortierbar
7. Beide Komponenten (ArticleList, PhotobookList) zeigen identisches Verhalten
