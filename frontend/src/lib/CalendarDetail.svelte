<svelte:options runes />

<script lang="ts">
  import EntityDetail from "./EntityDetail.svelte";

  let { id }: { id: number } = $props();
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
        style="height: 1200px; overflow: hidden;"
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
