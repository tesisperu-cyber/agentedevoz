# 🎓 Generador de Marco Teórico Académico
**Powered by Groq AI — LLaMA 3.3 70B Versatile**

## 📦 Archivos del proyecto

```
marco-teorico-ia/
├── app.py                  ← Aplicación principal Streamlit
├── requirements.txt        ← Dependencias Python
├── .streamlit/
│   └── config.toml        ← Tema visual
└── README.md
```

## 🚀 Deploy en Streamlit Community Cloud (gratuito)

### 1. Sube el proyecto a GitHub
```bash
git init
git add .
git commit -m "Marco Teórico IA"
git remote add origin https://github.com/TU_USUARIO/marco-teorico-ia.git
git push -u origin main
```

### 2. Conecta con Streamlit Cloud
1. Ve a share.streamlit.io
2. New app → selecciona repositorio
3. Main file path: `app.py`
4. Deploy

### 3. (Opcional) API Key como secreto
En Settings → Secrets:
```toml
GROQ_API_KEY = "gsk_tu_clave"
```

## 💻 Ejecución local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 🔑 Obtener API Key de Groq (gratuita)
1. console.groq.com → crear cuenta
2. API Keys → Create API Key
3. Clave empieza con gsk_
