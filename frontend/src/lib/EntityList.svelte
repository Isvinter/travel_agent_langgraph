<svelte:options runes />

<script lang="ts">
  import { navigateTo } from "./stores/router";
  import { formatDate, formatDuration } from "./utils/format";
  import { sortItems } from "./utils/sort";
  import type { Snippet } from "svelte";

  interface Props {
    entityType: "article" | "photobook" | "calendar";
    extraColumns?: Snippet;
    extraRowCells?: Snippet<[item: Record<string, any>]>;
  }

  let { entityType, extraColumns, extraRowCells }: Props = $props();

  interface EntitySummary {
    id: number;
    title: string | null;
    tour_date: string | null;
    tour_duration_hours: number | null;
    total_distance_km: number | null;
    elevation_gain_m: number | null;
    image_count: number | null;
    generation_timestamp: string | null;
    status?: string | null;
    calendar_year?: number | null;
    preset?: string | null;
  }

  const apiPathMap: Record<string, string> = { article: "articles", photobook: "photobooks", calendar: "calendars" };
  const apiPath = $derived(apiPathMap[entityType]);
  const viewPage = $derived(entityType);
  const listPageMap: Record<string, string> = { article: "articles", photobook: "photobooks", calendar: "calendars" };
  const listPage = $derived(listPageMap[entityType]);
  const entityLabelMap: Record<string, string> = { article: "Artikel", photobook: "Fotobuch", calendar: "Kalender" };
  const entityLabel = $derived(entityLabelMap[entityType]);
  const entityLabelPluralMap: Record<string, string> = { article: "Artikel", photobook: "Fotobücher", calendar: "Kalender" };
  const entityLabelPlural = $derived(entityLabelPluralMap[entityType]);
  const isCalendar = $derived(entityType === "calendar");

  let entities: EntitySummary[] = $state([]);
  let total: number = $state(0);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);
  let aborted: boolean = false;

  let tourDateFrom: string = $state("");
  let tourDateTo: string = $state("");
  let durationMin: string = $state("");
  let durationMax: string = $state("");

  let selectedIds: Set<number> = $state(new Set());
  let dialogOpen: boolean = $state(false);
  let dialogMode: "single" | "batch" = $state("single");
  let dialogItemId: number | null = $state(null);
  let deleting: boolean = $state(false);

  let sortColumn: string | null = $state(null);
  let sortDirection: "asc" | "desc" = $state("asc");

  let displayed = $derived(
    sortColumn ? sortItems(entities, sortColumn, sortDirection) : entities
  );

  function toggleSelect(id: number) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    selectedIds = next;
  }

  function toggleSelectAll() {
    if (selectedIds.size === entities.length) selectedIds = new Set();
    else selectedIds = new Set(entities.map(e => e.id));
  }

  function handleSort(column: string) {
    if (sortColumn === column) sortDirection = sortDirection === "asc" ? "desc" : "asc";
    else { sortColumn = column; sortDirection = "desc"; }
  }

  async function fetchEntities() {
    loading = true;
    error = null;
    try {
      const params = new URLSearchParams();
      if (tourDateFrom) params.set("tour_date_from", tourDateFrom);
      if (tourDateTo) params.set("tour_date_to", tourDateTo);
      if (durationMin && durationMin !== "0") params.set("duration_min", durationMin);
      if (durationMax && durationMax !== "21") params.set("duration_max", durationMax);
      params.set("limit", "50");

      const res = await fetch(`/api/${apiPath}?${params.toString()}`);
      if (aborted) return;
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();
      const keyMap: Record<string, string> = { article: "articles", photobook: "photobooks", calendar: "calendars" };
      entities = data[keyMap[entityType]];
      total = data.total;
      selectedIds = new Set();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function handleView(id: number) {
    navigateTo({ page: viewPage, id });
  }

  function openSingleDelete(id: number) {
    dialogMode = "single";
    dialogItemId = id;
    dialogOpen = true;
  }

  function openBatchDelete() {
    if (selectedIds.size === 0) return;
    dialogMode = "batch";
    dialogItemId = null;
    dialogOpen = true;
  }

  function closeDialog() {
    dialogOpen = false;
    dialogItemId = null;
  }

  async function confirmDelete() {
    deleting = true;
    try {
      if (dialogMode === "single" && dialogItemId !== null) {
        const res = await fetch(`/api/${apiPath}/${dialogItemId}`, { method: "DELETE" });
        if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      } else {
        const res = await fetch(`/api/${apiPath}/delete-batch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids: [...selectedIds] }),
        });
        if (!res.ok) throw new Error(`Batch delete failed: ${res.status}`);
      }
      closeDialog();
      await fetchEntities();
    } catch (e: any) {
      error = e.message;
    } finally {
      deleting = false;
    }
  }

  $effect(() => {
    aborted = false;
    fetchEntities();
    return () => { aborted = true; };
  });
</script>

<div class="entity-list">
  <div class="header">
    <h2>Gespeicherte {entityLabelPlural} ({total})</h2>
    <button
      class="batch-delete-btn"
      disabled={selectedIds.size === 0}
      onclick={openBatchDelete}
    >
      🗑 Auswahl löschen ({selectedIds.size})
    </button>
  </div>

  <div class="filters">
    <label>
      Tour-Datum von:
      <input type="date" bind:value={tourDateFrom} />
    </label>
    <label>
      Tour-Datum bis:
      <input type="date" bind:value={tourDateTo} />
    </label>
    <div class="filter-duration">
      <span class="filter-duration-label">Dauer</span>
      <input type="range" min={0} max={21} bind:value={durationMin} />
      <span class="range-val">{durationMin || "0"}</span>
      <span class="filter-sep">–</span>
      <input type="range" min={0} max={21} bind:value={durationMax} />
      <span class="range-val">{durationMax || "21"}</span>
      <span class="filter-unit">Tage</span>
    </div>
    <button class="filter-btn" onclick={fetchEntities}>Filtern</button>
  </div>

  {#if loading}
    <p class="status">Lade {entityLabelPlural}...</p>
  {:else if error}
    <p class="status error">Fehler: {error}</p>
  {:else if entities.length === 0}
    <p class="status">Keine {entityLabelPlural} gefunden.</p>
  {:else}
    <div class="table-scroll-wrapper">
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th class="th-check">
                <input
                  type="checkbox"
                  checked={selectedIds.size === entities.length && entities.length > 0}
                  onchange={toggleSelectAll}
                />
              </th>
              <th class="sortable" onclick={() => handleSort("title")}>
                Titel {sortColumn === "title" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
              </th>
              {#if isCalendar}
                <th class="sortable num" onclick={() => handleSort("calendar_year")}>
                  Jahr {sortColumn === "calendar_year" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                </th>
                <th class="sortable" onclick={() => handleSort("preset")}>
                  Preset {sortColumn === "preset" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                </th>
                <th>Status</th>
                <th class="sortable" onclick={() => handleSort("generation_timestamp")}>
                  Erstellt {sortColumn === "generation_timestamp" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                </th>
              {:else}
                <th class="sortable" onclick={() => handleSort("tour_date")}>
                  Tour-Datum {sortColumn === "tour_date" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                </th>
                <th class="sortable num" onclick={() => handleSort("tour_duration_hours")}>
                  Dauer {sortColumn === "tour_duration_hours" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                </th>
                <th class="sortable num" onclick={() => handleSort("total_distance_km")}>
                  Distanz {sortColumn === "total_distance_km" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                </th>
                <th class="sortable num" onclick={() => handleSort("elevation_gain_m")}>
                  Höhenmeter {sortColumn === "elevation_gain_m" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                </th>
                <th class="sortable num" onclick={() => handleSort("image_count")}>
                  Bilder {sortColumn === "image_count" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                </th>
              {/if}
              {#if extraColumns}
                {@render extraColumns()}
              {/if}
              <th class="actions-header"></th>
            </tr>
          </thead>
          <tbody>
            {#each displayed as item}
              <tr>
                <td class="td-check">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(item.id)}
                    onchange={() => toggleSelect(item.id)}
                  />
                </td>
                <td>
                  {item.title || "Ohne Titel"}
                  {#if entityType === "article" && item.status === "draft"}
                    <span class="draft-badge">Entwurf</span>
                  {/if}
                </td>
                {#if isCalendar}
                  <td class="num">{item.calendar_year ?? "\u2014"}</td>
                  <td>{item.preset ?? "\u2014"}</td>
                  <td>{item.status ?? "\u2014"}</td>
                  <td>{formatDate(item.generation_timestamp)}</td>
                {:else}
                  <td>{formatDate(item.tour_date)}</td>
                  <td class="num">{formatDuration(item.tour_duration_hours)}</td>
                  <td class="num">{item.total_distance_km ? `${item.total_distance_km} km` : "\u2014"}</td>
                  <td class="num">{item.elevation_gain_m ? `${item.elevation_gain_m} m` : "\u2014"}</td>
                  <td class="num">{item.image_count ?? "\u2014"}</td>
                {/if}
                {#if extraRowCells}
                  {@render extraRowCells(item)}
                {/if}
                <td class="actions-cell">
                  <button class="icon-btn" title="Ansehen" onclick={() => handleView(item.id)}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                      <circle cx="12" cy="12" r="3"/>
                    </svg>
                  </button>
                  <button class="icon-btn icon-delete" title="Löschen" onclick={() => openSingleDelete(item.id)}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="3 6 5 6 21 6"/>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
</div>

{#if dialogOpen}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="dialog-overlay" onclick={closeDialog} role="dialog" aria-modal="true" tabindex={-1} onkeydown={(e) => e.key === "Escape" && closeDialog()}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="dialog" onclick={(e: MouseEvent) => e.stopPropagation()}>
      <p>
        {dialogMode === "single"
          ? `Diesen ${entityLabel.toLowerCase()} wirklich löschen? Dies entfernt auch die Dateien.`
          : `${selectedIds.size} ${entityLabelPlural.toLowerCase()} wirklich löschen? Dies entfernt auch die Dateien.`}
      </p>
      <div class="dialog-actions">
        <button class="cancel-btn" onclick={closeDialog} disabled={deleting}>Abbrechen</button>
        <button class="confirm-btn" onclick={confirmDelete} disabled={deleting}>
          {deleting ? "Lösche..." : "Löschen"}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .entity-list {
    padding: 1rem;
    display: flex;
    flex-direction: column;
    height: 100%;
  }
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }
  .header h2 {
    font-size: 0.875rem;
  }
  .batch-delete-btn {
    padding: 0.4rem 0.75rem;
    font-size: 0.8rem;
    background: var(--error);
    color: white;
    white-space: nowrap;
    border: none;
    border-radius: var(--radius);
    cursor: pointer;
  }
  .batch-delete-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
    background: var(--panel-2);
    color: var(--text-muted);
  }
  .batch-delete-btn:not(:disabled):hover {
    opacity: 0.9;
  }
  .filters {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
    margin-bottom: 1rem;
    align-items: flex-end;
  }
  .filters label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.75rem;
    color: var(--text-muted);
  }
  .filters input {
    padding: 0.35rem 0.5rem;
    font-size: 0.8rem;
  }
  .filter-btn {
    padding: 0.4rem 0.75rem;
    background: var(--accent);
    color: white;
    font-size: 0.8rem;
    height: fit-content;
    align-self: flex-end;
  }
  .status {
    color: var(--text-muted);
    padding: 2rem 0;
    text-align: center;
  }
  .status.error {
    color: var(--error);
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
  }
  th {
    text-align: left;
    color: var(--text-muted);
    font-weight: 600;
    padding: 10px 12px;
    border-bottom: 2px solid var(--border);
    white-space: nowrap;
    position: sticky;
    top: 0;
    background: var(--th-bg);
    z-index: 1;
    font-size: 0.72rem;
  }
  th.sortable {
    cursor: pointer;
    user-select: none;
  }
  th.sortable:hover {
    color: var(--text-primary);
  }
  .th-check {
    width: 2rem;
  }
  td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  .td-check {
    width: 2rem;
  }
  .td-check input {
    cursor: pointer;
  }
  tr:hover {
    background: var(--panel-2);
  }

  .filter-duration {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 0.75rem;
    color: var(--text-muted);
  }
  .filter-duration-label {
    margin-right: 4px;
  }
  .filter-duration input[type="range"] {
    width: 70px;
    accent-color: var(--accent);
    padding: 0;
    margin: 0;
  }
  .range-val {
    min-width: 18px;
    text-align: center;
    color: var(--text-primary);
    font-size: 0.75rem;
  }
  .filter-sep {
    color: var(--text-muted);
  }
  .filter-unit {
    color: var(--text-muted);
    font-size: 0.7rem;
  }

  .actions-header {
    width: 70px;
  }
  .actions-cell {
    text-align: center;
    white-space: nowrap;
  }
  .icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px;
    opacity: 0.5;
    transition: opacity 0.15s, color 0.15s;
    color: var(--text-secondary);
    display: inline-flex;
    align-items: center;
  }
  .icon-btn:hover {
    opacity: 1;
    color: var(--accent);
  }
  .icon-delete:hover {
    color: var(--error);
  }

  .dialog-overlay {
    position: fixed;
    inset: 0;
    background: var(--overlay-bg);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }
  .dialog {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1.5rem;
    max-width: 400px;
    width: 90%;
  }
  .dialog p {
    margin: 0 0 1.25rem 0;
    font-size: 0.9rem;
  }
  .dialog-actions {
    display: flex;
    gap: 0.75rem;
    justify-content: flex-end;
  }
  .cancel-btn {
    padding: 0.4rem 0.75rem;
    background: var(--surface-alt);
    color: var(--text);
    font-size: 0.8rem;
  }
  .cancel-btn:hover {
    background: var(--accent);
  }
  .confirm-btn {
    padding: 0.4rem 0.75rem;
    background: var(--error);
    color: white;
    font-size: 0.8rem;
  }
  .confirm-btn:disabled, .cancel-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .draft-badge {
    font-size: 0.6rem;
    background: #fef3c7;
    color: #92400e;
    padding: 1px 6px;
    border-radius: 3px;
    margin-left: 0.4rem;
    font-weight: 500;
  }

  .table-scroll-wrapper {
    flex: 1;
    overflow: auto;
    min-height: 0;
  }
</style>
