from pathlib import Path

from app.state import AppState
from app.services.load_tour_notes import load_tour_notes


def load_tour_notes_node(state: AppState) -> AppState:
    """Liest optionale Tour-Notizen aus /data/notes/."""
    notes_dir = str(Path(__file__).resolve().parent.parent.parent / "data" / "notes")
    state.notes = load_tour_notes(notes_dir) or None
    if state.notes:
        print(f"📝 Loaded notes ({len(state.notes)} chars)")
    else:
        print("ℹ️ No notes found (optional)")
    return state
