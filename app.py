import streamlit as st
from groq import Groq
from audio_recorder_streamlit import audio_recorder
import io, base64, tempfile, os, asyncio, hashlib, tempfile

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Agente de Voz · Groq", page_icon="🎙️", layout="centered")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Syne', sans-serif; }
.stApp { background: #0a0a0f; }
.chat-user {
  background:#1c1c28; border:1px solid rgba(124,106,255,0.3);
  border-radius:16px 4px 16px 16px; padding:12px 16px;
  margin:6px 0; color:#e8e8f0; font-size:14px; line-height:1.6;
}
.chat-assistant {
  background:#12121a; border:1px solid #2a2a3d;
  border-radius:4px 16px 16px 16px; padding:12px 16px;
  margin:6px 0; color:#e8e8f0; font-size:14px; line-height:1.6;
}
.role-label {
  font-family:'Space Mono',monospace; font-size:10px;
  letter-spacing:2px; text-transform:uppercase; margin-bottom:4px;
}
.role-user      { color:#ff6a9a; }
.role-assistant { color:#7c6aff; }
.heard-box {
  background:#12121a; border:1px solid #2a2a3d; border-radius:10px;
  padding:8px 14px; font-family:'Space Mono',monospace; font-size:12px;
  color:#7878a0; margin:8px 0;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
def _init(key, val):
    if key not in st.session_state:
        st.session_state[key] = val

_init("messages",        [])
_init("groq_client",     None)
_init("last_audio_hash", None)   # evita reprocesar mismo audio
_init("last_text_sent",  None)   # evita duplicado en reruns de form
_init("pending_audio",   None)   # bytes del mp3 listo para reproducir
_init("pending_audio_id","")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;padding:16px 0 8px">
  <div style="display:inline-block;background:#12121a;border:1px solid #2a2a3d;
       border-radius:100px;padding:4px 16px;font-family:'Space Mono',monospace;
       font-size:11px;color:#7c6aff;letter-spacing:2px;margin-bottom:12px;">
    ● GROQ · LLAMA 3.3 · 70B
  </div>
  <h1 style="color:#e8e8f0;font-size:34px;margin:0;letter-spacing:-1px;">🎙️ Agente de Voz</h1>
  <p style="color:#7878a0;font-family:'Space Mono',monospace;font-size:11px;margin-top:4px;">
    Habla o escribe · Responde por voz y texto
  </p>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 Groq API Key")
    api_key = st.text_input("", type="password", placeholder="gsk_...", label_visibility="collapsed")
    if api_key:
        st.session_state.groq_client = Groq(api_key=api_key)
        st.success("✓ Conectado")

    st.markdown("---")
    st.markdown("### 🤖 Modelo")
    model = st.selectbox("", [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "llama3-70b-8192",
        "llama3-8b-8192",
    ], label_visibility="collapsed")

    st.markdown("---")
    st.markdown("### 🔊 Voz")
    tts_on = st.toggle("Respuesta por audio", value=True)
    voice_map = {
        "🇲🇽 Jorge (México)"   : "es-MX-JorgeNeural",
        "🇲🇽 Dalia (México)"   : "es-MX-DaliaNeural",
        "🇪🇸 Alvaro (España)"  : "es-ES-AlvaroNeural",
        "🇪🇸 Elvira (España)"  : "es-ES-ElviraNeural",
        "🇦🇷 Tomas (Argentina)": "es-AR-TomasNeural",
        "🇵🇪 Alex (Perú)"      : "es-PE-AlexNeural",
    }
    voice_name = voice_map[st.selectbox("", list(voice_map.keys()), label_visibility="collapsed")]
    tts_rate   = st.select_slider("Velocidad", ["-20%","-10%","+0%","+10%","+20%"], value="+0%")

    st.markdown("---")
    st.markdown("### 💬 Sistema")
    system_prompt = st.text_area("", label_visibility="collapsed", height=100,
        value="Eres un asistente de voz amigable. Responde en español, de forma clara y concisa, en párrafos breves.")

    st.markdown("---")
    if st.button("🗑️ Limpiar", use_container_width=True):
        for k in ["messages","last_audio_hash","last_text_sent","pending_audio","pending_audio_id"]:
            st.session_state[k] = [] if k == "messages" else None
        st.rerun()

# ── TTS: genera MP3 completo antes de reproducir ──────────────────────────────
async def _tts_async(text: str, voice: str, rate: str) -> bytes:
    """Descarga todo el audio antes de devolverlo (sin chunks sueltos)."""
    import edge_tts
    # Guardar en archivo temporal para asegurar escritura completa
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp_path = f.name
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch="+0Hz")
    await communicate.save(tmp_path)          # ← save() completo, no stream()
    with open(tmp_path, "rb") as f:
        data = f.read()
    os.unlink(tmp_path)
    return data

def generate_tts(text: str, voice: str, rate: str) -> bytes | None:
    """Limpia el texto y genera audio MP3 completo."""
    clean = text.replace("*","").replace("_","").replace("#","").replace("`","").strip()
    # Cortar en oración completa si es muy largo
    if len(clean) > 700:
        for sep in [". ","! ","? ",", "]:
            idx = clean.rfind(sep, 0, 700)
            if idx > 200:
                clean = clean[:idx+1]
                break
        else:
            clean = clean[:700]
    try:
        # Manejar loop de asyncio en todos los entornos
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _tts_async(clean, voice, rate))
                    return future.result(timeout=15)
            else:
                return loop.run_until_complete(_tts_async(clean, voice, rate))
        except RuntimeError:
            return asyncio.run(_tts_async(clean, voice, rate))
    except Exception as e:
        st.warning(f"⚠️ Audio no disponible: {e}")
        return None

def inject_audio(audio_bytes: bytes, uid: str):
    """Inyecta el audio UNA sola vez usando uid para evitar repeats."""
    if st.session_state.pending_audio_id == uid:
        return
    b64 = base64.b64encode(audio_bytes).decode()
    st.markdown(
        f'<audio autoplay style="display:none" id="aud_{uid}">'
        f'<source src="data:audio/mpeg;base64,{b64}" type="audio/mpeg">'
        f'</audio>',
        unsafe_allow_html=True,
    )
    st.session_state.pending_audio_id = uid

# ── STT: Groq Whisper ─────────────────────────────────────────────────────────
def transcribe(audio_bytes: bytes, client: Groq) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        path = f.name
    try:
        with open(path, "rb") as f:
            r = client.audio.transcriptions.create(
                file=("audio.wav", f, "audio/wav"),
                model="whisper-large-v3",
                language="es",
                response_format="text",
            )
        return (r if isinstance(r, str) else r.text).strip()
    except Exception as e:
        st.error(f"Error STT: {e}")
        return ""
    finally:
        os.unlink(path)

# ── LLM: Groq LLaMA ───────────────────────────────────────────────────────────
def ask_llm(user_msg: str, client: Groq, mdl: str, sys: str) -> str:
    history = [{"role": "system", "content": sys}]
    for m in st.session_state.messages:
        history.append({"role": m["role"], "content": m["content"]})
    history.append({"role": "user", "content": user_msg})
    r = client.chat.completions.create(model=mdl, messages=history,
                                       max_tokens=1024, temperature=0.7)
    return r.choices[0].message.content

# ── Render historial ──────────────────────────────────────────────────────────
def render_history():
    if not st.session_state.messages:
        st.markdown("""
        <div style="text-align:center;padding:36px 0;color:#7878a0;
             font-family:'Space Mono',monospace;font-size:13px;">
          <div style="font-size:32px;opacity:0.3;margin-bottom:8px;">🤖</div>
          Inicia la conversación
        </div>""", unsafe_allow_html=True)
        return
    for m in st.session_state.messages:
        if m["role"] == "user":
            st.markdown(f'<div class="role-label role-user">👤 Tú</div>'
                        f'<div class="chat-user">{m["content"]}</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="role-label role-assistant">🤖 Agente</div>'
                        f'<div class="chat-assistant">{m["content"]}</div>',
                        unsafe_allow_html=True)

render_history()

# ── Si hay audio pendiente lo reproduce aquí (después del historial) ──────────
if st.session_state.pending_audio:
    inject_audio(
        st.session_state.pending_audio,
        f"msg_{len(st.session_state.messages)}"
    )
    st.session_state.pending_audio = None   # limpiar para no repetir

# ── Proceso central ───────────────────────────────────────────────────────────
def process(user_input: str):
    """
    Flujo:
    1. Agrega mensaje usuario al historial y hace rerun → texto visible YA
    2. En el siguiente run detecta que hay respuesta pendiente, llama LLM
    3. Agrega respuesta, genera audio, guarda en pending_audio, rerun
    4. El audio se reproduce al inicio del siguiente render
    """
    if not st.session_state.groq_client:
        st.error("⚠️ Configura tu Groq API Key.")
        return

    # Paso 1 & 2 juntos: LLM primero (rápido en Groq), luego TTS
    with st.spinner("⚡ Pensando..."):
        try:
            reply = ask_llm(user_input, st.session_state.groq_client, model, system_prompt)
        except Exception as e:
            st.error(f"Error LLM: {e}")
            return

    # Guardar texto en historial
    st.session_state.messages.append({"role": "user",      "content": user_input})
    st.session_state.messages.append({"role": "assistant", "content": reply})

    # Generar audio DESPUÉS de guardar texto (no bloquea la visualización)
    if tts_on:
        with st.spinner("🔊 Generando audio..."):
            audio = generate_tts(reply, voice_name, tts_rate)
            if audio:
                st.session_state.pending_audio = audio

    st.rerun()

# ── Tabs de entrada ───────────────────────────────────────────────────────────
st.markdown("---")
tab_voz, tab_texto = st.tabs(["🎙️  Voz", "⌨️  Texto"])

# ── VOZ ───────────────────────────────────────────────────────────────────────
with tab_voz:
    st.markdown('<div style="text-align:center;color:#7878a0;'
                'font-family:Space Mono,monospace;font-size:11px;margin:10px 0 18px">'
                'Pulsa · Habla · Suelta</div>', unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        audio_bytes = audio_recorder(
            text="", recording_color="#cc3333", neutral_color="#7c6aff",
            icon_name="microphone", icon_size="3x",
            pause_threshold=2.0, sample_rate=16000,
        )

    if audio_bytes and len(audio_bytes) > 1000:
        ahash = hashlib.md5(audio_bytes).hexdigest()
        if ahash != st.session_state.last_audio_hash:          # nuevo audio
            st.session_state.last_audio_hash = ahash
            if not st.session_state.groq_client:
                st.error("⚠️ Configura tu Groq API Key.")
            else:
                with st.spinner("🎧 Transcribiendo..."):
                    transcript = transcribe(audio_bytes, st.session_state.groq_client)
                if transcript:
                    st.markdown(f'<div class="heard-box">📝 {transcript}</div>',
                                unsafe_allow_html=True)
                    process(transcript)
                else:
                    st.warning("No se detectó voz.")

# ── TEXTO ─────────────────────────────────────────────────────────────────────
with tab_texto:
    with st.form("tf", clear_on_submit=True):
        c1, c2 = st.columns([5, 1])
        with c1:
            txt = st.text_input("", placeholder="Escribe tu pregunta...",
                                label_visibility="collapsed")
        with c2:
            send = st.form_submit_button("➤", use_container_width=True)

    if send and txt.strip():
        if txt.strip() != st.session_state.last_text_sent:     # nuevo texto
            st.session_state.last_text_sent = txt.strip()
            process(txt.strip())
