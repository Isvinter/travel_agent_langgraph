<svelte:options runes />

<script lang="ts">
  import { navigateTo } from "./stores/router";

  let { id }: { id: number } = $props();

  interface PhotobookFull {
    id: number;
    title: string | null;
    tour_date: string | null;
    tour_duration_hours: number | null;
    generation_timestamp: string | null;
    total_distance_km: number | null;
    elevation_gain_m: number | null;
    elevation_loss_m: number | null;
    html_content: string | null;
    html_path: string | null;
    pdf_path: string | null;
    gpx_file: string | null;
    model_used: string | null;
    notes: string | null;
    photobook_size: string | null;
    page_count: number | null;
    images: { image_path: string; is_map: boolean; is_elevation_profile: boolean }[];
  }

  let photobook: PhotobookFull | null = $state(null);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);
  let deleting: boolean = $state(false);

  function iframeHeight(pageCount: number | null): string {
    if (!pageCount || pageCount < 1) return "1200px";
    return `${pageCount * 1125}px`;
  }

  async function fetchPhotobook() {
    loading = true;
    error = null;
    try {
      const res = await fetch(`/api/photobooks/${id}`);
      if (!res.ok) {
        if (res.status === 404) throw new Error("Fotobuch nicht gefunden.");
        throw new Error(`API error: ${res.status}`);
      }
      const data = await res.json();
      photobook = data.photobook;
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function handleDelete() {
    if (!confirm("Fotobuch wirklich löschen? Dies entfernt auch die Dateien.")) return;
    deleting = true;
    try {
      const res = await fetch(`/api/photobooks/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      navigateTo({ page: "photobooks" });
    } catch (e: any) {
      error = e.message;
      deleting = false;
    }
  }

  function handlePdfExport() {
    window.open(`/api/photobooks/${id}/pdf`, "_blank");
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

  $effect(() => {
    fetchPhotobook();
  });
</script>

<div class="photobook-detail">
  <div class="toolbar">
    <button class="back-btn" onclick={() => navigateTo({ page: "photobooks" })}>
      ← Zurück zur Liste
    </button>
    {#if photobook}
      <div class="toolbar-right">
        <button class="pdf-btn" onclick={handlePdfExport}>Als PDF exportieren</button>
        <button class="delete-btn" onclick={handleDelete} disabled={deleting}>
          {deleting ? "Lösche..." : "🗑 Löschen"}
        </button>
      </div>
    {/if}
  </div>

  {#if loading}
    <p class="status">Lade Fotobuch...</p>
  {:else if error}
    <p class="status error">{error}</p>
  {:else if photobook}
    <h1 class="title">{photobook.title || "Fotobuch"}</h1>

    <div class="meta">
      {#if photobook.tour_date}
        <span>📅 {formatDate(photobook.tour_date)}</span>
      {/if}
      {#if photobook.tour_duration_hours}
        <span>⏱ {formatDuration(photobook.tour_duration_hours)}</span>
      {/if}
      {#if photobook.total_distance_km}
        <span>📏 {photobook.total_distance_km} km</span>
      {/if}
      {#if photobook.elevation_gain_m}
        <span>⛰ {photobook.elevation_gain_m} m ↑</span>
      {/if}
      {#if photobook.model_used}
        <span>🤖 {photobook.model_used}</span>
      {/if}
      {#if photobook.photobook_size}
        <span>📖 {formatSize(photobook.photobook_size)} ({photobook.page_count ?? "?"} Seiten)</span>
      {/if}
    </div>

    {#if photobook.notes}
      <details class="notes-section">
        <summary>Notizen</summary>
        <pre class="notes">{photobook.notes}</pre>
      </details>
    {/if}

    {#if photobook.html_content}
      <iframe
        class="photobook-iframe"
        srcdoc={photobook.html_content}
        title="Fotobuch"
        sandbox=""
        scrolling="no"
        style="height: {iframeHeight(photobook.page_count)}; overflow: hidden;"
      ></iframe>
    {/if}
  {/if}
</div>

<style>
  .photobook-detail {
    padding: 1rem;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    max-width: 1400px;
  }
  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }
  .toolbar-right {
    display: flex;
    gap: 0.5rem;
  }
  .back-btn, .delete-btn, .pdf-btn {
    padding: 0.4rem 0.75rem;
    font-size: 0.8rem;
  }
  .back-btn {
    background: var(--surface-alt);
    color: var(--text);
  }
  .back-btn:hover {
    background: var(--accent);
  }
  .pdf-btn {
    background: var(--success);
    color: white;
  }
  .pdf-btn:hover {
    filter: brightness(0.9);
  }
  .delete-btn {
    background: var(--error);
    color: white;
  }
  .delete-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .title {
    font-size: 1.5rem;
    margin-bottom: 0.75rem;
  }
  .meta {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    margin-bottom: 1rem;
    color: var(--text-muted);
    font-size: 0.8rem;
  }
  .notes-section {
    margin-bottom: 1rem;
  }
  .notes-section summary {
    cursor: pointer;
    color: var(--accent);
    font-size: 0.85rem;
  }
  .notes {
    background: var(--surface);
    padding: 0.75rem;
    border-radius: 4px;
    margin-top: 0.5rem;
    font-size: 0.8rem;
    white-space: pre-wrap;
  }
  .photobook-iframe {
    width: 100%;
    border: none;
    background: white;
  }
  .status {
    color: var(--text-muted);
    padding: 2rem 0;
    text-align: center;
  }
  .status.error {
    color: var(--error);
  }
</style>
