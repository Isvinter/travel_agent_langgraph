<svelte:options runes />

<script lang="ts">
  import DOMPurify from "dompurify";
  import { navigateTo } from "./stores/router";
  import { currentDraftId } from "./stores/pipeline";

  function sanitize(html: string): string {
    return DOMPurify.sanitize(html);
  }

  interface Props {
    id: number;
  }

  let { id }: Props = $props();

  interface ArticleData {
    id: number;
    title: string;
    html_content: string;
    status: string;
    revision_round: number;
    images: { image_path: string; is_map: boolean; is_elevation_profile: boolean }[];
  }

  interface MarkedBlock {
    element_type: "paragraph" | "image";
    element_index: number;
    original_content: string;
    instruction: string;
  }

  let article: ArticleData | null = $state(null);
  let loading: boolean = $state(true);
  let error: string = $state("");
  let htmlBlocks: { type: string; content: string; index: number; src?: string; alt?: string }[] = $state([]);
  let markedBlocks: MarkedBlock[] = $state([]);
  let markedIndices: Set<number> = $state(new Set());
  let revising: boolean = $state(false);
  let publishing: boolean = $state(false);
  let deleting: boolean = $state(false);
  let showDeleteConfirm: boolean = $state(false);
  let revisionResult: string = $state("");

  async function loadArticle() {
    loading = true;
    error = "";
    try {
      const res = await fetch(`/api/articles/${id}`);
      if (!res.ok) throw new Error("Artikel nicht gefunden");
      const data = await res.json();
      article = data.article;
      parseHtml(article.html_content);
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function parseHtml(html: string) {
    const blocks: typeof htmlBlocks = [];
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, "text/html");
    const body = doc.body;
    let idx = 0;

    function walk(node: Element) {
      for (const child of node.children) {
        const tag = child.tagName.toLowerCase();
        if (tag === "p") {
          const text = child.textContent?.trim() || "";
          if (text.length === 0) continue;
          blocks.push({ type: "paragraph", content: child.outerHTML, index: idx });
          child.setAttribute("data-block-index", String(idx));
          idx++;
        } else if (tag === "figure") {
          const img = child.querySelector("img");
          const figcaption = child.querySelector("figcaption");
          blocks.push({
            type: "image",
            content: child.outerHTML,
            index: idx,
            src: img?.getAttribute("src") || "",
            alt: figcaption?.textContent || img?.getAttribute("alt") || "",
          });
          child.setAttribute("data-block-index", String(idx));
          idx++;
        } else if (tag === "div" || tag === "section" || tag === "article" || tag === "main" || tag === "blockquote" || tag === "body") {
          walk(child);
        } else if (tag === "h1" || tag === "h2" || tag === "h3" || tag === "h4" || tag === "h5" || tag === "h6") {
          // Überschriften nicht markierbar, aber zählen für konsistentes Indexing
          idx++;
        }
      }
    }

    walk(body);
    htmlBlocks = blocks;
  }

  function getRenderedHtml(): string {
    const parser = new DOMParser();
    const doc = parser.parseFromString(article?.html_content || "", "text/html");
    const body = doc.body;
    let idx = 0;

    function walk(node: Element) {
      for (const child of node.children) {
        const tag = child.tagName.toLowerCase();
        if (tag === "p") {
          const text = child.textContent?.trim() || "";
          if (text.length === 0) continue;
          child.setAttribute("data-block-index", String(idx));
          if (markedIndices.has(idx)) {
            child.setAttribute("data-marked", "true");
          } else {
            child.removeAttribute("data-marked");
          }
          idx++;
        } else if (tag === "figure") {
          child.setAttribute("data-block-index", String(idx));
          if (markedIndices.has(idx)) {
            child.setAttribute("data-marked", "true");
          } else {
            child.removeAttribute("data-marked");
          }
          idx++;
        } else if (tag === "div" || tag === "section" || tag === "article" || tag === "main" || tag === "blockquote" || tag === "body") {
          walk(child);
        } else if (tag === "h1" || tag === "h2" || tag === "h3" || tag === "h4" || tag === "h5" || tag === "h6") {
          idx++;
        }
      }
    }
    walk(body);
    return body.innerHTML;
  }

  function handleBlockClick(e: MouseEvent) {
    const target = e.target as HTMLElement;
    const blockEl = target.closest("[data-block-index]") as HTMLElement | null;
    if (!blockEl) return;

    const idxAttr = blockEl.getAttribute("data-block-index");
    if (idxAttr === null) return;

    const blockIndex = parseInt(idxAttr, 10);
    const block = htmlBlocks.find(b => b.index === blockIndex);
    if (!block || block.type === "heading") return;

    if (markedIndices.has(blockIndex)) {
      markedIndices.delete(blockIndex);
      markedBlocks = markedBlocks.filter(m => m.element_index !== blockIndex);
    } else {
      markedIndices.add(blockIndex);
      const elementType = block.type === "image" ? "image" : "paragraph";
      const originalContent = block.type === "image"
        ? (block.src || block.alt || block.content)
        : block.content;
      markedBlocks = [...markedBlocks, {
        element_type: elementType,
        element_index: blockIndex,
        original_content: originalContent,
        instruction: "",
      }];
    }
    markedBlocks = [...markedBlocks];
    markedIndices = new Set(markedIndices);
  }

  function updateInstruction(index: number, value: string) {
    markedBlocks = markedBlocks.map(m =>
      m.element_index === index ? { ...m, instruction: value } : m
    );
  }

  function removeMark(index: number) {
    markedIndices.delete(index);
    markedBlocks = markedBlocks.filter(m => m.element_index !== index);
    markedBlocks = [...markedBlocks];
    markedIndices = new Set(markedIndices);
  }

  async function submitRevision() {
    if (markedBlocks.length === 0) return;
    revising = true;
    revisionResult = "";
    try {
      const res = await fetch(`/api/articles/${id}/revise`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ changes: markedBlocks }),
      });
      if (!res.ok) {
        const err = await res.json();
        revisionResult = `Fehler: ${err.detail || "Revision fehlgeschlagen"}`;
        return;
      }
      const data = await res.json();
      revisionResult = `Revision erfolgreich (Runde ${data.revision_round})`;
      if (data.html && article) {
        article.html_content = data.html;
        article.revision_round = data.revision_round;
        parseHtml(data.html);
      }
      markedBlocks = [];
      markedIndices = new Set();
    } catch (e: any) {
      revisionResult = `Fehler: ${e.message}`;
    } finally {
      revising = false;
    }
  }

  async function publishArticle() {
    publishing = true;
    revisionResult = "";
    try {
      const res = await fetch(`/api/articles/${id}/publish`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json();
        revisionResult = `Fehler: ${err.detail || "Veröffentlichung fehlgeschlagen"}`;
        return;
      }
      currentDraftId.set(null);
      navigateTo({ page: "article", id });
    } catch (e: any) {
      revisionResult = `Fehler: ${e.message}`;
    } finally {
      publishing = false;
    }
  }

  async function confirmDelete() {
    deleting = true;
    try {
      const res = await fetch(`/api/articles/${id}`, { method: "DELETE" });
      if (!res.ok) {
        revisionResult = "Fehler beim Löschen des Entwurfs";
        return;
      }
      currentDraftId.set(null);
      navigateTo({ page: "articles" });
    } catch (e: any) {
      revisionResult = `Fehler: ${e.message}`;
    } finally {
      deleting = false;
      showDeleteConfirm = false;
    }
  }

  $effect(() => {
    loadArticle();
  });
</script>

<div class="draft-review">
  {#if loading}
    <div class="state-message">Lade Entwurf...</div>
  {:else if error}
    <div class="state-message error">{error}</div>
  {:else if article}
    <div class="draft-header">
      <div class="draft-info">
        <h2>{article.title || "Entwurf ohne Titel"}</h2>
        <span class="draft-badge">Entwurf</span>
        {#if article.revision_round > 0}
          <span class="revision-badge">Revision {article.revision_round}</span>
        {/if}
      </div>
      <div class="draft-actions">
        <button
          class="btn btn-danger"
          onclick={() => showDeleteConfirm = true}
          disabled={revising || publishing || deleting}
        >Verwerfen</button>
        <button
          class="btn btn-primary"
          onclick={publishArticle}
          disabled={revising || publishing || deleting}
        >
          {#if publishing}
            <span class="spinner"></span>
            Übernehme...
          {:else}
            Beitrag übernehmen
          {/if}
        </button>
      </div>
    </div>

    <div class="draft-body">
      <!-- LINKS: Artikel -->
      <div class="article-preview">
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
      <div
        class="article-content"
        onclick={handleBlockClick}
        role="region"
        aria-label="Artikelvorschau"
      >
          {@html sanitize(getRenderedHtml())}
        </div>
      </div>

      <!-- RECHTS: Änderungs-Panel -->
      <div class="revision-panel">
        <h3>Änderungen</h3>
        <p class="panel-hint">Klicke auf Absätze oder Bilder im Artikel, um sie für Änderungen zu markieren.</p>

        {#if markedBlocks.length === 0}
          <p class="no-marks">Keine Elemente markiert.</p>
        {:else}
          <div class="marked-list">
            {#each markedBlocks as block (block.element_index)}
              <div class="marked-item">
                <div class="marked-header">
                  <span class="marked-badge">#{block.element_index}</span>
                  <span class="marked-type">{block.element_type === "image" ? "Bild" : "Absatz"}</span>
                  <button class="remove-btn" onclick={() => removeMark(block.element_index)} title="Markierung entfernen">×</button>
                </div>
                <div class="marked-content-preview">
                  {block.element_type === "image"
                    ? block.original_content.substring(0, 80)
                    : block.original_content.replace(/<[^>]+>/g, "").substring(0, 120)}
                  ...
                </div>
                <textarea
                  class="instruction-input"
                  placeholder="Anweisung für die Überarbeitung..."
                  value={block.instruction}
                  oninput={(e) => updateInstruction(block.element_index, (e.target as HTMLTextAreaElement).value)}
                  rows="3"
                ></textarea>
              </div>
            {/each}
          </div>

          <button
            class="btn btn-accent submit-btn"
            onclick={submitRevision}
            disabled={revising || markedBlocks.length === 0}
          >
            {#if revising}
              <span class="spinner"></span>
              Überarbeite...
            {:else}
              Änderungen senden
            {/if}
          </button>

          {#if revisionResult}
            <p class="revision-result" class:error={revisionResult.startsWith("Fehler")}>{revisionResult}</p>
          {/if}
        {/if}
      </div>
    </div>
  {/if}
</div>

<!-- DELETE CONFIRM DIALOG -->
{#if showDeleteConfirm}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="dialog-overlay" onclick={() => showDeleteConfirm = false} role="dialog" aria-modal="true" tabindex={-1}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="dialog-box" onclick={(e: MouseEvent) => e.stopPropagation()}>
      <p class="dialog-text">Möchtest du diesen Entwurf wirklich verwerfen?</p>
      <p class="dialog-sub">Der Entwurf wird endgültig gelöscht.</p>
      <div class="dialog-buttons">
        <button class="btn btn-secondary" onclick={() => showDeleteConfirm = false}>Abbrechen</button>
        <button class="btn btn-danger" onclick={confirmDelete} disabled={deleting}>
          {#if deleting}
            <span class="spinner"></span>
            Lösche...
          {:else}
            Endgültig verwerfen
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .draft-review {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .state-message {
    padding: 2rem;
    text-align: center;
    color: var(--text-secondary);
  }
  .state-message.error {
    color: var(--danger, #e74c3c);
  }

  .draft-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .draft-info {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    min-width: 0;
  }
  .draft-info h2 {
    font-size: 1.1rem;
    margin: 0;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .draft-badge {
    background: var(--warning, #f39c12);
    color: #fff;
    font-size: 0.65rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    flex-shrink: 0;
  }
  .revision-badge {
    background: var(--panel-2);
    color: var(--text-secondary);
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    flex-shrink: 0;
  }
  .draft-actions {
    display: flex;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .btn {
    padding: 0.4rem 1rem;
    border: none;
    border-radius: var(--radius);
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
  }
  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .btn-primary {
    background: var(--accent);
    color: #fff;
  }
  .btn-primary:hover:not(:disabled) {
    background: var(--accent-hover);
  }
  .btn-danger {
    background: transparent;
    color: var(--danger, #e74c3c);
    border: 1px solid var(--danger, #e74c3c);
  }
  .btn-danger:hover:not(:disabled) {
    background: var(--danger, #e74c3c);
    color: #fff;
  }
  .btn-secondary {
    background: var(--panel-2);
    color: var(--text-secondary);
    border: 1px solid var(--border);
  }
  .btn-secondary:hover:not(:disabled) {
    background: var(--border);
    color: var(--text-primary);
  }
  .btn-accent {
    background: var(--accent);
    color: #fff;
    width: 100%;
    margin-top: 0.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
  }
  .btn-accent:hover:not(:disabled) {
    background: var(--accent-hover);
  }

  .draft-body {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  .article-preview {
    flex: 6;
    overflow-y: auto;
    overflow-x: clip;
    padding: 1.5rem 2rem;
  }

  .article-content {
    overflow-wrap: break-word;
  }

  .article-content :global(img) {
    max-width: 100%;
    height: auto;
    display: block;
  }
  .article-content :global(figure) {
    max-width: 100%;
    box-sizing: border-box;
  }

  .article-content :global(p[data-block-index]) {
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
    border-left: 3px solid transparent;
    padding: 0.5rem 0.75rem;
    border-radius: 4px;
    margin-bottom: 0.5rem;
    background: var(--panel-2);
  }
  .article-content :global(p[data-block-index]:hover) {
    background: var(--border);
  }
  .article-content :global(p[data-marked="true"]) {
    background: rgba(52, 152, 219, 0.1);
    border-left-color: var(--accent);
  }

  .article-content :global(figure[data-block-index]) {
    cursor: pointer;
    transition: outline 0.15s, background 0.15s;
    outline: 2px solid transparent;
    border-radius: 4px;
    padding: 1rem;
    margin: 0.5rem 0;
    background: var(--panel-2);
    box-sizing: border-box;
  }
  .article-content :global(figure[data-block-index]:hover) {
    outline-color: var(--border);
    background: var(--border);
  }
  .article-content :global(figure[data-marked="true"]) {
    outline-color: var(--accent);
    background: rgba(52, 152, 219, 0.05);
  }

  .article-content :global(h1),
  .article-content :global(h2),
  .article-content :global(h3),
  .article-content :global(h4),
  .article-content :global(h5),
  .article-content :global(h6) {
    cursor: default;
  }

  .revision-panel {
    flex: 4;
    border-left: 1px solid var(--border);
    padding: 1.25rem;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    background: var(--panel);
  }
  .revision-panel h3 {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 0.25rem 0;
  }
  .panel-hint {
    font-size: 0.7rem;
    color: var(--text-muted);
    margin: 0 0 1rem 0;
  }
  .no-marks {
    font-size: 0.8rem;
    color: var(--text-muted);
    text-align: center;
    padding: 1.5rem 0;
  }

  .marked-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    flex: 1;
    overflow-y: auto;
  }
  .marked-item {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.75rem;
  }
  .marked-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.4rem;
  }
  .marked-badge {
    background: var(--accent);
    color: #fff;
    font-size: 0.6rem;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 10px;
    flex-shrink: 0;
  }
  .marked-type {
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .remove-btn {
    margin-left: auto;
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 1.1rem;
    cursor: pointer;
    padding: 0 0.25rem;
    line-height: 1;
  }
  .remove-btn:hover {
    color: var(--danger, #e74c3c);
  }
  .marked-content-preview {
    font-size: 0.72rem;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
    line-height: 1.4;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .instruction-input {
    width: 100%;
    box-sizing: border-box;
    font-size: 0.75rem;
    padding: 0.4rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--panel);
    color: var(--text-primary);
    resize: vertical;
    font-family: inherit;
  }
  .instruction-input:focus {
    outline: none;
    border-color: var(--accent);
  }
  .instruction-input::placeholder {
    color: var(--text-muted);
  }

  .submit-btn {
    flex-shrink: 0;
  }

  .revision-result {
    font-size: 0.75rem;
    margin-top: 0.5rem;
    color: var(--accent);
  }
  .revision-result.error {
    color: var(--danger, #e74c3c);
  }

  /* DELETE DIALOG */
  .dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }
  .dialog-box {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
    max-width: 400px;
    width: 90%;
  }
  .dialog-text {
    font-size: 0.9rem;
    color: var(--text-primary);
    margin: 0 0 0.3rem 0;
    font-weight: 600;
  }
  .dialog-sub {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin: 0 0 1.25rem 0;
  }
  .dialog-buttons {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
  }

  .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    display: inline-block;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
