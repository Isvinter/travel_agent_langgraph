<svelte:options runes />

<script lang="ts">
  import { currentDraftId } from "./stores/pipeline";
  import { navigateTo } from "./stores/router";

  let { id }: { id: number } = $props();

  interface MarkedItem {
    element_type: "paragraph" | "image";
    element_index: number;
    original_content: string;
    instruction: string;
  }

  let articleHtml: string = $state("");
  let title: string = $state("");
  let revisionRound: number = $state(0);
  let marked: MarkedItem[] = $state([]);
  let loading: boolean = $state(true);
  let sending: boolean = $state(false);
  let errorMsg: string = $state("");
  let paragraphWarning: string = $state("");
  let previewEl: HTMLDivElement | undefined = $state();

  async function loadDraft() {
    loading = true;
    errorMsg = "";
    try {
      const res = await fetch(`/api/articles/${id}`);
      if (!res.ok) throw new Error("Draft nicht gefunden");
      const article = await res.json();
      articleHtml = article.html_content || "";
      title = article.title || "Draft";
      revisionRound = article.revision_round || 0;
    } catch (e: any) {
      errorMsg = e.message;
    } finally {
      loading = false;
    }
  }

  function attachClickHandlers() {
    if (!previewEl) return;
    const blocks = previewEl.querySelectorAll("p, figure");
    blocks.forEach((block, idx) => {
      block.setAttribute("data-block-index", String(idx));
      const handler = (e: Event) => {
        e.stopPropagation();
        toggleMark(idx, block);
      };
      (block as any).__draftClickHandler = handler;
      block.addEventListener("click", handler);
    });
  }

  function toggleMark(index: number, block: Element) {
    const existingIdx = marked.findIndex((m) => m.element_index === index);
    if (existingIdx >= 0) {
      marked = marked.filter((m) => m.element_index !== index);
      block.classList.remove("marked");
    } else {
      const isFigure = block.tagName === "FIGURE";
      const content = isFigure
        ? (block.querySelector("img")?.getAttribute("src") || block.textContent?.trim() || "")
        : block.textContent?.trim() || "";
      marked = [...marked, {
        element_type: isFigure ? "image" : "paragraph",
        element_index: index,
        original_content: content.slice(0, 500),
        instruction: "",
      }];
      block.classList.add("marked");
    }
  }

  function removeMark(index: number) {
    marked = marked.filter((m) => m.element_index !== index);
    if (previewEl) {
      const block = previewEl.querySelector(`[data-block-index="${index}"]`);
      block?.classList.remove("marked");
    }
  }

  async function handleRevise() {
    if (marked.length === 0 || sending) return;
    sending = true;
    paragraphWarning = "";
    errorMsg = "";
    try {
      const res = await fetch(`/api/articles/${id}/revise`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ changes: marked }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Revision fehlgeschlagen");
      }
      const data = await res.json();
      articleHtml = data.html;
      revisionRound = data.revision_round;
      marked = [];
      if (data.paragraph_count_changed) {
        paragraphWarning = "Achtung: Das LLM hat die Absatz-Anzahl verändert. Bitte den Artikel prüfen.";
      }
    } catch (e: any) {
      errorMsg = e.message;
    } finally {
      sending = false;
    }
  }

  async function handlePublish() {
    try {
      const res = await fetch(`/api/articles/${id}/publish`, { method: "POST" });
      if (!res.ok) throw new Error("Veröffentlichung fehlgeschlagen");
      currentDraftId.set(null);
      navigateTo({ page: "article", id });
    } catch (e: any) {
      errorMsg = e.message;
    }
  }

  async function handleDelete() {
    if (!confirm("Draft wirklich verwerfen?")) return;
    try {
      await fetch(`/api/articles/${id}`, { method: "DELETE" });
      currentDraftId.set(null);
      navigateTo({ page: "pipeline" });
    } catch (e: any) {
      errorMsg = e.message;
    }
  }

  loadDraft();

  $effect(() => {
    if (articleHtml && previewEl) {
      previewEl.innerHTML = articleHtml;
      attachClickHandlers();
    }
  });
</script>

{#if loading}
  <div class="draft-status">Draft wird geladen…</div>
{:else if errorMsg}
  <div class="draft-error">Fehler: {errorMsg}</div>
{:else}
  <div class="draft-layout">
    <div class="draft-header">
      <h2>{title} <span class="revision-badge">Revision {revisionRound}</span></h2>
      {#if paragraphWarning}
        <div class="warning">{paragraphWarning}</div>
      {/if}
      {#if errorMsg}
        <div class="draft-error">{errorMsg}</div>
      {/if}
    </div>

    <div class="draft-split">
      <div class="draft-preview" bind:this={previewEl}></div>

      <div class="draft-sidebar">
        <h3>Änderungen</h3>

        {#if marked.length === 0}
          <p class="hint">Klicke auf einen Absatz oder ein Bild im Artikel, um es zu markieren.</p>
        {:else}
          {#each marked as item, i (item.element_index)}
            <div class="marked-item">
              <div class="marked-header">
                <span class="badge">Markiert #{i + 1} — {item.element_type === "image" ? "Bild" : "Absatz"} {item.element_index}</span>
              </div>
              <div class="marked-preview">{item.original_content.slice(0, 150)}…</div>
              <label>
                <span class="field-label">Anweisung:</span>
                <textarea
                  bind:value={item.instruction}
                  placeholder="z.B. Kürzer fassen, mehr Details zur Aussicht..."
                  rows={3}
                ></textarea>
              </label>
              <button class="btn-remove" onclick={() => removeMark(item.element_index)}>
                Markierung entfernen
              </button>
            </div>
          {/each}
        {/if}

        <div class="actions">
          <button
            class="btn btn-publish"
            onclick={handlePublish}
          >
            ✓ Beitrag übernehmen
          </button>
          <button
            class="btn btn-revise"
            disabled={marked.length === 0 || sending}
            onclick={handleRevise}
          >
            {sending ? "Überarbeite…" : "↻ Änderungen senden"}
          </button>
          <button
            class="btn btn-delete"
            onclick={handleDelete}
          >
            ✗ Verwerfen
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .draft-layout { display: flex; flex-direction: column; height: 100%; min-height: 0; }
  .draft-header { flex-shrink: 0; margin-bottom: 1rem; }
  .draft-header h2 { font-size: 1.2rem; margin: 0; color: var(--text-primary); }
  .revision-badge { font-size: 0.7rem; background: var(--accent); color: white; padding: 2px 8px; border-radius: 10px; margin-left: 0.5rem; }
  .draft-status { padding: 2rem; color: var(--text-muted); text-align: center; }
  .draft-error { padding: 0.5rem; background: #fef2f2; color: #dc2626; border-radius: 4px; font-size: 0.8rem; margin-bottom: 0.5rem; }
  .warning { padding: 0.5rem; background: #fffbeb; color: #d97706; border-radius: 4px; font-size: 0.8rem; margin-bottom: 0.5rem; }

  .draft-split { display: flex; gap: 1.5rem; flex: 1; min-height: 0; overflow: hidden; }
  .draft-preview { flex: 3; overflow-y: auto; padding: 1.5rem; background: var(--panel); border: 1px solid var(--border); border-radius: 6px; font-family: Georgia, serif; line-height: 1.7; }
  .draft-preview :global(p), .draft-preview :global(figure) { padding: 8px; margin: 8px 0; border-radius: 4px; cursor: pointer; transition: background 0.15s; border: 2px solid transparent; }
  .draft-preview :global(p:hover), .draft-preview :global(figure:hover) { background: var(--surface-alt); border-color: var(--border); }
  .draft-preview :global(.marked) { background: #e8f0fe !important; border-color: #4a90d9 !important; }

  .draft-sidebar { flex: 2; overflow-y: auto; padding: 1rem; background: var(--panel); border: 1px solid var(--border); border-radius: 6px; display: flex; flex-direction: column; gap: 0.75rem; }
  .draft-sidebar h3 { font-size: 0.85rem; color: var(--text-secondary); margin: 0; text-transform: uppercase; letter-spacing: 0.05em; }
  .hint { font-size: 0.75rem; color: var(--text-muted); text-align: center; padding: 1rem 0; }

  .marked-item { background: #f0f7ff; border: 1px solid #4a90d9; border-radius: 6px; padding: 0.75rem; }
  .badge { font-size: 0.65rem; color: #4a90d9; font-weight: 600; }
  .marked-preview { font-size: 0.7rem; color: #666; font-style: italic; margin: 0.3rem 0; }
  .field-label { font-size: 0.65rem; font-weight: 600; display: block; margin-bottom: 0.2rem; color: var(--text-secondary); }
  textarea { width: 100%; padding: 0.4rem; border: 1px solid var(--border); border-radius: 4px; font-size: 0.72rem; resize: vertical; background: var(--bg); color: var(--text-primary); box-sizing: border-box; }
  .btn-remove { background: none; border: none; color: #ef4444; font-size: 0.65rem; cursor: pointer; padding: 0; margin-top: 0.4rem; }

  .actions { display: flex; flex-direction: column; gap: 0.5rem; margin-top: auto; padding-top: 0.75rem; border-top: 1px solid var(--border); }
  .btn { width: 100%; padding: 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; cursor: pointer; border: 1px solid var(--border); transition: opacity 0.15s; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-publish { background: #16a34a; color: white; border-color: #16a34a; }
  .btn-publish:hover:not(:disabled) { background: #15803d; }
  .btn-revise { background: var(--accent); color: white; border-color: var(--accent); }
  .btn-revise:hover:not(:disabled) { background: var(--accent-hover); }
  .btn-delete { background: transparent; color: var(--text-muted); }
  .btn-delete:hover { color: #ef4444; border-color: #ef4444; }
</style>
