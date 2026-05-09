<script lang="ts">
  import { toastMessages, dismissToast, type ToastMessage } from "../stores/toast";

  let messages: ToastMessage[] = $state([]);

  $effect(() => {
    const unsub = toastMessages.subscribe((msgs) => {
      messages = msgs;
    });
    return unsub;
  });

  function handleDismiss(id: number) {
    dismissToast(id);
  }

  function handleNavigate(link: string) {
    window.location.hash = link;
  }
</script>

{#if messages.length > 0}
  <div class="toast-container">
    {#each messages as msg (msg.id)}
      <div class="toast" role="alert">
        <span class="toast-message">{msg.message}</span>
        {#if msg.link && msg.linkText}
          <button class="toast-link" onclick={() => handleNavigate(msg.link!)}>
            {msg.linkText}
          </button>
        {/if}
        <button class="toast-close" onclick={() => handleDismiss(msg.id)} aria-label="Schließen">
          ✕
        </button>
      </div>
    {/each}
  </div>
{/if}

<style>
  .toast-container {
    position: fixed;
    bottom: 1rem;
    right: 1rem;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-width: 380px;
  }

  .toast {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: var(--panel-2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    animation: toast-in 0.25s ease-out;
  }

  @keyframes toast-in {
    from {
      opacity: 0;
      transform: translateY(0.5rem);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .toast-message {
    flex: 1;
    font-size: 0.85rem;
    color: var(--text-primary);
  }

  .toast-link {
    padding: 0.35rem 0.65rem;
    background: var(--accent);
    color: white;
    font-size: 0.75rem;
    font-weight: 600;
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
    white-space: nowrap;
  }

  .toast-link:hover {
    background: var(--accent-hover);
  }

  .toast-close {
    padding: 0.15rem 0.35rem;
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 0.85rem;
    cursor: pointer;
    line-height: 1;
    border-radius: var(--radius-sm);
    flex-shrink: 0;
  }

  .toast-close:hover {
    color: var(--text-primary);
    background: var(--accent-ghost);
  }
</style>
