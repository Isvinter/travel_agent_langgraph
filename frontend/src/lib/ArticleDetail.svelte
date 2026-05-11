<svelte:options runes />

<script lang="ts">
  import DOMPurify from "dompurify";
  import EntityDetail from "./EntityDetail.svelte";

  function sanitize(html: string | null): string {
    if (!html) return "";
    return DOMPurify.sanitize(html);
  }

  let { id }: { id: number } = $props();
</script>

<EntityDetail id={id} entityType="article">
  {#snippet content(html)}
    {#if html}
      <div class="content">
        {@html sanitize(html)}
      </div>
    {/if}
  {/snippet}
</EntityDetail>

<style>
  /* Content-Styles — nur für Artikel-spezifische Typografie */
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
</style>
