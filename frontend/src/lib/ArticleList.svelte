<svelte:options runes />

<script lang="ts">
  import { navigateTo } from "./stores/router";

  interface ArticleSummary {
    id: number;
    title: string | null;
    tour_date: string | null;
    tour_duration_hours: number | null;
    total_distance_km: number | null;
    elevation_gain_m: number | null;
    image_count: number | null;
    generation_timestamp: string | null;
  }

  let articles: ArticleSummary[] = $state([]);
  let total: number = $state(0);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);

  let tourDateFrom: string = $state("");
  let tourDateTo: string = $state("");
  let durationMin: string = $state("");
  let durationMax: string = $state("");

  async function fetchArticles() {
    loading = true;
    error = null;

    try {
      const params = new URLSearchParams();
      if (tourDateFrom) params.set("tour_date_from", tourDateFrom);
      if (tourDateTo) params.set("tour_date_to", tourDateTo);
      if (durationMin) params.set("duration_min", durationMin);
      if (durationMax) params.set("duration_max", durationMax);
      params.set("limit", "50");

      const res = await fetch(`/api/articles?${params.toString()}`);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();
      articles = data.articles;
      total = data.total;
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
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

  function handleView(id: number) {
    navigateTo({ page: "article", id });
  }

  // Fetch on mount
  $effect(() => {
    fetchArticles();
  });
</script>

<div class="article-list">
  <div class="header">
    <h2>Gespeicherte Artikel ({total})</h2>
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
    <button class="filter-btn" onclick={fetchArticles}>Filtern</button>
  </div>

  {#if loading}
    <p class="status">Lade Artikel...</p>
  {:else if error}
    <p class="status error">Fehler: {error}</p>
  {:else if articles.length === 0}
    <p class="status">Keine Artikel gefunden.</p>
  {:else}
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Titel</th>
            <th>Tour-Datum</th>
            <th>Dauer</th>
            <th>Distanz</th>
            <th>Höhenmeter</th>
            <th>Bilder</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each articles as a}
            <tr>
              <td>{a.title || "Ohne Titel"}</td>
              <td>{formatDate(a.tour_date)}</td>
              <td>{formatDuration(a.tour_duration_hours)}</td>
              <td>{a.total_distance_km ? `${a.total_distance_km} km` : "—"}</td>
              <td>{a.elevation_gain_m ? `${a.elevation_gain_m} m` : "—"}</td>
              <td>{a.image_count ?? "—"}</td>
              <td>
                <button class="view-btn" onclick={() => handleView(a.id)}>Ansehen</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .article-list {
    padding: 1rem;
    height: 100%;
    overflow-y: auto;
  }
  .header {
    margin-bottom: 1rem;
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
    overflow-x: auto;
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
  }
  td {
    padding: 0.5rem;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  tr:hover {
    background: rgba(255, 255, 255, 0.03);
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
</style>
