# Generador de Metadescripciones para Carreras

Herramienta para generar **4 metadescripciones por carrera** usando la API de OpenAI, tomando como insumo un `.zip` con PDFs (uno por carrera).

Ideal para campañas de **Google Ads (90 caracteres)** o **SEO (155 caracteres)**.

## 🚀 Requisitos
- Python 3.10+
- Clave API de OpenAI (`OPENAI_API_KEY`)

## 📦 Instalación
```bash
pip install -r requirements.txt
```

## 🔑 Configurar clave API
```bash
# macOS / Linux
export OPENAI_API_KEY="tu_api_key"

# Windows (PowerShell)
$env:OPENAI_API_KEY="tu_api_key"
```

## 🧪 Uso en CLI
```bash
python main.py --zip ./examples/carreras.zip --out ./salida/metadescripciones.csv --limit 90 --model gpt-4.1-mini
```

## 💻 Uso con interfaz web (opcional)
```bash
streamlit run streamlit_app.py
```

## 🗂 Estructura recomendada
```
metadescripciones-carreras/
├── README.md
├── requirements.txt
├── main.py
├── streamlit_app.py
└── prompts/
    └── system_prompt.txt
```

## 📝 Salida
CSV con columnas:
- `carrera`
- `descripcion_1`..`descripcion_4`
- `caracteres_1`..`caracteres_4`
- `archivo_origen`

## ❗ Notas
- Mantén tu `OPENAI_API_KEY` **fuera** del repositorio (usa variables de entorno).
- Si tus PDFs son **escaneados** (imágenes), necesitarás OCR (p. ej. `pytesseract`), no incluido aquí.

