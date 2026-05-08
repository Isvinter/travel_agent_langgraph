<svelte:options runes />

<script lang="ts">
  import { reviewEnabled } from "./stores/pipeline";

  let enabled = $derived($reviewEnabled);

  function toggle() {
    reviewEnabled.set(!$reviewEnabled);
  }
</script>

<div class="review-checkbox">
  <label class="checkbox-label">
    <input
      type="checkbox"
      checked={enabled}
      onchange={toggle}
    />
    <span class="checkbox-text">Entwurf vor Veröffentlichung prüfen</span>
  </label>
</div>

<style>
  .review-checkbox {
    padding: 0.25rem 0;
  }
  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    font-size: 0.72rem;
    color: var(--text-secondary);
  }
  .checkbox-label input[type="checkbox"] {
    accent-color: var(--accent);
    width: 14px;
    height: 14px;
    cursor: pointer;
  }
  .checkbox-text {
    user-select: none;
  }
</style>
