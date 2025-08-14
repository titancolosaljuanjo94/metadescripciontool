import os, io, zipfile
import streamlit as st
import pandas as pd
from openai import OpenAI
from main import extract_text_from_pdf, guess_career_name, summarize_signals, call_openai, enforce_rules, DEFAULT_MODEL

st.set_page_config(page_title="Metadescripciones por Carrera", layout="centered")

st.title("Generador de Metadescripciones (4 por carrera)")
api_key = st.text_input("OPENAI_API_KEY", type="password", value=os.getenv("OPENAI_API_KEY") or "")
model = st.text_input("Modelo", value=os.getenv("OPENAI_MODEL", DEFAULT_MODEL))
char_limit = st.number_input("Límite de caracteres", min_value=50, max_value=180, value=90, step=1)
uploaded = st.file_uploader("Sube tu .zip con PDFs por carrera", type=["zip"])

if st.button("Generar") and uploaded and api_key:
    os.environ["OPENAI_API_KEY"] = api_key
    client = OpenAI(api_key=api_key)
    zf = zipfile.ZipFile(uploaded)
    rows = []
    for fname in zf.namelist():
        if fname.lower().endswith(".pdf"):
            data = zf.read(fname)
            text = extract_text_from_pdf(data)
            if not text.strip():
                continue
            career = guess_career_name(fname, text)
            signals = summarize_signals(text)
            options = call_openai(career, signals, char_limit, model=model)
            options = enforce_rules(options, career, char_limit)
            while len(options) < 4:
                options.append(f"{career}: Descubre el plan de estudios y oportunidades. Conoce más.")
            rows.append({
                "carrera": career,
                "descripcion_1": options[0],
                "descripcion_2": options[1],
                "descripcion_3": options[2],
                "descripcion_4": options[3],
            })
    if rows:
        df = pd.DataFrame(rows).drop_duplicates(subset=["carrera"], keep="first")
        st.success("¡Listo! Descarga tu CSV abajo.")
        st.dataframe(df, use_container_width=True)
        st.download_button("Descargar CSV", df.to_csv(index=False).encode("utf-8"), "metadescripciones.csv", "text/csv")
    else:
        st.warning("No se encontraron PDFs válidos en el ZIP.")

