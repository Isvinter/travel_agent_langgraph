<svelte:options runes />

<script lang="ts">
  import ModelSelector from "./lib/ModelSelector.svelte";
  import FileDropZone from "./lib/FileDropZone.svelte";
  import OutputDirInput from "./lib/OutputDirInput.svelte";
  import NotesInput from "./lib/NotesInput.svelte";
  import RunButton from "./lib/RunButton.svelte";
  import OutputWindow from "./lib/OutputWindow.svelte";

  let modelSelector: ModelSelector;
  let fileDropZone: FileDropZone;
  let outputDirInput: OutputDirInput;
  let notesInput: NotesInput;
</script>

<div class="layout">
  <aside class="sidebar">
    <h1 class="title">Travel Agent</h1>

    <ModelSelector bind:this={modelSelector} />
    <FileDropZone bind:this={fileDropZone} />
    <OutputDirInput bind:this={outputDirInput} />
    <NotesInput bind:this={notesInput} />

    <div class="run-section">
      <RunButton
        getModel={() => modelSelector.getModel()}
        getFiles={() => fileDropZone.getFiles()}
        getOutputDir={() => outputDirInput.getOutputDir()}
        getNotes={() => notesInput.getNotes()}
      />
    </div>
  </aside>

  <main class="main">
    <OutputWindow />
  </main>
</div>

<style>
  .layout {
    display: flex;
    height: 100vh;
    width: 100vw;
  }
  .sidebar {
    width: 340px;
    min-width: 340px;
    background: var(--surface);
    border-right: 1px solid var(--border);
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    overflow-y: auto;
  }
  .title {
    font-size: 1rem;
    font-weight: bold;
    color: var(--accent);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .run-section {
    margin-top: auto;
    padding-top: 0.5rem;
  }
  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 1rem;
    overflow: hidden;
  }
</style>
