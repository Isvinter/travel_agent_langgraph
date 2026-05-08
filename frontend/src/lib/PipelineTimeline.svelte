<svelte:options runes />

<script lang="ts">
  import { pipelineSteps, result, runState, resetPipeline } from "./stores/pipeline";
  import { navigateTo } from "./stores/router";

  let steps = $derived($pipelineSteps);
  let res = $derived($result);
</script>

<div class="timeline-wrapper">
  {#if steps.length === 0}
    <div class="timeline-empty">
      <div class="timeline-empty-icon" aria-hidden="true">🚀</div>
      <p>Pipeline bereit. Konfiguriere die Einstellungen und starte die Generierung.</p>
    </div>
  {:else}
    {#if $runState === "done" && res}
      <div class="success-banner">
        <div class="success-icon" aria-hidden="true">🎉</div>
        <div class="success-body">
          <div class="success-title">
            {res.draft_id ? "Dein Entwurf wurde erstellt!" : "Dein Artikel wurde erfolgreich generiert!"}
          </div>
        </div>
        <div class="success-actions">
          {#if res.draft_id}
            <button class="btn-accent" onclick={() => { const id = res.draft_id ?? 0; resetPipeline(); navigateTo({ page: "draft", id }); }}>
              Entwurf ansehen
            </button>
          {:else if res.article_id}
            <button class="btn-accent" onclick={() => { const id = res.article_id ?? 0; resetPipeline(); navigateTo({ page: "article", id }); }}>
              Artikel ansehen
            </button>
          {/if}
          <button class="btn-secondary" onclick={() => { resetPipeline(); navigateTo({ page: "articles" }); }}>
            Zur Übersicht
          </button>
        </div>
      </div>
    {/if}

    <div class="timeline">
      {#each steps as step, i}
        <div class="t-step" class:active={step.status === "running"}>
          <div class="t-node">
            {#if step.status === "done"}
              <div class="t-dot done">✓</div>
            {:else if step.status === "running"}
              <div class="t-dot running"><div class="t-spinner" role="status" aria-label="In Bearbeitung"></div></div>
            {:else if step.status === "error"}
              <div class="t-dot error">✕</div>
            {:else}
              <div class="t-dot pending"></div>
            {/if}
            {#if i < steps.length - 1}
              <div class="t-line" class:done={step.status === "done"} class:pending={step.status === "pending"}></div>
            {/if}
          </div>
          <div class="t-body" class:pending={step.status === "pending"} class:error={step.status === "error"}>
            <div class="t-label">{step.label}</div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .timeline-wrapper {
    flex: 1;
    overflow-y: auto;
    padding: 0 1rem;
  }
  .timeline-empty {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
  }
  .timeline-empty-icon {
    font-size: 3rem;
    margin-bottom: 12px;
  }
  .timeline {
    max-width: 640px;
    margin: 0 auto;
    padding: 20px 0;
  }

  .success-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    background: rgba(74, 222, 128, 0.08);
    border: 1px solid rgba(74, 222, 128, 0.3);
    border-radius: var(--radius);
    padding: 14px 16px;
    margin-bottom: 20px;
    max-width: 640px;
  }
  .success-icon { font-size: 28px; flex-shrink: 0; }
  .success-body { flex: 1; }
  .success-title { font-size: 0.9rem; font-weight: 700; color: var(--success); }
  .success-actions { display: flex; gap: 6px; flex-shrink: 0; }
  .btn-accent {
    padding: 6px 12px;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: var(--radius);
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
  }
  .btn-accent:hover { background: var(--accent-hover); }
  .btn-secondary {
    padding: 6px 12px;
    background: var(--panel-2);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
  }
  .btn-secondary:hover { background: var(--border); }

  .t-step { display: flex; align-items: flex-start; gap: 12px; }
  .t-step.active .t-body {
    background: rgba(91, 140, 255, 0.06);
    border-left: 2px solid var(--accent);
    border-radius: var(--radius);
    padding: 8px 10px;
    margin: -6px -10px;
  }
  .t-step.active .t-label { color: var(--text-primary); }
  .t-body.pending { opacity: 0.45; }
  .t-body.error .t-label { color: var(--error); }

  .t-node { display: flex; flex-direction: column; align-items: center; min-width: 24px; }
  .t-dot { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; flex-shrink: 0; }
  .t-dot.done { background: var(--success); color: white; }
  .t-dot.running { background: var(--accent); }
  .t-dot.error { background: var(--error); color: white; }
  .t-dot.pending { background: var(--panel-2); border: 2px solid var(--border); }

  .t-spinner { width: 10px; height: 10px; border: 2px solid white; border-top-color: transparent; border-radius: 50%; animation: spin-timeline 1s linear infinite; }

  .t-line { width: 2px; flex: 1; min-height: 24px; background: var(--border); }
  .t-line.done { background: var(--success); opacity: 0.5; }
  .t-line.pending { opacity: 0.4; }

  .t-body { flex: 1; padding-bottom: 14px; min-width: 0; }
  .t-label { font-size: 0.82rem; font-weight: 600; color: var(--text-secondary); margin-bottom: 2px; }

  @keyframes spin-timeline { to { transform: rotate(360deg); } }
</style>
