<svelte:options runes />

<script lang="ts">
  import { navigateTo } from "./stores/router";

  let { id }: { id: number } = $props();

  interface ArticleFull {
    id: number;
    title: string | null;
    tour_date: string | null;
    tour_duration_hours: number | null;
    generation_timestamp: string | null;
    total_distance_km: number | null;
    elevation_gain_m: number | null;
    elevation_loss_m: number | null;
    html_content: string | null;
    markdown_content: string | null;
    markdown_path: string | null;
    html_path: string | null;
    gpx_file: string | null;
    model_used: string | null;
    notes: string | null;
    images: { image_path: string; is_map: boolean; is_elevation_profile: boolean }[];
  }

  let article: ArticleFull | null = $state(null);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);
  let deleting: boolean = $state(false);

  async function fetchArticle() {
    loading = true;
    error = null;
    try {
      const res = await fetch(`/api/articles/${id}`);
      if (!res.ok) {
        if (res.status === 404) throw new Error("Artikel nicht gefunden.");
        throw new Error(`API error: ${res.status}`);
      }
      const data = await res.json();
      article = data.article;
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function handleDelete() {
    if (!confirm("Artikel wirklich löschen? Dies entfernt auch die Dateien.")) return;
    deleting = true;
    try {
      const res = await fetch(`/api/articles/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      navigateTo({ page: "articles" });
    } catch (e: any) {
      error = e.message;
      deleting = false;
    }
  }

  function handlePdfExport() {
    window.open(`/api/articles/${id}/pdf`, "_blank");
  }

  function formatDate(iso: string | null): string {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("de-DE");
  }

  function formatDuration(hours: number | null): string {
    if (hours === null || hours === undefined) return "—";
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    return `${h}h ${m}m`;
  }

  $effect(() => {
    fetchArticle();
  });
</script>

<div class="article-detail">
  <div class="toolbar">
    <button class="back-btn" onclick={() => navigateTo({ page: "articles" })}>
      ← Zurück zur Liste
    </button>
    {#if article}
      <div class="toolbar-right">
        <button class="pdf-btn" onclick={handlePdfExport}>Als PDF exportieren</button>
        <button class="delete-btn" onclick={handleDelete} disabled={deleting}>
          {deleting ? "Lösche..." : "🗑 Löschen"}
        </button>
      </div>
    {/if}
  </div>

  {#if loading}
    <p class="status">Lade Artikel...</p>
  {:else if error}
    <p class="status error">{error}</p>
  {:else if article}
    <h1 class="title">{article.title || "Ohne Titel"}</h1>

    <div class="meta">
      {#if article.tour_date}
        <span>📅 {formatDate(article.tour_date)}</span>
      {/if}
      {#if article.tour_duration_hours}
        <span>⏱ {formatDuration(article.tour_duration_hours)}</span>
      {/if}
      {#if article.total_distance_km}
        <span>📏 {article.total_distance_km} km</span>
      {/if}
      {#if article.elevation_gain_m}
        <span>⛰ {article.elevation_gain_m} m ↑</span>
      {/if}
      {#if article.model_used}
        <span>🤖 {article.model_used}</span>
      {/if}
    </div>

    {#if article.notes}
      <details class="notes-section">
        <summary>Notizen</summary>
        <pre class="notes">{article.notes}</pre>
      </details>
    {/if}

    {#if article.html_content}
      <div class="content">
        {@html article.html_content}
      </div>
    {/if}
  {/if}
</div>

<style>
  .article-detail {
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
    background: #27ae60;
    color: white;
  }
  .pdf-btn:hover {
    background: #219a52;
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
    line-height: 1.6;
  }
  .content :global(img) {
    max-width: 100%;
    border-radius: 4px;
  }
  .content :global(h1),
  .content :global(h2),
  .content :global(h3) {
    margin-top: 1.25rem;
    margin-bottom: 0.5rem;
  }
  .content :global(p) {
    margin-bottom: 0.75rem;
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
