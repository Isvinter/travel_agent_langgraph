"""
Design Blogpost Service

Nimmt das rohe HTML-Fragment aus der Blog-Generierung und lässt es von
einem Ollama-Modell in ein vollständiges, gestyltes HTML-Dokument einbetten.
Rein textueller Call — keine Bilder.
"""

from typing import Optional


def _build_design_prompt(html_body: str) -> str:
    """Baut den Prompt für das Design-Modell."""
    return f"""Du bist ein Web-Designer, spezialisiert auf lesbare, elegante Reiseblogs.

Deine Aufgabe: Bette den folgenden HTML-Inhalt in ein vollständiges,
self-contained HTML-Dokument ein.

⚠️  KRITISCH — SCHEMA-INTEGRITÄT:
JEDER einzelne HTML-Tag im übergebenen Inhalt MUSS 1:1 erhalten bleiben.
Das HTML-Tag-Schema ist die Basis des Dokuments — du darfst es NICHT
antasten, verändern, ersetzen oder umstrukturieren.

FOLGENDE TRANSFORMATIONEN SIND STRENG VERBOTEN:
- ❌ <h1> oder <h2> oder <h3> in <p> umwandeln
- ❌ <p> in <div> oder <br> umwandeln
- ❌ <img> in <figure> oder <div> wrappen (das src-Attribut muss bleiben)
- ❌ <ul>/<ol>/<li> in <p> umwandeln
- ❌ <blockquote> entfernen oder in <p> umwandeln
- ❌ Textinhalt umformulieren, kürzen oder ergänzen
- ❌ Tags löschen, verschachteln oder neu anordnen

ERLAUBT ist NUR:
- ✅ Umschließendes <!DOCTYPE html>, <html>, <head>, <body> hinzufügen
- ✅ <meta>-Tags und <title> im <head> ergänzen
- ✅ EINEN <style>-Block im <head> mit allen CSS-Regeln platzieren
- ✅ Den gesamten Original-Inhalt zwischen <body>...</body> EINBETTEN

TECHNISCHE REGELN:
- Alle CSS-Regeln in EINEM <style>-Block im <head>
- Keine externen Ressourcen, keine CDN-Links, kein JavaScript
- Valides, vollständiges HTML5
- Gib NUR das HTML zurück — keine Erklärungen, keine Markdown-Fences

DESIGN-RICHTUNG:
- Lesbare, gut proportionierte Typographie (serif oder sans-serif)
- Harmonische, naturverbundene Farbpalette (Erdtöne, Waldgrün, warmes Grau)
- Zentriertes Layout mit max-width (700–900px) und ausreichend Padding
- Responsive Bilder: img {{ max-width: 100%; height: auto; }}
- Angenehme Zeilenabstände (line-height: 1.6–1.8)
- Klare visuelle Hierarchie: h1, h2, h3 deutlich unterscheidbar
- Subtile Akzente: dezente Trennlinien, Blockquote-Styling

BEISPIEL — so MUSS der Inhalt erhalten bleiben:
Input:  <h1>Titel</h1><p>Text</p><img alt="Foto" src="a.jpg">
Output: ...<body><h1>Titel</h1><p>Text</p><img alt="Foto" src="a.jpg"></body>...

---CONTENT---
{html_body}"""


def _call_ollama_text(
    prompt: str,
    model: str = "gemma4:26b-ctx128k",
    base_url: str = "http://localhost:11434",
) -> Optional[str]:
    """Ruft Ollama /api/chat für reinen Text auf (keine Bilder).

    Returns:
        Antwort-String oder None bei Fehler.
    """
    try:
        import requests

        url = f"{base_url}/api/chat"

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 16384,
            },
        }

        response = requests.post(url, json=payload, timeout=60)

        if response.status_code == 200:
            result = response.json()
            return result.get("message", {}).get("content", "")
        else:
            print(f"❌ Design Ollama API Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return None

    except requests.exceptions.ConnectionError:
        print("❌ Design: Could not connect to Ollama. Is it running? (ollama serve)")
        return None
    except Exception as e:
        print(f"❌ Design: Error calling Ollama: {e}")
        return None


def _extract_styled_html(response: str) -> Optional[str]:
    """Validiert die LLM-Antwort und bereinigt sie.

    Entfernt ggf. Markdown-Code-Fences, prüft auf <style>- und <body>-Tag.
    Gibt das bereinigte HTML zurück oder None bei Fehler.
    """
    if not response or len(response.strip()) < 100:
        print("⚠️  Design: Response zu kurz (< 100 Zeichen)")
        return None

    stripped = response.strip()

    # Markdown-Code-Fences entfernen (LLMs ignorieren die Anweisung oft)
    if stripped.startswith("```html"):
        stripped = stripped[7:]
    elif stripped.startswith("```"):
        stripped = stripped[3:]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    stripped = stripped.strip()

    if "<style>" not in stripped and "<style " not in stripped:
        print("⚠️  Design: Kein <style>-Tag in der Antwort gefunden")
        return None

    if "<body>" not in stripped and "<body " not in stripped:
        print("⚠️  Design: Kein <body>-Tag in der Antwort — CSS-only-Output erkannt")
        return None

    return stripped


def design_blogpost_service(
    html_body: str,
    model: str = "gemma4:26b-ctx128k",
) -> Optional[str]:
    """Nimmt rohes HTML-Body-Fragment und gibt gestyltes HTML-Dokument zurück.

    Args:
        html_body: Das rohe HTML-Fragment (h1, p, img, ...)
        model: Ollama-Modell-Name

    Returns:
        Vollständiges HTML-Dokument mit inline CSS, oder None bei Fehler.
        Bei None bleibt das Original-HTML erhalten.
    """
    if not html_body or not html_body.strip():
        print("⚠️  Design: Kein HTML-Body zum Stylen vorhanden")
        return None

    prompt = _build_design_prompt(html_body)
    response = _call_ollama_text(prompt, model=model)

    if response is None:
        print("⚠️  Design: Keine Antwort von Ollama — Original-HTML bleibt erhalten")
        return None

    return _extract_styled_html(response)
