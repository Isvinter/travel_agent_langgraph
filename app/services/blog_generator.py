# app/services/blog_generator.py
"""
Blogpost Generator Service

Generiert Blogposts basierend auf Bildern, Geodaten und Metadaten
unter Verwendung von Ollama (wählbar) multimodalem Modell.
"""

import base64
import io
import os
import re
import shutil
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

from app.config import OLLAMA_BASE_URL, PERSONAS, LENGTH_PRESETS, OUTPUT_DIR


def _strip_thinking_tokens(text: str) -> str:
    """Entfernt Thinking-/CoT-Tokens aus dem LLM-Output."""
    text = re.sub(
        r'<(?:think|thinking)[^>]*>.*?</(?:think|thinking)\s*>',
        '',
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return text.lstrip('\n')


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

            # Konvertieren zu RGB (JPEG unterstützt kein RGBA)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Konvertieren zu Base64
            import io
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
            
    except Exception as e:
        print(f"⚠️ Error encoding image {image_path}: {e}")
        return None


def compress_image_to_jpeg(
    image_path: str,
    output_path: str,
    max_size_bytes: int = 1024 * 1024,  # 1 MB
    max_dim: int = 1200,
) -> str | None:
    """Komprimiert ein Bild auf ≤ max_size_bytes, konvertiert nach JPEG.

    Resizet zuerst auf max_dim, reduziert dann JPEG-Qualität.
    Bei Bedarf wird weiter verkleinert bis das Limit erreicht ist.
    Gibt den Pfad zur ausgegebenen Datei zurück oder None bei Fehler.
    """
    try:
        from PIL import Image, ImageOps

        if not os.path.exists(image_path):
            return None

        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")  # JPEG unterstützt kein Alpha/Kanäle

            # Mandatory: auf max_dim runterskalieren
            if max(img.size) > max_dim:
                ratio = max_dim / max(img.size)
                img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)

            w, h = img.size

            # Phase 1: JPEG-Qualität reduzieren
            quality = 85
            while quality >= 10:
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                if len(buf.getvalue()) <= max_size_bytes:
                    with open(output_path, "wb") as f:
                        f.write(buf.getvalue())
                    return output_path
                quality -= 5

            # Phase 2: weitere Grössenreduktion
            while max(w, h) > 200:
                w = int(w * 0.75)
                h = int(h * 0.75)
                resized = img.resize((w, h), Image.LANCZOS)

                buf = io.BytesIO()
                resized.save(buf, format="JPEG", quality=75, optimize=True)
                if len(buf.getvalue()) <= max_size_bytes:
                    with open(output_path, "wb") as f:
                        f.write(buf.getvalue())
                    return output_path

            # Fallback: kleinste mögliche Größe
            buf = io.BytesIO()
            img.resize((200, int(h * 200 / w))).save(
                buf, format="JPEG", quality=10, optimize=True
            )
            with open(output_path, "wb") as f:
                f.write(buf.getvalue())
            return output_path

    except Exception as e:
        print(f"⚠️ Error compressing image {image_path}: {e}")
        return None


def construct_blog_post_prompt(
    images: List[Dict[str, Any]],
    map_image_path: Optional[str] = None,
    elevation_profile_path: Optional[str] = None,
    gpx_stats: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
    image_path_prefix: str = "",
    enrichment_context: Optional[Dict[str, Any]] = None,
    weather: Any = None,
    poi_list: Optional[List[Dict[str, Any]]] = None,
    output_config: Any = None,
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Konstruiert den Prompt für das multimodale Modell.

    images: muss VORAB ausgewählte Bilder enthalten (max ~8).

    Args:
        images: Liste von Bild-Dictionaries mit path, timestamp, lat, lon
        map_image_path: relativer Pfad zur generierten Übersichtskarte
        elevation_profile_path: relativer Pfad zum Höhengraphen
        gpx_stats: GPX-Statistiken (Distanz, Höhe, etc.)
        notes: Optional: Unsortierte Notizen zur Tour

    Returns:
        Tuple von (text_prompt, list_of_messages_for_ollama)
    """

    # Header für den Prompt — Persona und Länge aus Config
    if output_config and hasattr(output_config, 'style_persona'):
        persona = PERSONAS.get(output_config.style_persona, list(PERSONAS.values())[0])
        persona_prompt = persona["prompt"]
        length = LENGTH_PRESETS.get(output_config.article_length, LENGTH_PRESETS["normal"])
        length_guidance = (
            f"UMFANG: Schreibe {length['min_words']}–{length['max_words']} Wörter. "
            f"Halte dich an diese Vorgabe — weder deutlich kürzer noch deutlich länger.\n"
        )
    else:
        # Fallback für Aufrufe ohne OutputConfig (CLI, alte Tests)
        persona_prompt = PERSONAS["mountain_veteran"]["prompt"]
        length_guidance = "UMFANG: Schreibe 650–1300 Wörter.\n"

    text_prompt = f"""{persona_prompt}

{length_guidance}
Deine Aufgabe ist es, einen Blogpost über unsere neueste Tour zu verfassen.
Schreibe nicht nur einen Bericht, sondern erzähle eine echte Geschichte!

HIER SIND DIE DATEN ZUR TOUR:
"""

    available_images = []

    # GPX-Statistiken hinzufügen
    if gpx_stats:
        text_prompt += f"""
    📊 TOUR-STATISTIKEN:
    - Distanz: {gpx_stats.get('total_distance', 0):.2f} km
    - Gesamtzeit: {gpx_stats.get('total_time', 'N/A')}
    - Höhenmeter: {gpx_stats.get('total_elevation_gain', 0):.0f} m auf, {gpx_stats.get('total_elevation_loss', 0):.0f} m ab
    - Start: {gpx_stats.get('start_time', 'N/A')}
    - Ziel: {gpx_stats.get('end_time', 'N/A')}
    """

    # Notizen hinzufügen
    if notes:
        text_prompt += f"""
    📝 NOTIZEN ZUR TOUR (Baue diese organisch als echte Erlebnisse in die Story ein):
    {notes}
    """

    # Karte und Höhengraph referenzieren
    if elevation_profile_path:
        text_prompt += "\nHIER IST DAS HÖHENPROFIL dieser Tour (wird als Bild hochgeladen):\n"
    if map_image_path:
        text_prompt += "\nHIER IST DIE ÜBERSICHTSKARTE der Route (wird als Bild hochgeladen):\n"

    # Hauptanweisung
    text_prompt += """
    DEINE AUFGABE:

    1. **TIEFE**: Nimm dir Zeit für Details. Beschreibe die Atmosphäre, das Wetter, die körperliche Anstrengung (brennende Waden bei Höhenmetern!), die Geräusche der Natur und das Gefühl der Belohnung am Ziel. "Show, don't tell!"

    2. **KARTE + HÖHENPROFIL**:
    - Übersichtskarte MUSS am Anfang des Artikels erscheinen, direkt nach der Einleitung — mit Beschreibung:
      ![Routenverlauf unserer Tour — jeder markierte Punkt ein Stück Weg](./images/00_map.png)
    - Höhengraphen MUSS am Ende des Artikels erscheinen, im Abschnitt "Hard Facts" oder "Fazit" — mit Beschreibung:
      ![Höhenprofil der Tour — jeder Anstieg und jeder Abstieg auf einen Blick](./images/00_elevation_profile.png)

    3. **BILDER & TEXTFLUSS**: Integriere die Tour-Fotos organisch als Meilensteine in die Geschichte.
    - Schreibe für JEDES Bild (auch Karte und Höhengraphen!) eine aussagekräftige Bildunterschrift IM ALT-TEXT (1-2 Sätze).
    - **WICHTIG:** Die Bildbeschreibung steht NUR im alt-Text des Bildes — schreibe sie NICHT zusätzlich als separaten Fließtext davor oder danach.
    - Leite im Fließtext kurz auf das Bild hin (z.B. "Als wir um die Ecke bogen…"), aber wiederhole NICHT die Bildbeschreibung.

    4. **TEXTFLUSS**: Mach den Leser neugierig. Nutze abwechslungsreiche Satzstrukturen und Absätze.

    5. **STRUKTUR — als Markdown-Überschriften mit ## und ###**:
    - **Ganz am Anfang MUSS ein # Haupttitel stehen** (eine Zeile mit # als erstes Zeichen).
      Beispiel: # Meine Wintertour durch die Allgäuer Alpen
    - Verwende `##` für Hauptabschnitte und `###` für Unterabschnitte.
    - Deine Abschnitte:
    - **Hook & Einleitung**: Ein packender Einstieg. Warum diese Tour? Die Vorfreude. (KEINE Überschrift nötig — Starte direkt mit dem Text.)
    - **## Die Übersicht**: Beschreibe die Route anhand der Karte. Bette die Karte ein.
    - **## Der Aufbruch**: Wie war der Start? Leichtes Einlaufen oder direkt steil?
    - **## Die Challenge**: Die Höhenmeter, Erschöpfung, Hindernisse.
    - **## Das Highlight**: Der emotionale Höhepunkt, Aussicht, Gipfelmoment.
    - **## Der Abstieg & Fazit**: Die Rückkehr, Resümee. Bette hier den Höhengraphen ein.

    6. **FORMATIERUNG (STRIKT)**:
    - Gib NUR den Markdown-Text des Blogposts zurück.
    - Keine Einleitung deinerseits, keine Metatexte, keine Kommentare.
    - Nutze ## und ### für Überschriften — MINDESTENS eine ##-Überschrift pro Abschnitt.
    - Jeder Abschnitt der Heldenreise MUSS mit einer ##-Überschrift beginnen (außer der Einleitung).
    - Nutze für Bilder EXAKT folgendes Format: ![Deine Beschreibung](pfad/zum/bild)
    - **WICHTIG:** Verwende NUR die exakten Dateipfade aus der Liste unten. Kopiere den Pfad 1:1.
      Erfinde NIEMALS eigene Pfade oder Nummern — jeder Pfad aus der Liste muss exakt verwendet werden.
    - **JEDES Bild BRAUCHT eine Beschreibung im alt-Text** (auch Karte und Höhengraphen).
      Beispiel: ![Atmosphärische Beschreibung des Bildinhalts](PFAD_AUS_DER_LISTE)

    DIE FÜR DICH AUSGEWÄHLTEN BILDER (verwende GENAU diese Pfade):
    """

    # Bilder-Informationen hinzufügen
    for idx, img in enumerate(images, 1):
        rel_path = f"{image_path_prefix}{os.path.basename(img.get('path', ''))}"
        original = img.get("original_path", img.get("path", ""))
        img_info = {
            "id": idx,
            "path": rel_path,
            "original_path": original,
            "timestamp": img.get("timestamp", "Unbekannt"),
            "location": f"{img.get('latitude', 0):.6f}, {img.get('longitude', 0):.6f}" if img.get("latitude") else "Keine Geodaten"
        }
        available_images.append(img_info)
        text_prompt += (
            f"\nBild {idx}: {img_info['timestamp']} | {img_info['location']}\n"
            f"  Pfad: {rel_path}"
        )

    text_prompt += """

    Lass die Tastatur glühen und nimm uns mit auf dieses Abenteuer! BEGINNE JETZT MIT DEM BLOGPOST:
    """

    # --- Wetter- und POI-Anreicherung ---
    if enrichment_context:
        weather_summary = enrichment_context.get("weather_summary", "")
        kept_pois = enrichment_context.get("kept_pois", [])
        discarded_fields = enrichment_context.get("discarded_weather_fields", [])

        if weather_summary:
            text_prompt += f"""

☀️  WETTER WÄHREND DER TOUR:
{weather_summary}
"""
            if discarded_fields:
                text_prompt += f"(Nicht relevante Wetterdaten wurden ausgefiltert: {', '.join(discarded_fields)})\n"

        if kept_pois:
            text_prompt += f"""
📍  INTERESSANTE ORTE ENTLANG DER ROUTE:
"""
            for poi in kept_pois:
                name = poi.get("name", "Unbekannt")
                ptype = poi.get("type", "POI")
                dist = poi.get("distance_km", "?")
                wiki = poi.get("wiki_extract", "")
                text_prompt += f"- {name} ({ptype}, {dist} km entfernt)"
                if wiki:
                    text_prompt += f": {wiki[:300]}"
                text_prompt += "\n"
    elif weather or poi_list:
        # Fallback: Rohdaten, wenn kein Review-Kontext
        if hasattr(weather, 'summary') and weather.summary:
            text_prompt += f"""

☀️  WETTER WÄHREND DER TOUR:
{weather.summary}
"""
        if poi_list:
            text_prompt += """
📍  INTERESSANTE ORTE ENTLANG DER ROUTE:
"""
            for poi in poi_list:
                name = poi.get("name", "Unbekannt")
                ptype = poi.get("type", "POI")
                dist = poi.get("distance_km", "?")
                text_prompt += f"- {name} ({ptype}, {dist} km entfernt)\n"
    # --- Ende Wetter- und POI-Anreicherung ---

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
        path_for_encode = img.get("original_path", img["path"])
        base64_image = encode_image_to_base64(path_for_encode)
        if base64_image:
            image_messages.append({
                "image": base64_image,
                "id": img["id"],
                "path": img["path"],
                "timestamp": img["timestamp"],
                "location": img["location"]
            })

    # Map Image hinzufügen falls vorhanden
    map_b64 = None
    if map_image_path and os.path.exists(map_image_path):
        map_b64 = encode_image_to_base64(map_image_path)
        if map_b64:
            image_messages.insert(0, {  # Map zuerst
                "image": map_b64,
                "id": "map",
                "path": map_image_path,
                "type": "overview_map"
            })

    # Elevationsprofil hinzufügen falls vorhanden
    elevation_b64 = None
    if elevation_profile_path and os.path.exists(elevation_profile_path):
        elevation_b64 = encode_image_to_base64(elevation_profile_path, max_size=800)
        if elevation_b64:
            image_messages.insert(1, {  # nach Map
                "image": elevation_b64,
                "id": "elevation",
                "path": elevation_profile_path,
                "type": "elevation_profile"
            })
            text_prompt += f"\n\nHIER IST DAS HÖHENPROFIL der Tour (als Bild):"

    return text_prompt, image_messages


def call_ollama_multimodal(
    prompt: str,
    images: List[Dict[str, Any]],
    model: str = "gemma4:26b-ctx128k",
    base_url: str = OLLAMA_BASE_URL,
) -> Optional[str]:
    """
    Ruft Ollama multimodales Modell auf und generiert Blogpost.
    
    Args:
        prompt: Text-Prompt
        images: Liste von Bildern mit Base64-Encoding
        model: Modell-Name (z.B. gemma4:26b-ctx128k)
        base_url: Ollama API URL
        
    Returns:
        Generierter Blogpost oder None bei Fehler
    """
    
    try:
        import requests
        
        # Ollama API Endpoint für chat (besser für multimodal)
        url = f"{base_url.rstrip('/')}/api/chat"
        
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
                "num_predict": 16384  # Längere Antworten erlauben
            }
        }
        
        # Request senden
        response = requests.post(url, json=messages_payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            return result.get("message", {}).get("content", "")
        else:
            print(f"❌ Ollama API Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
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
    elevation_profile_path: Optional[str] = None,
    gpx_stats: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
    model: str = "gemma4:26b-ctx128k",
    enrichment_context: Optional[Dict[str, Any]] = None,
    weather: Any = None,
    poi_list: Optional[List[Dict[str, Any]]] = None,
    output_config: Any = None,
) -> Dict[str, Any]:
    """
    Generiert einen kompletten Blogpost und speichert ihn als .md und .html Datei.

    images: muss VORAB ausgewählte Bilder enthalten (max ~8).
    Jedes Bild wird auf ≤1 MB komprimiert und als JPEG im Artikel-Unterverzeichnis abgelegt.
    Der Markdown verwendet relative Pfade zur ./images/ Verzeichnis.
    """
    # ---- Per-Artikel-Unterverzeichnis ----
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    article_dir = os.path.join(project_root, OUTPUT_DIR, timestamp)
    images_dir = os.path.join(article_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    image_path_prefix = f"./images/"

    # ---- GPX-Bilder (Karte, Höhengraph) in Output kopieren ----
    final_elevation_path = None
    final_map_path = None
    if elevation_profile_path and os.path.exists(elevation_profile_path):
        shutil.copy2(elevation_profile_path, os.path.join(images_dir, "00_elevation_profile.png"))
        final_elevation_path = "./images/00_elevation_profile.png"

    if map_image_path and os.path.exists(map_image_path):
        shutil.copy2(map_image_path, os.path.join(images_dir, "00_map.png"))
        final_map_path = "./images/00_map.png"

    # ---- Bilder komprimieren + Mapping erstellen ----
    path_mapping: dict[str, str] = {}  # original_path -> relative_path
    for idx, img in enumerate(images, 1):
        orig = img.get("path", "")
        if not orig or orig in path_mapping:
            continue
        basename = os.path.splitext(os.path.basename(orig))[0]
        out_name = f"{idx:02d}_{basename}.jpg"
        out_path = os.path.join(images_dir, out_name)
        if compress_image_to_jpeg(orig, out_path):
            path_mapping[orig] = f"./images/{out_name}"

    # ---- Prompt mit relativen Bildpfaden für den LLM bauen ----
    # Zuerst path_mapping auf images anwenden, damit der LLM korrekte Pfade sieht
    images_for_prompt = []
    for img in images:
        orig = img.get("path", "")
        if orig in path_mapping:
            images_for_prompt.append({**img, "path": path_mapping[orig], "original_path": orig})
        else:
            images_for_prompt.append(img)

    print("🤖 Constructing blog post prompt...")
    # Absolute Pfade für map/elevation (construct_blog_post_prompt prüft os.path.exists)
    abs_map = final_map_path or (map_image_path if map_image_path and os.path.exists(map_image_path) else None)
    prompt, image_data = construct_blog_post_prompt(
        images=images_for_prompt,
        map_image_path=abs_map,
        elevation_profile_path=elevation_profile_path,
        gpx_stats=gpx_stats,
        notes=notes,
        image_path_prefix=image_path_prefix,
        enrichment_context=enrichment_context,
        weather=weather,
        poi_list=poi_list,
        output_config=output_config,
    )
    print(f"🗺️  Map: {final_map_path or 'N/A'}, Elevation: {final_elevation_path or 'N/A'}")

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
            "file_paths": {},
        }

    print("✅ Blog post generated successfully!")

    # Thinking-Tokens entfernen
    result = _strip_thinking_tokens(result)

    # ---- Post-processing: Bildpfade im Output normalisieren ----
    # Reverse-Mapping: alle Pfade die das LLM evtl. nutzt -> relativer Pfad
    reverse_map: dict[str, str] = {}
    for orig, rel in path_mapping.items():
        reverse_map[rel] = rel
        bn = os.path.basename(orig)
        reverse_map[orig] = rel
        reverse_map[bn] = rel

    # Build forward + backward lookup for path resolution
    index_to_rel: dict[int, str] = {}
    basename_to_rel: dict[str, str] = {}
    for orig, rel in path_mapping.items():
        bn = os.path.basename(orig)
        basename_to_rel[bn.lower()] = rel
        m_idx = re.match(r'(\d+)_', bn)
        if m_idx:
            index_to_rel[int(m_idx.group(1))] = rel

    def resolve_path(path: str) -> str:
        # Exact match (full path, basename, relative path)
        if path in reverse_map:
            return reverse_map[path]
        # Case-insensitive basename lookup
        bn = os.path.basename(path).lower()
        if bn in basename_to_rel:
            return basename_to_rel[bn]
        # "Bild_N.jpg" / "photo_N.jpg" / "IMG_N.jpg" patterns
        for prefix in ("Bild", "Photo", "IMG", "Image"):
            m_fmt = re.match(
                rf'{prefix}[_\s]*(\d+)\.(jpg|jpeg|png)',
                path, re.IGNORECASE,
            )
            if m_fmt:
                idx = int(m_fmt.group(1))
                if idx in index_to_rel:
                    return index_to_rel[idx]
                break
        # Valid image extension — keep as-is (map/elevation)
        if re.search(r'\.(jpg|jpeg|png)', path, re.IGNORECASE):
            return path
        # Last resort: extract last number and try index match
        numbers = re.findall(r'(\d+)', path)
        for num_str in reversed(numbers):
            idx = int(num_str)
            if idx in index_to_rel:
                return index_to_rel[idx]
        return path

    md_images = re.findall(r'!\[([^\]]+)\]\(([^)]+)\)', result)
    for desc, path in md_images:
        resolved = resolve_path(path)
        if resolved != path:
            result = result.replace(f"![{desc}]({path})", f"![{desc}]({resolved})")

    # ---- In Artikel-Verzeichnis speichern ----
    md_file_path = os.path.join(article_dir, f"{timestamp}_blogpost.md")
    html_file_path = os.path.join(article_dir, f"{timestamp}_blogpost.html")

    try:
        with open(md_file_path, "w", encoding="utf-8") as f:
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
            "file_paths": {},
        }

    try:
        import markdown
        html_return = markdown.markdown(result, extensions=["fenced_code", "tables", "sane_lists"])
        with open(html_file_path, "w", encoding="utf-8") as f:
            f.write(html_return)
        print(f"💾 HTML saved to: {html_file_path}")
    except Exception as e:
        print(f"❌ Error saving HTML file: {e}")
        html_return = result

    selected_images = [resolve_path(p) for _, p in md_images if re.search(r'\.(jpg|jpeg|png)', p, re.IGNORECASE)]
    descriptions = {d: resolve_path(p) for d, p in md_images if re.search(r'\.(jpg|jpeg|png)', p, re.IGNORECASE)}

    print(f"📸 Extracted {len(selected_images)} selected images for blog post")

    return {
        "success": True,
        "markdown": result,
        "html": html_return,
        "selected_images": selected_images,
        "descriptions": descriptions,
        "file_paths": {
            "markdown": md_file_path,
            "html": html_file_path,
        },
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
    result = call_ollama_multimodal(poc_prompt, [], model="gemma4:26b-ctx128k")
    
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