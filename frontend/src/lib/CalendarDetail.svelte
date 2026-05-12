<svelte:options runes />

<script lang="ts">
  import EntityDetail from "./EntityDetail.svelte";

  let { id }: { id: number } = $props();

  /** Dynamische Iframe-Höhe: Kalender hat 13 Seiten (1 Cover + 12 Monate) im Querformat. */
  function iframeHeight(_html: string | null): string {
    if (!_html) return "1200px";
    const pageMatches = _html.match(/class="calendar-page"/g);
    const pc = pageMatches ? pageMatches.length : 13;
    return `${pc * 800}px`;
  }
</script>

<EntityDetail id={id} entityType="calendar">
  {#snippet content(html, _entity)}
    {#if html}
      <iframe
        class="calendar-iframe"
        srcdoc={html}
        title="Kalender"
        sandbox="allow-same-origin"
        scrolling="no"
        style="height: {iframeHeight(html)}; overflow: hidden;"
      ></iframe>
    {/if}
  {/snippet}
  {#snippet extraMeta(entity)}
    {#if entity?.calendar_year}
      <span>{entity.calendar_year}</span>
    {/if}
  {/snippet}
</EntityDetail>

<style>
  .calendar-iframe {
    width: 100%;
    border: none;
    background: white;
  }
</style>
