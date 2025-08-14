import os, io, zipfile, re, argparse
from pathlib import Path
from slugify import slugify
import pandas as pd
from tqdm import tqdm
from pypdf import PdfReader
from openai import OpenAI

# —— Parámetros por defecto ——
DEFAULT_CHAR_LIMIT = 90  # Usa 90 para Google Ads. Cambia a 155 para SEO.
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    text = "\n".join(parts)
    # Limpieza básica
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text).strip()
    return text

def guess_career_name(filename: str, text: str) -> str:
    # 1) por nombre de archivo
    stem = Path(filename).stem
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = stem.strip()
    # heurísticas simples
    candidates = [
        stem,
        # Busca posibles encabezados típicos
        *re.findall(r"(?:Carrera de|Escuela de|Programa de)\s+([A-Za-zÁÉÍÓÚáéíóúñÑ\s]+)", text, flags=re.IGNORECASE),
        *re.findall(r"(?:[Ll]icenciatura en|[Bb]achiller en)\s+([A-Za-zÁÉÍÓÚáéíóúñÑ\s]+)", text),
        *re.findall(r"(?i)^([A-Za-zÁÉÍÓÚáéíóúñÑ\s]{6,40})\s*\n", text)[:1]
    ]
    candidates = [c.strip() for c in candidates if len(c.strip()) >= 6]
    # Toma el mejor “look”
    career = candidates[0] if candidates else stem or "Carrera"
    # Título con mayúsculas iniciales
    career = " ".join(w.capitalize() for w in career.split())
    return career

def summarize_signals(text: str, max_chars_summary: int = 800) -> str:
    # Señales básicas: beneficios, cursos/malla, salidas, modalidad/duración, diferenciales
    # Recorte simple si el PDF es muy largo (opcional: podrías hacer chunks + resumen).
    snippet = text[:20000]
    # Heurístico: busca secciones
    sections = []
    for label in ["perfil del egresado", "malla", "plan de estudios", "salidas", "campo laboral", "duración", "modalidad", "competencias", "por qué estudiar"]:
        m = re.search(label + r".{0,400}", snippet, flags=re.IGNORECASE | re.DOTALL)
        if m:
            sections.append(m.group(0))
    base = "\n\n".join(sections) if sections else snippet[:3000]
    return base[:max_chars_summary]

def call_openai(career: str, signals: str, char_limit: int, model: str = DEFAULT_MODEL) -> list[str]:
    system_prompt = Path("prompts/system_prompt.txt").read_text(encoding="utf-8")
    user_prompt = f"""
Contexto resumido de la carrera:
---
{signals}
---

Genera 4 metadescripciones distintas para la carrera "{career}".
Límite estricto: {char_limit} caracteres (incluyendo espacios).
Una por línea, sin numeración, sin comillas.
"""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role":"system","content":system_prompt.replace("LÍMITE_DE_CARACTERES", str(char_limit))},
            {"role":"user","content":user_prompt}
        ],
        temperature=0.7,
        max_tokens=300
    )
    text = resp.choices[0].message.content.strip()
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    # Toma las primeras 4 válidas
    return lines[:4]

def length_ok(s: str, limit: int) -> bool:
    return len(s) <= limit

def too_similar(a: str, b: str) -> bool:
    # Similaridad muy simple por solapamiento de palabras
    sa = set(re.findall(r"\w+", a.lower()))
    sb = set(re.findall(r"\w+", b.lower()))
    if not sa or not sb:
        return False
    jacc = len(sa & sb) / len(sa | sb)
    return jacc >= 0.7  # umbral conservador

def dedupe_keep_first(options: list[str]) -> list[str]:
    kept = []
    for o in options:
        if any(too_similar(o, k) for k in kept):
            continue
        kept.append(o)
    return kept

def enforce_rules(options: list[str], career: str, limit: int) -> list[str]:
    clean = []
    for o in options:
        # fuerza inclusión del nombre de la carrera (si no, añade suave al inicio)
        if career.lower() not in o.lower():
            o = f"{career}: {o}"
        # recorta espacios multiples
        o = re.sub(r"\s{2,}", " ", o).strip()
        # enforce limite
        if len(o) > limit:
            o = o[:limit].rstrip()
        clean.append(o)
    clean = dedupe_keep_first(clean)
    # rellena si faltan (opcional: duplicar con pequeñas variaciones)
    while len(clean) < 4 and clean:
        v = clean[-1]
        v2 = re.sub(r"(Conoce|Descubre|Explora)", "Infórmate", v, count=1)
        if v2 == v:
            v2 = v + "."
        if len(v2) > limit:
            v2 = v2[:limit].rstrip()
        if not any(too_similar(v2, k) for k in clean):
            clean.append(v2)
        else:
            break
    return clean[:4]

def process_zip(zip_path: str, out_csv: str, char_limit: int, model: str):
    rows = []
    with zipfile.ZipFile(zip_path, 'r') as z:
        filelist = [f for f in z.namelist() if f.lower().endswith(".pdf")]
        for fname in tqdm(filelist, desc="Procesando PDFs"):
            try:
                data = z.read(fname)
                text = extract_text_from_pdf(data)
                if not text.strip():
                    continue
                career = guess_career_name(Path(fname).name, text)
                signals = summarize_signals(text)
                options = call_openai(career, signals, char_limit, model=model)
                options = [o for o in options if o]
                options = [o for o in options if length_ok(o, char_limit)]
                options = enforce_rules(options, career, char_limit)

                # asegura 4 salidas (si vinieron menos)
                while len(options) < 4:
                    options.append(f"{career}: Descubre el plan de estudios y oportunidades. Conoce más.")

                row = {
                    "carrera": career,
                    "descripcion_1": options[0],
                    "descripcion_2": options[1],
                    "descripcion_3": options[2],
                    "descripcion_4": options[3],
                    "caracteres_1": len(options[0]),
                    "caracteres_2": len(options[1]),
                    "caracteres_3": len(options[2]),
                    "caracteres_4": len(options[3]),
                    "archivo_origen": fname
                }
                rows.append(row)
            except Exception as e:
                rows.append({
                    "carrera": f"ERROR en {fname}",
                    "descripcion_1": str(e),
                    "descripcion_2": "",
                    "descripcion_3": "",
                    "descripcion_4": "",
                    "caracteres_1": 0, "caracteres_2": 0, "caracteres_3": 0, "caracteres_4": 0,
                    "archivo_origen": fname
                })

    df = pd.DataFrame(rows)
    # Orden y dedup por carrera (si hay múltiples PDFs por carrera, te quedas con el primero)
    df = df.drop_duplicates(subset=["carrera"], keep="first")
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False, encoding="utf-8")
    return out_csv

def main():
    parser = argparse.ArgumentParser(description="Genera 4 metadescripciones por carrera desde PDFs usando OpenAI.")
    parser.add_argument("--zip", required=True, help="Ruta al .zip con PDFs por carrera")
    parser.add_argument("--out", default="salida/metadescripciones.csv", help="Ruta de salida CSV")
    parser.add_argument("--limit", type=int, default=DEFAULT_CHAR_LIMIT, help="Límite de caracteres (90 Ads, 155 SEO)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modelo OpenAI (ej. gpt-4.1-mini)")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Falta OPENAI_API_KEY en el entorno.")

    out = process_zip(args.zip, args.out, args.limit, args.model)
    print(f"✅ Listo: {out}")

if __name__ == "__main__":
    main()

