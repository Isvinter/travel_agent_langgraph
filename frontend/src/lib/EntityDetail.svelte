<svelte:options runes />

<script lang="ts">
  import { navigateTo } from "./stores/router";
  import { formatDate, formatDuration } from "./utils/format";
  import type { Snippet } from "svelte";

  interface Props {
    id: number;
    entityType: "article" | "photobook";
    content: Snippet<[htmlContent: string | null]>;
    extraMeta?: Snippet<[entity: Record<string, any>]>;
  }

  let { id, entityType, content, extraMeta }: Props = $props();

  const apiPath = entityType === "article" ? "articles" : "photobooks";
  const backPage = entityType === "article" ? "articles" : "photobooks" as const;
  const entityLabel = entityType === "article" ? "Artikel" : "Fotobuch";

  interface EntityFull {
    id: number;
    title: string | null;
    tour_date: string | null;
    tour_duration_hours: number | null;
    total_distance_km: number | null;
    elevation_gain_m: number | null;
    elevation_loss_m: number | null;
    html_content: string | null;
    gpx_file: string | null;
    model_used: string | null;
    notes: string | null;
  }

  let entity: EntityFull | null = $state(null);
  let rawEntity: Record<string, any> | null = $state(null);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);
  let aborted: boolean = false;
  let deleting: boolean = $state(false);

  async function fetchEntity() {
    loading = true;
    error = null;
    try {
      const res = await fetch(`/api/${apiPath}/${id}`);
      if (aborted) return;
      if (!res.ok) {
        if (res.status === 404) throw new Error(`${entityLabel} nicht gefunden.`);
        throw new Error(`API error: ${res.status}`);
      }
      const data = await res.json();
      entity = data[apiPath === "articles" ? "article" : "photobook"];
      rawEntity = entity;
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function handleDelete() {
    if (!confirm(`${entityLabel} wirklich löschen? Dies entfernt auch die Dateien.`)) return;
    deleting = true;
    try {
      const res = await fetch(`/api/${apiPath}/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      navigateTo({ page: backPage });
    } catch (e: any) {
      error = e.message;
      deleting = false;
    }
  }

  function handlePdfExport() {
    window.open(`/api/${apiPath}/${id}/pdf`, "_blank");
  }

  $effect(() => {
    aborted = false;
    fetchEntity();
    return () => { aborted = true; };
  });
</script>

<div class="entity-detail">
  <div class="toolbar">
    <button class="back-btn" onclick={() => navigateTo({ page: backPage })}>
      ← Zurück zur Liste
    </button>
    {#if entity}
      <div class="toolbar-right">
        <button class="pdf-btn" onclick={handlePdfExport}>Als PDF exportieren</button>
        <button class="delete-btn" onclick={handleDelete} disabled={deleting}>
          {deleting ? "Lösche..." : "🗑 Löschen"}
        </button>
      </div>
    {/if}
  </div>

  {#if loading}
    <p class="status">Lade {entityLabel}...</p>
  {:else if error}
    <p class="status error">{error}</p>
  {:else if entity}
    <h1 class="title">{entity.title || (entityType === "article" ? "Ohne Titel" : "Fotobuch")}</h1>

    <div class="meta">
      {#if entity.tour_date}
        <span>📅 {formatDate(entity.tour_date)}</span>
      {/if}
      {#if entity.tour_duration_hours}
        <span>⏱ {formatDuration(entity.tour_duration_hours)}</span>
      {/if}
      {#if entity.total_distance_km}
        <span>📏 {entity.total_distance_km} km</span>
      {/if}
      {#if entity.elevation_gain_m}
        <span>⛰ {entity.elevation_gain_m} m ↑</span>
      {/if}
      {#if entity.model_used}
        <span>🤖 {entity.model_used}</span>
      {/if}
      {#if extraMeta && rawEntity}
        {@render extraMeta(rawEntity)}
      {/if}
    </div>

    {#if entity.notes}
      <details class="notes-section">
        <summary>Notizen</summary>
        <pre class="notes">{entity.notes}</pre>
      </details>
    {/if}

    {@render content(entity.html_content)}
  {/if}
</div>

<style>
  .entity-detail {
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
  .status {
    color: var(--text-muted);
    padding: 2rem 0;
    text-align: center;
  }
  .status.error {
    color: var(--error);
  }
</style>
