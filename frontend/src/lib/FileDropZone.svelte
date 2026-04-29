<script lang="ts">
  import { pipeline } from "./stores/pipeline";

  interface UploadedFile {
    name: string;
    path: string;
    type: "gpx" | "image" | "txt" | "other";
  }

  let files: UploadedFile[] = $state([]);
  let dragging: boolean = $state(false);
  let gpxFile: string | null = $state(null);

  const acceptedExtensions = [".gpx", ".jpg", ".jpeg", ".png", ".txt"];

  function getFileType(name: string): UploadedFile["type"] {
    const ext = name.toLowerCase().split(".").pop() || "";
    if (ext === "gpx") return "gpx";
    if (["jpg", "jpeg", "png"].includes(ext)) return "image";
    if (ext === "txt") return "txt";
    return "other";
  }

  async function uploadFile(file: File) {
    const formData = new FormData();
    formData.append("file", file);

    try {
      const sessionId = $pipeline.sessionId;
      const res = await fetch("/api/files/upload", {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      if (!res.ok) throw new Error("Upload failed");
      const data = await res.json();
      const f: UploadedFile = {
        name: data.filename,
        path: data.path,
        type: getFileType(data.filename),
      };
      files = [...files, f];

      if (f.type === "gpx") {
        gpxFile = f.path;
      }
      return f;
    } catch (e) {
      console.error("Upload error:", e);
      return null;
    }
  }

  async function handleDrop(e: DragEvent) {
    e.preventDefault();
    dragging = false;
    if (!e.dataTransfer?.files) return;
    for (const file of e.dataTransfer.files) {
      const ext = "." + file.name.split(".").pop()?.toLowerCase();
      if (acceptedExtensions.includes(ext)) {
        await uploadFile(file);
      }
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    dragging = true;
  }

  function handleDragLeave() {
    dragging = false;
  }

  async function handleFileSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files) return;
    for (const file of input.files) {
      await uploadFile(file);
    }
    input.value = "";
  }

  async function removeFile(f: UploadedFile) {
    try {
      const sessionId = $pipeline.sessionId;
      await fetch(`/api/files/${f.name}`, {
        method: "DELETE",
        credentials: "include",
      });
    } catch (e) {
      console.error("Delete error:", e);
    }
    files = files.filter((x) => x !== f);
    if (f.type === "gpx" && gpxFile === f.path) {
      gpxFile = files.find((x) => x.type === "gpx")?.path ?? null;
    }
  }

  export function getFiles(): { gpxFile: string; imageFiles: string[]; txtFile: string | null } {
    return {
      gpxFile: gpxFile || "",
      imageFiles: files.filter((f) => f.type === "image").map((f) => f.path),
      txtFile: files.find((f) => f.type === "txt")?.path ?? null,
    };
  }
</script>

<div class="dropzone" class:active={dragging}>
  <div
    class="zone"
    ondrop={handleDrop}
    ondragover={handleDragOver}
    ondragleave={handleDragLeave}
    role="button"
    tabindex="0"
  >
    <p class="zone-text">Dateien hier ablegen</p>
    <p class="zone-hint">.gpx .jpg .png .txt</p>
    <label class="browse-btn">
      <input type="file" multiple accept=".gpx,.jpg,.jpeg,.png,.txt" onchange={handleFileSelect} hidden />
      oder auswählen
    </label>
  </div>

  {#if files.length > 0}
    <ul class="file-list">
      {#each files as f}
        <li class="file-item {f.type}">
          <span class="file-type">{f.type.toUpperCase()}</span>
          <span class="file-name">{f.name}</span>
          <button class="remove-btn" onclick={() => removeFile(f)} title="Entfernen">&times;</button>
        </li>
      {/each}
    </ul>
  {/if}

  {#if !gpxFile && files.length > 0}
    <p class="warning">Keine GPX-Datei erkannt. Eine GPX-Datei wird benötigt.</p>
  {/if}
</div>

<style>
  .dropzone {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .zone {
    border: 2px dashed var(--border);
    border-radius: 6px;
    padding: 1.5rem 1rem;
    text-align: center;
    transition: border-color 0.2s, background 0.2s;
    cursor: pointer;
  }
  .zone.active {
    border-color: var(--accent);
    background: rgba(233, 69, 96, 0.08);
  }
  .zone-text {
    font-size: 0.9rem;
    margin-bottom: 0.2rem;
  }
  .zone-hint {
    font-size: 0.7rem;
    color: var(--text-muted);
    margin-bottom: 0.6rem;
  }
  .browse-btn {
    font-size: 0.8rem;
    color: var(--accent);
    cursor: pointer;
    text-decoration: underline;
  }
  .file-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    max-height: 140px;
    overflow-y: auto;
  }
  .file-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.3rem 0.5rem;
    background: var(--surface);
    border-radius: 3px;
    font-size: 0.75rem;
  }
  .file-type {
    font-weight: bold;
    font-size: 0.65rem;
    color: var(--accent);
    min-width: 2rem;
  }
  .file-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .remove-btn {
    background: none;
    color: var(--text-muted);
    font-size: 1rem;
    padding: 0 0.25rem;
  }
  .remove-btn:hover {
    color: var(--error);
  }
  .warning {
    font-size: 0.7rem;
    color: var(--warning);
  }
</style>
