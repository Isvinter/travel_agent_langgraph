# Design Node: LLM-gesteuertes CSS-Styling für Blog-HTML

## Ziel

Ein neuer Pipeline-Schritt am Ende des Workflows, der das rohe HTML (aus
`markdown.markdown()` konvertiert) mit einem inline CSS-Stylesheet versieht. Der
Schritt ist vollständig LLM-gesteuert, eigenständig entfernbar und beeinflusst
keinen anderen Teil der Pipeline.

## Ansatz

**Approach A — LLM Full Wrapper:** Das rohe HTML-Body-Fragment wird als Ganzes
an Ollama gesendet. Das Modell erhält den Auftrag, es in ein vollständiges
HTML-Dokument mit eingebettetem `<style>`-Block einzubetten. Der Content selbst
darf nicht verändert werden.

## Architektur

### Pipeline-Position

```
... → generate_blog_post → design_blogpost → persist_article
```

Der Node sitzt zwischen Blog-Generierung und Persistierung. Entfernen bedeutet:
in `graph.py` die Kante von `generate_blog_post` direkt auf `persist_article`
zurückbiegen.

### Neue Dateien

| Datei | Rolle |
|---|---|
| `app/nodes/design_blogpost.py` | Thin Node: `AppState → AppState` |
| `app/services/design_blogpost.py` | Business Logic: Prompt-Bau, Ollama-Call, HTML-Ersetzung |

### Geänderte Dateien

| Datei | Änderung |
|---|---|
| `app/graph.py` | Node registrieren + Edge `generate_blog_post` → `design_blogpost` → `persist_article` |

### Datenfluss

```
state.blog_post["html"]   (rohes HTML-Fragment: <h1>, <p>, <img>, ...)
         ↓
  design_blogpost_service(state.blog_post["html"], state.model)
         ↓
state.blog_post["html"]   (überschrieben mit vollständigem, gestyltem HTML-Dokument)
```

`state.blog_post["markdown"]` bleibt unverändert.

## Service-Spezifikation

### `design_blogpost_service(html_body: str, model: str) -> str | None`

**Input:**
- `html_body`: Das rohe HTML-Fragment aus `markdown.markdown()`. Enthält
  elementare Tags (`h1`, `h2`, `h3`, `p`, `img`, `ul`, `ol`, `li`,
  `blockquote`, `table`, `code`, `pre`) ohne Klassen, IDs oder umschließende
  Dokumentstruktur.

**Output:**
- Ein vollständiges, self-contained HTML-Dokument mit inline `<style>`-Block,
  oder `None` bei Fehler (dann bleibt das Original-HTML erhalten).

**Prompt-Strategie (breite kreative Vorgaben):**

1. **Rolle:** "Du bist ein Web-Designer, spezialisiert auf lesbare, elegante
   Reiseblogs."
2. **Content-Constraint:** Der übergebene HTML-Inhalt darf NICHT verändert,
   umformuliert, gekürzt oder ergänzt werden. Nur die umschließende
   HTML-Struktur und CSS werden hinzugefügt.
3. **Design-Richtung:** Lesbare Typographie, harmonische Farbpalette,
   zentriertes Layout mit `max-width`, responsive Bilder, angenehme
   Zeilenabstände, klare visuelle Hierarchie (h1/h2/h3 unterscheidbar).
4. **Technische Constraints:**
   - Alle CSS-Regeln in einem `<style>`-Tag im `<head>`
   - Keine externen Ressourcen, keine CDN-Links, kein JavaScript
   - Das Dokument muss valides HTML5 sein
5. **Delimiter:** Der rohe HTML-Inhalt folgt nach einer klaren Trennlinie
   (`---CONTENT---`).

**LLM-Aufruf:**
- Nutzt denselben `http://localhost:11434/api/chat` Endpoint wie
  `blog_generator.py`
- Keine Bilder im Request — reiner Text-Call
- Timeout: 60 Sekunden
- Temperatur: 0.7 (gleiche kreative Einstellung wie Blog-Generator)

### Fehlerbehandlung

- Ollama nicht erreichbar → Warning-Log, `None` zurückgeben
- Leere oder zu kurze Antwort (< 100 Zeichen) → Warning-Log, `None` zurückgeben
- Exception beim API-Call → Warning-Log, `None` zurückgeben

In allen Fehlerfällen läuft die Pipeline normal weiter. Das rohe HTML bleibt
erhalten und wird so persistiert.

## Node-Spezifikation

```python
def design_blogpost_node(state: AppState) -> AppState:
    # Guard: kein Blog-Post oder fehlgeschlagene Generierung
    if not state.blog_post or not state.blog_post.get("success"):
        return state

    html = state.blog_post.get("html", "")
    if not html:
        return state

    styled = design_blogpost_service(html, model=state.model)
    if styled:
        state.blog_post["html"] = styled
        # Überschreibe die bestehende .html-Datei
        html_path = state.blog_post.get("file_paths", {}).get("html")
        if html_path:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(styled)

    return state
```

## Dateioperationen

- Der Service überschreibt die existierende `.html`-Datei im
  `output/<timestamp>/`-Verzeichnis mit der gestylten Version.
- Die `.md`-Datei bleibt unverändert.
- Es werden keine neuen Dateien oder Verzeichnisse angelegt.

## Constraints

- **Keine externen Accounts/Cloud-Services:** Ollama läuft lokal, kein
  Internet-Zugriff nötig.
- **Keine Abhängigkeiten zu anderen Pipeline-Schritten:** Der Node liest nur
  `state.blog_post["html"]` und `state.model`, schreibt nur
  `state.blog_post["html"]` zurück.
- **Entfernbar:** Entfernen des Nodes erfordert nur eine Edge-Änderung in
  `graph.py`, keine weiteren Code-Änderungen.

## Nicht-Ziele (Out of Scope)

- Kein JavaScript, keine Interaktivität
- Keine Dark-Mode-Unterstützung (kann später ergänzt werden)
- Keine Bild-Galerien, Lightboxen oder Slideshows
- Kein Preprocessing des HTML mit BeautifulSoup
- Keine Template-Engine (Jinja2, etc.)
- Keine CSS-Fallback-Strategie (Best-Effort)
