<svelte:options runes />

<script lang="ts">
  import EntityList from "./EntityList.svelte";

  function formatSize(size: string | null): string {
    if (!size) return "\u2014";
    const map: Record<string, string> = { short: "Klein", normal: "Normal", detailed: "Gross" };
    return map[size] || size;
  }
</script>

<EntityList entityType="photobook">
  {#snippet extraColumns()}
    <th>Grösse</th>
  {/snippet}
  {#snippet extraRowCells(item)}
    <td>{formatSize((item as any).photobook_size)}</td>
  {/snippet}
</EntityList>
