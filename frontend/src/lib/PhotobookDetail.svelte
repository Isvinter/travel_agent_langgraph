<svelte:options runes />

<script lang="ts">
  import EntityDetail from "./EntityDetail.svelte";

  let { id }: { id: number } = $props();

  let pageCount: number | null = $state(null);

  function formatSize(size: string | null): string {
    if (!size) return "\u2014";
    const map: Record<string, string> = { short: "Klein", normal: "Normal", detailed: "Gross" };
    return map[size] || size;
  }

  function iframeHeight(pc: number | null): string {
    if (!pc || pc < 1) return "1200px";
    return `${pc * 1125}px`;
  }
</script>

<EntityDetail id={id} entityType="photobook">
  {#snippet content(html, entity)}
    {#if html}
      <iframe
        class="photobook-iframe"
        srcdoc={html}
        title="Fotobuch"
        sandbox="allow-same-origin"
        scrolling="no"
        style="height: {iframeHeight(pageCount)}; overflow: hidden;"
      ></iframe>
    {/if}
  {/snippet}
  {#snippet extraMeta(entity)}
    {#if entity?.page_count && entity.page_count !== pageCount}
      <!-- Aktualisiere pageCount reaktiv -->
      {pageCount = entity.page_count}
    {/if}
    {#if entity?.photobook_size}
      <span>📖 {formatSize(entity.photobook_size)} ({pageCount ?? "?"} Seiten)</span>
    {/if}
  {/snippet}
</EntityDetail>

<style>
  .photobook-iframe {
    width: 100%;
    border: none;
    background: white;
  }
</style>
