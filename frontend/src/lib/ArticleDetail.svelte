<svelte:options runes />

<script lang="ts">
  import DOMPurify from "dompurify";
  import { navigateTo } from "./stores/router";

  function sanitize(html: string | null): string {
    if (!html) return "";
    return DOMPurify.sanitize(html);
  }

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
        {@html sanitize(article.html_content)}
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
