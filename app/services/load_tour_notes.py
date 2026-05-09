"""Load unsorted tour notes from /data/notes/."""

import os


def load_tour_notes(absolute_notes_dir: str) -> str:
    """Liest alle .txt-Dateien in absolute_notes_dir und verknüpft sie zu einem Text."""
    if not os.path.isdir(absolute_notes_dir):
        return ""

    parts: list[str] = []
    for filename in sorted(os.listdir(absolute_notes_dir)):
        if filename.endswith(".txt"):
            filepath = os.path.join(absolute_notes_dir, filename)
            with open(filepath, encoding='utf-8') as f:
                parts.append(f"### {filename}\n{f.read()}")

    return "\n\n".join(parts)
