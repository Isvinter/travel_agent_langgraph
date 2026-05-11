<svelte:options runes />

<script lang="ts">
  import EntityDetail from "./EntityDetail.svelte";

  let { id }: { id: number } = $props();

  function formatSize(size: string | null): string {
    if (!size) return "\u2014";
    const map: Record<string, string> = { short: "Klein", normal: "Normal", detailed: "Gross" };
    return map[size] || size;
  }

  function iframeHeight(pageCount: number | null): string {
    if (!pageCount || pageCount < 1) return "1200px";
    return `${pageCount * 1125}px`;
  }
</script>

<EntityDetail id={id} entityType="photobook">
  {#snippet content(html)}
    {#if html}
      <iframe
        class="photobook-iframe"
        srcdoc={html}
        title="Fotobuch"
        sandbox=""
        scrolling="no"
        style="height: {iframeHeight(null)}; overflow: hidden;"
      ></iframe>
    {/if}
  {/snippet}
  {#snippet extraMeta(entity)}
    {#if entity?.photobook_size}
      <span>📖 {formatSize(entity.photobook_size)} ({entity.page_count ?? "?"} Seiten)</span>
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
