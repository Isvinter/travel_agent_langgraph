<script lang="ts">
  import { wildcardCount } from "./stores/pipeline";

  let count: number = $state(12);

  function handleInput() {
    wildcardCount.set(count);
  }
</script>

<div class="wildcard">
  <label for="wildcard-input">Max. Bilder im Artikel</label>
  <div class="wildcard-row">
    <input
      id="wildcard-input"
      type="range"
      min={4}
      max={20}
      bind:value={count}
      oninput={handleInput}
    />
    <span class="count-badge">{count}</span>
  </div>
</div>

<style>
  .wildcard {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  label {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .wildcard-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }
  input[type="range"] {
    flex: 1;
    accent-color: var(--accent);
    background: var(--bg);
    height: 4px;
    border: none;
    padding: 0;
  }
  .count-badge {
    font-size: 0.9rem;
    font-weight: bold;
    color: var(--accent);
    min-width: 2rem;
    text-align: center;
  }
</style>
