<script lang="ts">
  import { logLines } from "./stores/pipeline";

  let logContainer: HTMLDivElement;

  let ll = $derived($logLines);

  $effect(() => {
    ll;
    if (logContainer) {
      logContainer.scrollTop = logContainer.scrollHeight;
    }
  });

  function badgeLabel(status: string): string {
    switch (status) {
      case "error":
        return "Fehler";
      case "done":
      case "success":
        return "OK";
      case "running":
        return "Läuft";
      default:
        return status || "Info";
    }
  }
</script>

<div class="output-window panel" bind:this={logContainer}>
  {#if ll.length === 0}
    <p class="placeholder">Die Pipeline-Ausgabe erscheint hier...</p>
  {:else}
    {#each ll as line}
      <div class="log-row" class:active={line.status === "running"}>
        <span class="log-time">{line.timestamp}</span>
        <span class="log-step-message">
          <span class="log-step">{line.stage}</span>
          <span class="log-message">{line.message}</span>
        </span>
        <span class="badge" class:success={line.status === "done" || line.status === "success"} class:error={line.status === "error"} class:running={line.status === "running"}>
          {badgeLabel(line.status)}
        </span>
      </div>
    {/each}
  {/if}
</div>

<style>
  .output-window {
    flex: 1;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem;
    font-size: 0.8rem;
    overflow-y: auto;
    line-height: 1.6;
  }
  .placeholder {
    color: var(--text-muted);
    font-style: italic;
  }
  .log-row {
    display: grid;
    grid-template-columns: 80px 1fr auto;
    align-items: center;
    padding: 8px 12px;
    border-radius: var(--radius-sm);
  }
  .log-row:hover {
    background: var(--panel-2);
  }
  .log-row.active {
    background: var(--row-active-bg);
  }
  .log-time {
    color: var(--text-muted);
    font-size: 12px;
  }
  .log-step-message {
    min-width: 0;
  }
  .log-step {
    color: var(--text-primary);
    font-weight: 500;
  }
  .log-message {
    color: var(--text-secondary);
    font-size: 13px;
  }
  .log-step + .log-message {
    margin-left: 0.5rem;
  }

  .badge {
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 500;
    background: var(--panel-2);
    color: var(--text-muted);
  }
  .badge.success {
    background: var(--badge-success-bg);
    color: var(--badge-success-text);
  }
  .badge.error {
    background: var(--badge-error-bg);
    color: var(--badge-error-text);
  }
  .badge.running {
    background: var(--badge-running-bg);
    color: var(--badge-running-text);
  }
</style>
