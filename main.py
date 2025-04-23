import streamlit as st
import google.generativeai as genai
import whisper
import os
import tempfile
import subprocess
from streamlit_mic_recorder import mic_recorder

# Load the Gemini API key from Streamlit secrets or environment variables
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    st.error("Please set the GEMINI_API_KEY in Streamlit secrets or environment variables.")
    st.stop()
genai.configure(api_key=GEMINI_API_KEY)

# Streamlit app setup
st.title("Scam Audio Detector")
st.write("Upload or record an audio file to check if it's a scam.")

# Option to choose input method
option = st.selectbox("Choose input method", ["Upload Audio", "Record Audio"])

# Function to convert audio to WAV format with proper sample rate
def convert_to_wav(audio_path, output_path):
    try:
        subprocess.run(
            ["ffmpeg", "-i", audio_path, "-acodec", "pcm_s16le", "-ar", "16000", output_path],
            check=True,
            capture_output=True,
            text=True
        )
        return output_path
    except subprocess.CalledProcessError as e:
        st.error(f"Error converting audio to WAV: {e.stderr}")
        return None
    except FileNotFoundError:
        st.error("FFmpeg is not installed or not found in PATH. Please install FFmpeg.")
        return None

# Function to transcribe audio using Whisper
def transcribe_audio(audio_path):
    try:
        # Check file size to ensure it's not empty
        file_size = os.path.getsize(audio_path)
        if file_size < 100:
            return None, "Audio file is empty or too small."
        
        model = whisper.load_model("medium")
        result = model.transcribe(audio_path, language="en")  # Adjust language as needed
        text = result["text"]
        if not text.strip():
            return None, "Transcription is empty."
        return text, None
    except Exception as e:
        return None, f"Error transcribing audio: {e}"

# Function to analyze text using Gemini API
def analyze_text(text):
    try:
        prompt = (
            f"Analyze this phone call transcription and determine if it resembles a spam call. "
            f"Look for signs like unsolicited offers, urgent language, or requests for personal information. "
            f"If the transcription is too short or lacks context, state that more information is needed. "
            f"Answer yes or no, and provide a brief explanation (1-2 sentences): {text}"
        )
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        response_text = response.text.lower()
        if "yes" in response_text:
            result = "Scam detected!"
            color = "red"
        elif "no" in response_text:
            result = "Not a scam."
            color = "green"
        else:
            result = "Unable to determine."
            color = "orange"
        explanation = response.text
        return result, explanation, color
    except Exception as e:
        st.error(f"Error analyzing text with Gemini API: {e}")
        return None, None, None

# Handle audio input based on user selection
if option == "Upload Audio":
    audio_file = st.file_uploader("Upload Audio", type=["wav", "mp3"])
    if audio_file:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as temp_file:
            temp_file.write(audio_file.getbuffer())
            temp_audio_path = temp_file.name

        # Convert to WAV if necessary
        wav_path = temp_audio_path + ".wav"
        converted_path = convert_to_wav(temp_audio_path, wav_path)
        if not converted_path:
            os.remove(temp_audio_path)
            st.stop()

        # Play the audio
        st.audio(converted_path, format='audio/wav')

        if st.button("Analyze"):
            with st.spinner("Transcribing audio..."):
                text, error = transcribe_audio(converted_path)
                if error:
                    st.error(error)
                    os.remove(temp_audio_path)
                    os.remove(converted_path)
                    st.stop()
                st.write("Transcription:", text)

            # Check transcription length
            if len(text.split()) < 5:
                st.error("Transcription is too short for analysis. Please upload a longer audio clip.")
                os.remove(temp_audio_path)
                os.remove(converted_path)
                st.stop()

            with st.spinner("Analyzing for scams..."):
                result, explanation, color = analyze_text(text)
                if result:
                    st.markdown(f"<h3 style='color:{color}'>{result}</h3>", unsafe_allow_html=True)
                    st.write("Explanation:", explanation)

        # Clean up temporary files
        os.remove(temp_audio_path)
        os.remove(converted_path)

elif option == "Record Audio":
    st.write("**Note**: Ensure your browser has microphone access. You may need to click 'Allow' when prompted.")
    audio = mic_recorder(start_prompt="Start recording", stop_prompt="Stop recording", key="mic_recorder")
    
    if audio:
        # Save recorded audio temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_file.write(audio['bytes'])
            temp_audio_path = temp_file.name

        # Debug: Check file size
        file_size = os.path.getsize(temp_audio_path)
        st.write(f"Recorded audio file size: {file_size} bytes")
        if file_size < 100:
            st.error("Recorded audio file is empty. Please ensure your microphone is working and browser permissions are granted.")
            os.remove(temp_audio_path)
            st.stop()

        # Convert to WAV with proper sample rate
        wav_path = temp_audio_path + "_converted.wav"
        converted_path = convert_to_wav(temp_audio_path, wav_path)
        if not converted_path:
            os.remove(temp_audio_path)
            st.stop()

        # Play the audio to confirm recording
        st.audio(converted_path, format='audio/wav')

        if st.button("Analyze"):
            with st.spinner("Transcribing audio..."):
                text, error = transcribe_audio(converted_path)
                if error:
                    st.error(error)
                    os.remove(temp_audio_path)
                    os.remove(converted_path)
                    st.stop()
                st.write("Transcription:", text)

            # Check transcription length
            if len(text.split()) < 5:
                st.error("Transcription is too short for analysis. Please record a longer audio clip.")
                os.remove(temp_audio_path)
                os.remove(converted_path)
                st.stop()

            with st.spinner("Analyzing for scams..."):
                result, explanation, color = analyze_text(text)
                if result:
                    st.markdown(f"<h3 style='color:{color}'>{result}</h3>", unsafe_allow_html=True)
                    st.write("Explanation:", explanation)

        # Clean up temporary files
        os.remove(temp_audio_path)
        os.remove(converted_path)

# Disclaimer
st.write("**Note**: This is a proof-of-concept application. Predictions are based on AI analysis and may not be accurate in all cases. Always use your judgment when dealing with potential scams.")