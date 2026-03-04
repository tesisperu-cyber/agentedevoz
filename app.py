import streamlit as st
from groq import Groq
from audio_recorder_streamlit import audio_recorder
import io
import base64
import tempfile
import os

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agente de Voz · Groq LLaMA",
    page_icon="🎙️",
    layout="centered",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');

  html, body, [class*="css"] { font-family: 'Syne', sans-serif; }
  .stApp { background: #0a0a0f; }

  h1 { font-family: 'Syne', sans-serif; font-weight: 800; }

  .chat-user {
    background: #1c1c28;
    border: 1px solid rgba(124,106,255,0.3);
    border-radius: 16px 4px 16px 16px;
    padding: 12px 16px;
    margin: 8px 0;
    color: #e8e8f0;
    font-size: 14px;
    line-height: 1.6;
  }
  .chat-assistant {
    background: #12121a;
    border: 1px solid #2a2a3d;
    border-radius: 4px 16px 16px 16px;
    padding: 12px 16px;
    margin: 8px 0;
    color: #e8e8f0;
    font-size: 14px;
    line-height: 1.6;
  }
  .role-label {
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  .role-user { color: #ff6a9a; }
  .role-assistant { color: #7c6aff; }

  .status-box {
    background: #12121a;
    border: 1px solid #2a2a3d;
    border-radius: 12px;
    padding: 10px 14px;
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    color: #7878a0;
    text-align: center;
    margin: 10px 0;
  }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "groq_client" not in st.session_state:
    st.session_state.groq_client = None

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 20px 0 10px;">
  <div style="display:inline-block; background:#12121a; border:1px solid #2a2a3d;
       border-radius:100px; padding:5px 16px; font-family:'Space Mono',monospace;
       font-size:11px; color:#7c6aff; letter-spacing:2px; margin-bottom:14px;">
    ● GROQ · LLAMA 3.3 · 70B
  </div>
  <h1 style="color:#e8e8f0; font-size:36px; margin:0; letter-spacing:-1px;">
    🎙️ Agente de Voz
  </h1>
  <p style="color:#7878a0; font-family:'Space Mono',monospace; font-size:12px; margin-top:6px;">
    Habla o escribe · Responde por voz y texto
  </p>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Sidebar: API Key + Settings ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 Configuración")

    api_key = st.text_input(
        "Groq API Key",
        type="password",
        placeholder="gsk_xxxxxxxxxxxx",
        help="Obtén tu key gratis en console.groq.com",
    )

    if api_key:
        st.session_state.groq_client = Groq(api_key=api_key)
        st.success("✓ API Key configurada")

    st.markdown("---")
    st.markdown("### 🤖 Modelo")
    model = st.selectbox(
        "LLaMA Model",
        [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "llama3-70b-8192",
            "llama3-8b-8192",
        ],
        index=0,
    )

    st.markdown("---")
    st.markdown("### 🔊 Voz de respuesta")
    tts_enabled = st.toggle("Activar respuesta por voz", value=True)
    tts_speed = st.slider("Velocidad", 0.5, 2.0, 1.0, 0.1)

    st.markdown("---")
    st.markdown("### 💬 Sistema")
    system_prompt = st.text_area(
        "Prompt del sistema",
        value="Eres un asistente de voz inteligente y amigable. Responde en español de forma clara y concisa. Usa frases naturales y conversacionales.",
        height=100,
    )

    st.markdown("---")
    if st.button("🗑️ Limpiar conversación", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.markdown("""
    <div style='font-family:Space Mono,monospace; font-size:10px; color:#7878a0; text-align:center;'>
    📦 Groq + Whisper + gTTS<br>Deploy: Streamlit Cloud
    </div>
    """, unsafe_allow_html=True)

# ── Helper: TTS con gTTS ──────────────────────────────────────────────────────
def text_to_speech(text: str, speed: float = 1.0) -> str:
    """Genera audio base64 desde texto usando gTTS."""
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang="es", slow=(speed < 0.8))
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        audio_b64 = base64.b64encode(buf.read()).decode()
        return audio_b64
    except Exception as e:
        st.warning(f"TTS no disponible: {e}")
        return None

def autoplay_audio(audio_b64: str):
    """Reproduce audio automáticamente en el browser."""
    audio_html = f"""
    <audio autoplay style="display:none;">
      <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
    </audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

# ── Helper: STT con Groq Whisper ──────────────────────────────────────────────
def transcribe_audio(audio_bytes: bytes, client: Groq) -> str:
    """Transcribe audio usando Groq Whisper."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        with open(tmp_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=("audio.wav", f, "audio/wav"),
                model="whisper-large-v3",
                language="es",
                response_format="text",
            )
        return transcription.strip() if isinstance(transcription, str) else transcription.text.strip()
    except Exception as e:
        st.error(f"Error en transcripción: {e}")
        return ""
    finally:
        os.unlink(tmp_path)

# ── Helper: Chat con Groq LLaMA ───────────────────────────────────────────────
def chat_with_groq(user_message: str, client: Groq, model: str, system: str) -> str:
    """Envía mensaje a Groq y retorna respuesta."""
    messages = [{"role": "system", "content": system}]
    for m in st.session_state.messages:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=1024,
        temperature=0.7,
    )
    return response.choices[0].message.content

# ── Render conversation ───────────────────────────────────────────────────────
def render_messages():
    if not st.session_state.messages:
        st.markdown("""
        <div style="text-align:center; padding:40px 20px; color:#7878a0;
             font-family:'Space Mono',monospace; font-size:13px;">
          <div style="font-size:36px; margin-bottom:10px; opacity:0.4;">🤖</div>
          Inicia la conversación con voz o texto
        </div>
        """, unsafe_allow_html=True)
        return

    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="role-label role-user">👤 Tú</div>
            <div class="chat-user">{msg["content"]}</div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="role-label role-assistant">🤖 Agente</div>
            <div class="chat-assistant">{msg["content"]}</div>
            """, unsafe_allow_html=True)

render_messages()

# ── Input: Tabs voz / texto ───────────────────────────────────────────────────
st.markdown("---")

tab_voz, tab_texto = st.tabs(["🎙️  Entrada por Voz", "⌨️  Entrada por Texto"])

# ── TAB VOZ ───────────────────────────────────────────────────────────────────
with tab_voz:
    st.markdown("""
    <div style="text-align:center; color:#7878a0; font-family:'Space Mono',monospace;
         font-size:12px; margin-bottom:16px;">
      Pulsa el botón de micrófono · Habla · Suelta para enviar
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        audio_bytes = audio_recorder(
            text="",
            recording_color="#cc3333",
            neutral_color="#7c6aff",
            icon_name="microphone",
            icon_size="3x",
            pause_threshold=2.5,
            sample_rate=16000,
        )

    if audio_bytes:
        if not st.session_state.groq_client:
            st.error("⚠️ Configura tu Groq API Key en el panel lateral.")
        else:
            with st.spinner("🎧 Transcribiendo audio..."):
                transcript = transcribe_audio(audio_bytes, st.session_state.groq_client)

            if transcript:
                st.markdown(f"""
                <div class="status-box">
                  📝 Transcripción: <strong style="color:#e8e8f0">{transcript}</strong>
                </div>
                """, unsafe_allow_html=True)

                with st.spinner("⚡ Pensando..."):
                    try:
                        reply = chat_with_groq(
                            transcript,
                            st.session_state.groq_client,
                            model,
                            system_prompt,
                        )
                        st.session_state.messages.append({"role": "user", "content": transcript})
                        st.session_state.messages.append({"role": "assistant", "content": reply})

                        if tts_enabled:
                            with st.spinner("🔊 Generando voz..."):
                                audio_b64 = text_to_speech(reply, tts_speed)
                                if audio_b64:
                                    autoplay_audio(audio_b64)

                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al llamar a Groq: {e}")
            else:
                st.warning("No se detectó audio. Intenta de nuevo.")

# ── TAB TEXTO ─────────────────────────────────────────────────────────────────
with tab_texto:
    with st.form("text_form", clear_on_submit=True):
        col_input, col_btn = st.columns([5, 1])
        with col_input:
            user_text = st.text_input(
                "Escribe tu mensaje",
                placeholder="Haz una pregunta al agente...",
                label_visibility="collapsed",
            )
        with col_btn:
            submitted = st.form_submit_button("➤", use_container_width=True)

    if submitted and user_text.strip():
        if not st.session_state.groq_client:
            st.error("⚠️ Configura tu Groq API Key en el panel lateral.")
        else:
            with st.spinner("⚡ Pensando..."):
                try:
                    reply = chat_with_groq(
                        user_text.strip(),
                        st.session_state.groq_client,
                        model,
                        system_prompt,
                    )
                    st.session_state.messages.append({"role": "user", "content": user_text.strip()})
                    st.session_state.messages.append({"role": "assistant", "content": reply})

                    if tts_enabled:
                        with st.spinner("🔊 Generando voz..."):
                            audio_b64 = text_to_speech(reply, tts_speed)
                            if audio_b64:
                                autoplay_audio(audio_b64)

                    st.rerun()
                except Exception as e:
                    st.error(f"Error al llamar a Groq: {e}")
