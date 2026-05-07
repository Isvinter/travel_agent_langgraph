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
      <div class="content">
        {@html photobook.html_content}
      </div>
    {/if}
  {/if}
</div>

<style>
  .photobook-detail {
    padding: 1rem;
    height: 100%;
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
  .content {
    line-height: 1.8;
    font-size: 1.05rem;
  }
  .content :global(h1) {
    font-size: 2rem;
    font-weight: 700;
    margin: 2rem 0 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--border);
  }
  .content :global(h2) {
    font-size: 1.4rem;
    font-weight: 600;
    margin: 1.8rem 0 0.8rem;
  }
  .content :global(h3) {
    font-size: 1.15rem;
    font-weight: 600;
    margin: 1.5rem 0 0.6rem;
  }
  .content :global(p) {
    margin: 0 0 1.2rem;
  }
  .content :global(img) {
    max-width: 100%;
    height: auto;
    display: block;
    border-radius: 4px;
  }
  .content :global(figure) {
    margin: 2rem auto;
    text-align: center;
  }
  .content :global(figure img) {
    margin: 0 auto;
  }
  .content :global(figcaption) {
    margin-top: 0.6rem;
    font-size: 0.9rem;
    color: var(--text-muted);
    font-style: italic;
    line-height: 1.5;
    max-width: 600px;
    margin-left: auto;
    margin-right: auto;
  }
  .content :global(blockquote) {
    margin: 1.5rem 0;
    padding: 0.8rem 1.5rem;
    border-left: 4px solid var(--accent);
    background: var(--surface);
    font-style: italic;
    color: var(--text-secondary);
  }
  .content :global(ul),
  .content :global(ol) {
    margin: 0 0 1.2rem 1.5rem;
    padding: 0;
  }
  .content :global(li) {
    margin-bottom: 0.4rem;
  }
  .content :global(a) {
    color: var(--accent);
    text-decoration: underline;
  }
  .content :global(hr) {
    border: none;
    border-top: 1px solid var(--border);
    margin: 2rem 0;
  }
  .content :global(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 1.5rem 0;
    font-size: 0.9rem;
  }
  .content :global(th),
  .content :global(td) {
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid var(--border);
    text-align: left;
  }
  .content :global(th) {
    font-weight: 600;
    background: var(--surface);
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
