# app/services/blog_generator.py
"""
Blogpost Generator Service

Generiert Blogposts basierend auf Bildern, Geodaten und Metadaten
unter Verwendung von Ollama (Gemma4:26b) multimodalem Modell.
"""

import base64
import os
import re
from typing import List, Dict, Any, Optional
import json
from datetime import datetime


def encode_image_to_base64(image_path: str, max_size: int = 800) -> Optional[str]:
    """
    Lädt ein Bild, skaliert es falls nötig und konvertiert es zu Base64.
    
    Args:
        image_path: Pfad zum Bild
        max_size: Maximale Breite/Höhe für Resize
        
    Returns:
        Base64-encoded string oder None bei Fehler
    """
    try:
        from PIL import Image
        
        if not os.path.exists(image_path):
            print(f"⚠️ Image not found: {image_path}")
            return None
            
        with Image.open(image_path) as img:
            # Resize wenn nötig (für Token-Effizienz)
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size))
            
            # Konvertieren zu Base64
            import io
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
            
    except Exception as e:
        print(f"⚠️ Error encoding image {image_path}: {e}")
        return None


def construct_blog_post_prompt(
    images: List[Dict[str, Any]],
    map_image_path: Optional[str] = None,
    gpx_stats: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Konstruiert den Prompt für das multimodale Modell.
    
    Args:
        images: Liste von Bild-Dictionaries mit path, timestamp, lat, lon
        map_image_path: Pfad zur generierten Übersichtskarte
        gpx_stats: GPX-Statistiken (Distanz, Höhe, etc.)
        notes: Optional: Unsortierte Notizen zur Tour
        
    Returns:
        Tuple von (text_prompt, list_of_messages_for_ollama)
    """
    
    # Header für den Prompt
    text_prompt = """
Du bist ein erfahrener Backpacker und Reiseblogger mit lockerem, authentischem Schreibstil.
Deine Aufgabe ist es, einen spannenden Blogpost über eine Tour zu verfassen.

HIER SIND DIE DATEN ZUR TOUR:
"""
    
    # GPX-Statistiken hinzufügen
    if gpx_stats:
        text_prompt += f"""
📊 TOUR-STATISTIKEN:
- Distanz: {gpx_stats.get('total_distance', 0):.2f} km
- Gesamtzeit: {gpx_stats.get('total_time', 'N/A')}
- Höhentour: {gpx_stats.get('total_elevation_gain', 0):.0f} m auf, {gpx_stats.get('total_elevation_loss', 0):.0f} m ab
- Start: {gpx_stats.get('start_time', 'N/A')}
- Ziel: {gpx_stats.get('end_time', 'N/A')}
"""
    
    # Notizen hinzufügen (später)
    if notes:
        text_prompt += f"""
📝 NOTIZEN ZUR TOUR:
{notes}
"""
    
    # Hauptanweisung
    text_prompt += """
DEINE AUFGABE:

1. **BILDAUSWAHL**: Wähle 5-7 der besten Bilder aus, die den Blogpost visuell unterstützen.
   
2. **BESCHREIBUNGEN**: Schreibe für jedes ausgewählte Bild eine kurze, passende Beschreibung 
   (1-2 Sätze), die den Inhalt beschreibt und emotional zum Text passt. Diese Beschreibungen 
   werden später als Bildunterschriften mit besonderer Schriftart unter dem Bild angezeigt.

3. **TEXTFLUSS**: Integriere die Bilder organisch in den Text. Referenziere sie natürlich 
   (z.B. "Wie man auf dem nächsten Bild sieht...", "Hier ein Blick auf...", "Das hier zeigt...").
   
4. **STIL**: Locker, persönlich, backpacker-tauglich. Nutze "wir" statt "ich", wenn möglich.
   Mach den Leser neugierig und emotional abholen.

5. **STRUKTUR**: 
   - Einleitung (Hintergrund, Warum diese Tour?)
   - Hauptteil (die Tour selbst, Highlights, Challenges)
   - Bilder organisch eingebaut mit Referenzen
   - Fazit/Ergebnis

6. **FORMAT**: Gib NUR den Markdown-Text des Blogposts zurück. Keine Einleitung, keine "MARKDOWN FORMAT" Überschriften, kein abschließender Kommentar.

   Nutze für Bilder folgendes Format im Text:
   ![Beschreibung](pfad/zum/bild)

HIER SIND DIE VERFÜGBAREN BILDER:
"""
    
    # Bilder-Informationen hinzufügen
    available_images = []
    for idx, img in enumerate(images, 1):
        img_info = {
            "id": idx,
            "path": img.get("path", ""),
            "timestamp": img.get("timestamp", "Unbekannt"),
            "location": f"{img.get('latitude', 0):.6f}, {img.get('longitude', 0):.6f}" if img.get("latitude") else "Keine Geodaten"
        }
        available_images.append(img_info)
        text_prompt += f"\nBild {idx}: {img_info['location']} ({img_info['timestamp']})"
    
    text_prompt += """
  
BEGINNE JETZT MIT DEM BLOGPOST!
"""
    
    # Messages für Ollama konstruieren (multimodal)
    messages = []
    
    # Text-Prompt als erster Message
    messages.append({
        "role": "user",
        "content": text_prompt
    })
    
    # Bilder hinzufügen (als separate messages oder im content array)
    # Ollama Qwen2.5 unterstützt multimodal inputs
    image_messages = []
    for img in available_images:
        base64_image = encode_image_to_base64(img["path"])
        if base64_image:
            image_messages.append({
                "image": base64_image,
                "id": img["id"],
                "path": img["path"],
                "timestamp": img["timestamp"],
                "location": img["location"]
            })
    
    # Map Image hinzufügen falls vorhanden
    if map_image_path and os.path.exists(map_image_path):
        map_base64 = encode_image_to_base64(map_image_path)
        if map_base64:
            image_messages.insert(0, {  # Map zuerst
                "image": map_base64,
                "id": "map",
                "path": map_image_path,
                "type": "overview_map"
            })
    
    return text_prompt, image_messages


def call_ollama_multimodal(
    prompt: str,
    images: List[Dict[str, Any]],
    model: str = "gemma4:26b",
    base_url: str = "http://localhost:11434"
) -> Optional[str]:
    """
    Ruft Ollama multimodales Modell auf und generiert Blogpost.
    
    Args:
        prompt: Text-Prompt
        images: Liste von Bildern mit Base64-Encoding
        model: Modell-Name (z.B. gemma4:26b)
        base_url: Ollama API URL
        
    Returns:
        Generierter Blogpost oder None bei Fehler
    """
    
    try:
        import requests
        
        # Ollama API Endpoint für chat (besser für multimodal)
        url = f"{base_url}/api/chat"
        
        # Vorbereitung des Requests
        # Ollama multimodal: Bilder als Top-Level "images" Key innerhalb der Message
        image_b64 = [img["image"] for img in images]

        messages_payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": image_b64,
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 4096  # Längere Antworten erlauben
            }
        }
        
        # Request senden
        response = requests.post(url, json=messages_payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            return result.get("message", {}).get("content", "")
        else:
            print(f"❌ Ollama API Error: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Ollama. Is it running? (ollama serve)")
        return None
    except Exception as e:
        print(f"❌ Error calling Ollama: {e}")
        return None


def generate_blog_post(
    images: List[Dict[str, Any]],
    map_image_path: Optional[str] = None,
    gpx_stats: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
    model: str = "gemma4:26b"
) -> Dict[str, Any]:
    """
    Hauptfunktion: Generiert einen kompletten Blogpost und speichert ihn als .md und .html Datei.
    
    Args:
        images: Liste von Bild-Informationen
        map_image_path: Pfad zur Übersichtskarte
        gpx_stats: GPX-Statistiken
        notes: Optionale Notizen
        model: Ollama Modell
        
    Returns:
        Dictionary mit markdown, html, selected_images, descriptions, file_paths
    """
    
    print("🤖 Constructing blog post prompt...")
    prompt, image_data = construct_blog_post_prompt(
        images=images,
        map_image_path=map_image_path,
        gpx_stats=gpx_stats,
        notes=notes
    )
    
    print(f"📸 Including {len(image_data)} images in prompt")
    
    print("📡 Sending to Ollama...")
    result = call_ollama_multimodal(prompt, image_data, model=model)
    
    if not result:
        print("❌ Failed to generate blog post")
        return {
            "success": False,
            "error": "Failed to generate blog post from Ollama",
            "markdown": "",
            "html": "",
            "selected_images": [],
            "descriptions": {},
            "file_paths": {}
        }
    
    print("✅ Blog post generated successfully!")
    
    # Datum-Uhrzeit für Dateinamen generieren
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Dateipfade relativ zum Projekt-Root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_dir = os.path.join(project_root, "output")
    md_file_path = os.path.join(output_dir, f"{timestamp}_blogpost.md")
    html_file_path = os.path.join(output_dir, f"{timestamp}_blogpost.html")

    os.makedirs(output_dir, exist_ok=True)

    # Markdown-Datei speichern
    try:
        with open(md_file_path, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"💾 Markdown saved to: {md_file_path}")
    except Exception as e:
        print(f"❌ Error saving markdown file: {e}")
        return {
            "success": False,
            "error": f"Error saving markdown file: {e}",
            "markdown": result,
            "html": "",
            "selected_images": [],
            "descriptions": {},
            "file_paths": {}
        }

    # HTML aus dem Markdown generieren und speichern
    try:
        import markdown
        html_return = markdown.markdown(result, extensions=['fenced_code', 'tables', 'sane_lists'])
        with open(html_file_path, 'w', encoding='utf-8') as f:
            f.write(html_return)
        print(f"💾 HTML saved to: {html_file_path}")
    except Exception as e:
        print(f"❌ Error saving HTML file: {e}")
        html_return = result  # Fallback

    # Ausgewählte Bilder und Beschreibungen aus dem Markdown extrahieren
    selected_images = []
    descriptions = {}
    # Passt ![Beschreibung](path/to/img.jpg)
    image_refs = re.findall(r'!\[([^\]]+)\]\(([^)]+)\)', result)
    for desc, path in image_refs:
        # Nur echte Bildpfade (Endung .jpg/.jpeg/.png), keine Platzhalter
        if re.search(r'\.(jpg|jpeg|png)', path, re.IGNORECASE):
            selected_images.append(path)
            descriptions[path] = desc

    print(f"📸 Extracted {len(selected_images)} selected images for blog post")

    return {
        "success": True,
        "markdown": result,
        "html": html_return,
        "selected_images": selected_images,
        "descriptions": descriptions,
        "file_paths": {
            "markdown": md_file_path,
            "html": html_file_path
        }
    }


# Proof of Concept: Einfache Version für ersten Test
def generate_blog_post_poc(
    images: List[Dict[str, Any]],
    map_image_path: Optional[str] = None,
    gpx_stats: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Proof-of-Concept Version: Erstellt einen simplen Blogpost.
    
    Ideal für ersten Test ohne komplexe Parsing-Logik.
    """
    
    # Vereinfachter Prompt für POC
    poc_prompt = f"""
Schreibe einen lockeren Backpacker-Blogpost über eine Tour.

TOUR-INFO:
{json.dumps(gpx_stats, indent=2, default=str) if gpx_stats else "Keine GPX-Daten verfügbar"}

VERFÜGBARE BILDER ({len(images)} Stück):
"""
    
    for idx, img in enumerate(images[:10], 1):
        poc_prompt += f"\n{idx}. {img.get('path', 'N/A')} - {img.get('timestamp', 'kein Timestamp')}"
    
    poc_prompt += """
1. ANALYSIERT DEN PROMPT:
   - Schreibe einen umfangreichen Blogpost (mindestens 1000 Wörter)
   - Nutze eine lockere, persönliche Reisejournal-Stimmung
   - Integriere GPX-Statistiken (Distanz, Höhenmeter)
   - Beschreibe emotionale Momente und Eindrücke

2. BILDER INTEGRIEREN:
   - Wähle die 5-8 besten Bilder für den Blogpost aus
   - Beschreibe jedes Bild kurz (Was ist zu sehen? Welche Stimmung?)
   - Verwende Markdown-Formatierung:
     ![Bildbeschreibung](path/to/image.jpg)
   - Ordne die Bilder chronologisch in den Text ein

3. STRUKTUR:
   - Title (H1)
   - Einleitung (persönlicher Einstieg)
   - Hauptteil (Erfahrungen, Highlights, Schwierigkeiten)
   - Fazit (Was war gut? Was war weniger gut? Empfehlung?)
   - Meta-Daten (Distanz, Zeit, Route)

4. BEISPIEL-OUTPUT-STRUKTUR:
# Mein Abenteuer im Gebirge

![Wunderschöne Berglandschaft](path/to/img1.jpg)

Ich stehe morgens um 5 Uhr auf...

![Landschaft](path/to/img2.jpg)

Am nächsten Tag...

---

## Statistiken

- **Distanz:** 8.67 km
- **Höhenmeter:** 862 m

---

## Fazit

Ein unvergessliches Erlebnis!
1. Wähle 5-7 Bilder aus
2. Schreibe einen Blogpost im lockeren Ton
3. Integriere Platzhalter für Bilder: ![Bild X](Bild_X)
4. Erkläre kurz, was jedes Bild zeigt

Format: Markdown mit klaren Abschnitten.
"""
    
    # Nur Text, keine Bilder an Modell senden (für POC einfacher)
    result = call_ollama_multimodal(poc_prompt, [], model="gemma4:26b")
    
    if result:
        return {
            "success": True,
            "markdown": result,
            "html": f"<html><body><pre>{result}</pre></body></html>",
            "note": "POC Version - Bilder müssen manuell zugeordnet werden"
        }
    else:
        return {
            "success": False,
            "error": "Generation failed",
            "markdown": "",
            "html": ""
        }