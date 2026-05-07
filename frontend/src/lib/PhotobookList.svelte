<svelte:options runes />

<script lang="ts">
  import { navigateTo } from "./stores/router";

  interface PhotobookSummary {
    id: number;
    title: string | null;
    tour_date: string | null;
    tour_duration_hours: number | null;
    total_distance_km: number | null;
    elevation_gain_m: number | null;
    image_count: number | null;
    photobook_size: string | null;
    page_count: number | null;
    generation_timestamp: string | null;
  }

  let photobooks: PhotobookSummary[] = $state([]);
  let total: number = $state(0);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);

  let tourDateFrom: string = $state("");
  let tourDateTo: string = $state("");
  let durationMin: string = $state("");
  let durationMax: string = $state("");

  let selectedIds: Set<number> = $state(new Set());
  let dialogOpen: boolean = $state(false);
  let dialogMode: "single" | "batch" = $state("single");
  let dialogItemId: number | null = $state(null);
  let deleting: boolean = $state(false);

  function toggleSelect(id: number) {
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    selectedIds = next;
  }

  function toggleSelectAll() {
    if (selectedIds.size === photobooks.length) {
      selectedIds = new Set();
    } else {
      selectedIds = new Set(photobooks.map(a => a.id));
    }
  }

  async function fetchPhotobooks() {
    loading = true;
    error = null;

    try {
      const params = new URLSearchParams();
      if (tourDateFrom) params.set("tour_date_from", tourDateFrom);
      if (tourDateTo) params.set("tour_date_to", tourDateTo);
      if (durationMin) params.set("duration_min", durationMin);
      if (durationMax) params.set("duration_max", durationMax);
      params.set("limit", "50");

      const res = await fetch(`/api/photobooks?${params.toString()}`);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();
      photobooks = data.photobooks;
      total = data.total;
      selectedIds = new Set();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function formatDate(iso: string | null): string {
    if (!iso) return "\u2014";
    return new Date(iso).toLocaleDateString("de-DE");
  }

  function formatDuration(hours: number | null): string {
    if (hours === null || hours === undefined) return "\u2014";
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    return `${h}h ${m}m`;
  }

  function formatSize(size: string | null): string {
    if (!size) return "\u2014";
    const map: Record<string, string> = { short: "Klein", normal: "Normal", detailed: "Gross" };
    return map[size] || size;
  }

  function handleView(id: number) {
    navigateTo({ page: "photobook", id });
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
        const res = await fetch(`/api/photobooks/${dialogItemId}`, { method: "DELETE" });
        if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      } else {
        const res = await fetch("/api/photobooks/delete-batch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids: [...selectedIds] }),
        });
        if (!res.ok) throw new Error(`Batch delete failed: ${res.status}`);
      }
      closeDialog();
      await fetchPhotobooks();
    } catch (e: any) {
      error = e.message;
    } finally {
      deleting = false;
    }
  }

  $effect(() => {
    fetchPhotobooks();
  });
</script>

<div class="photobook-list">
  <div class="header">
    <h2>Gespeicherte Fotobücher ({total})</h2>
    <button
      class="batch-delete-btn"
      disabled={selectedIds.size === 0}
      onclick={openBatchDelete}
    >
      Auswahl löschen ({selectedIds.size})
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
    <label>
      Dauer (min h):
      <input type="number" bind:value={durationMin} placeholder="z.B. 2" step="0.5" />
    </label>
    <label>
      Dauer (max h):
      <input type="number" bind:value={durationMax} placeholder="z.B. 8" step="0.5" />
    </label>
    <button class="filter-btn" onclick={fetchPhotobooks}>Filtern</button>
  </div>

  {#if loading}
    <p class="status">Lade Fotobücher...</p>
  {:else if error}
    <p class="status error">Fehler: {error}</p>
  {:else if photobooks.length === 0}
    <p class="status">Keine Fotobücher gefunden.</p>
  {:else}
    <div class="table-scroll-wrapper">
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th class="th-check">
                <input
                  type="checkbox"
                  checked={selectedIds.size === photobooks.length && photobooks.length > 0}
                  onchange={toggleSelectAll}
                />
              </th>
              <th>Titel</th>
              <th>Tour-Datum</th>
              <th>Dauer</th>
              <th>Distanz</th>
              <th>Höhenmeter</th>
              <th>Bilder</th>
              <th>Grösse</th>
              <th></th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each photobooks as p}
              <tr>
                <td class="td-check">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(p.id)}
                    onchange={() => toggleSelect(p.id)}
                  />
                </td>
                <td>{p.title || "Ohne Titel"}</td>
                <td>{formatDate(p.tour_date)}</td>
                <td>{formatDuration(p.tour_duration_hours)}</td>
                <td>{p.total_distance_km ? `${p.total_distance_km} km` : "\u2014"}</td>
                <td>{p.elevation_gain_m ? `${p.elevation_gain_m} m` : "\u2014"}</td>
                <td>{p.image_count ?? "\u2014"}</td>
                <td>{formatSize(p.photobook_size)}</td>
                <td>
                  <button class="view-btn" onclick={() => handleView(p.id)}>Ansehen</button>
                </td>
                <td>
                  <button class="delete-btn" onclick={() => openSingleDelete(p.id)}>Löschen</button>
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
  <div class="dialog-overlay" onclick={closeDialog}>
    <div class="dialog" onclick={(e: MouseEvent) => e.stopPropagation()}>
      <p>
        {dialogMode === "single"
          ? "Dieses Fotobuch wirklich löschen? Dies entfernt auch die Dateien."
          : `${selectedIds.size} Fotobücher wirklich löschen? Dies entfernt auch die Dateien.`}
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
  .photobook-list {
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
  }
  .batch-delete-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
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
  .table-container {
    /* overflow handled by .table-scroll-wrapper */
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
  }
  th {
    text-align: left;
    color: var(--text-muted);
    font-weight: normal;
    padding: 0.5rem 0.5rem;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
    position: sticky;
    top: 0;
    background: var(--panel);
    z-index: 1;
  }
  .th-check {
    width: 2rem;
  }
  td {
    padding: 0.5rem;
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
  .view-btn {
    padding: 0.3rem 0.6rem;
    background: var(--surface-alt);
    color: var(--text);
    font-size: 0.75rem;
  }
  .view-btn:hover {
    background: var(--accent);
  }
  .delete-btn {
    padding: 0.3rem 0.6rem;
    background: var(--error);
    color: white;
    font-size: 0.75rem;
  }
  .delete-btn:hover {
    opacity: 0.85;
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

  .table-scroll-wrapper {
    flex: 1;
    overflow: auto;
    min-height: 0;
  }
</style>
