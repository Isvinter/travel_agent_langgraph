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

  function statusColor(status: string): string {
    switch (status) {
      case "error":
        return "var(--error)";
      case "done":
      case "success":
        return "var(--success)";
      case "running":
        return "var(--accent)";
      default:
        return "var(--text-muted)";
    }
  }
</script>

<div class="output-window" bind:this={logContainer}>
  {#if ll.length === 0}
    <p class="placeholder">Die Pipeline-Ausgabe erscheint hier…</p>
  {:else}
    {#each ll as line}
      <div class="log-line">
        <span class="timestamp">{line.timestamp}</span>
        <span class="stage" style="color: {statusColor(line.status)}">{line.stage}</span>
        <span class="message">{line.message}</span>
      </div>
    {/each}
  {/if}
</div>

<style>
  .output-window {
    flex: 1;
    background: #0d0d1a;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem;
    font-size: 0.8rem;
    font-family: "JetBrains Mono", "Fira Code", monospace;
    overflow-y: auto;
    line-height: 1.6;
  }
  .placeholder {
    color: var(--text-muted);
    font-style: italic;
  }
  .log-line {
    display: flex;
    gap: 0.75rem;
    padding: 0.15rem 0;
  }
  .timestamp {
    color: var(--text-muted);
    min-width: 4.5rem;
    flex-shrink: 0;
  }
  .stage {
    font-weight: bold;
    min-width: 11rem;
    flex-shrink: 0;
  }
  .message {
    word-break: break-word;
  }
</style>
