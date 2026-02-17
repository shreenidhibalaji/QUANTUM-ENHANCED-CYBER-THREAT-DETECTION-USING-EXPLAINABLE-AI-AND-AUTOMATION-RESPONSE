<<<<<<< HEAD
import streamlit as st
import os
import base64
import fitz  # PyMuPDF for PDF processing
import speech_recognition as sr
from gtts import gTTS
from dotenv import load_dotenv
from deep_translator import GoogleTranslator
import google.generativeai as genai
import google.api_core.exceptions  
import langdetect
import qrcode
from io import BytesIO
from PIL import Image
import socket
import geocoder
import re
from fpdf import FPDF  # PDF generation


# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_GOOGLE_API_KEY_HERE")
genai.configure(api_key=GOOGLE_API_KEY)

# Get local IP for QR Code (Streamlit local URL)
hostname = socket.gethostname()
LOCAL_IP = socket.gethostbyname(hostname)

# Initialize session state for history & chat storage toggle
if "history" not in st.session_state:
    st.session_state.history = []
if "show_chat_storage" not in st.session_state:
    st.session_state.show_chat_storage = False  # Toggle button for chat storage

# Function to get Gemini AI response with context tracking
from deep_translator import GoogleTranslator

def get_gemini_response(question, lang="en"):
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")

        # Gather previous conversation history (last 5 exchanges for context)
        context = "\n".join(
            [f"User: {entry['query']}\nBot: {entry['response']}" for entry in st.session_state.history[-5:]]
        )

        # Restrict the chatbot to legal topics
        legal_prompt = (
            "You are a **legal expert** providing **accurate legal advice**. "
            "You should **only answer questions related to law, courts, legal procedures, rights, and justice**. "
            "If a question is **not related to law**, respond with: "
            "'I only provide information related to legal matters. Please ask a law-related question.'"
        )

        # Format query with context
        full_prompt = f"{legal_prompt}\n\nConversation so far:\n{context}\n\nUser's latest question:\n{question}\n\nProvide a response that maintains context."

        response = model.generate_content(full_prompt)
        answer = response.text if response else "Error fetching response."

        # Translate response if necessary
        return GoogleTranslator(source="auto", target=lang).translate(answer)
    
    except google.api_core.exceptions.ResourceExhausted:
        return "API quota exceeded. Please try again later."
    except Exception as e:
        return f"Error: {str(e)}"


# Speech-to-Text (STT) function
def recognize_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("Listening... Speak now.")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    try:
        return recognizer.recognize_google(audio)
    except:
        return "Could not recognize speech."

# Text-to-Speech (TTS) function
def text_to_speech(text, lang="en"):
    try:
        tts = gTTS(text=text, lang=lang)
        audio_bytes = BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        return base64.b64encode(audio_bytes.read()).decode()
    except Exception as e:
        return f"Speech Synthesis Error: {str(e)}"
# Function to split text into smaller chunks
# ✅ Place this function before summarize_pdf()
def redact_sensitive_info(text):
    """Uses Google Gemini AI to identify and redact sensitive info dynamically."""
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = f"Identify and replace any sensitive information in this text with '[REDACTED]'. Only modify sensitive details:\n\n{text}"
        response = model.generate_content(prompt)
        return response.text if response else text  # Return redacted text
    except Exception as e:
        return f"Error in redaction: {str(e)}"

# ✅ Now define summarize_pdf() after redact_sensitive_info()
def summarize_pdf(pdf_file, lang="en", redact=True):
    """Extracts and summarizes a PDF while optionally redacting sensitive info."""
    with fitz.open(stream=pdf_file.read(), filetype="pdf") as doc:
        pdf_text = "\n".join(page.get_text() for page in doc)

    # Detect Language and Translate if Needed
    detected_lang = langdetect.detect(pdf_text)
    if detected_lang != lang:
        pdf_text = GoogleTranslator(source=detected_lang, target=lang).translate(pdf_text)

    # If redaction is enabled, redact sensitive info
    sanitized_text = redact_sensitive_info(pdf_text) if redact else pdf_text

    # Send text (redacted or original) to Gemini AI for summarization
    return get_gemini_response(f"Summarize this:\n\n{sanitized_text}", lang)
#LEGAL FIRM
def get_nearby_legal_firms_and_specialists(latitude, longitude, legal_need):
    if latitude and longitude:
        legal_firms_url = f"https://www.google.com/maps/search/legal+firms/@{latitude},{longitude},15z"
        specialist_url = f"https://www.google.com/maps/search/{legal_need}+lawyer/@{latitude},{longitude},15z"
        return legal_firms_url, specialist_url
    else:
        return None, None
def generate_contract(contract_type, details):
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = f"Generate a {contract_type} contract with the following details:\n{details}"
        response = model.generate_content(prompt)
        return response.text if response else "Error generating contract."
    except Exception as e:
        return f"Error: {str(e)}"

# Function to create a PDF contract
def create_pdf(contract_text, contract_type):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(190, 10, contract_text)

    pdf_filename = f"{contract_type}_contract.pdf"
    pdf.output(pdf_filename)
    return pdf_filename

# Define functions for different contract types
def generate_nda(details):
    return generate_contract("Non-Disclosure Agreement (NDA)", details)

def generate_lease(details):
    return generate_contract("Lease Agreement", details)

def generate_employment(details):
    return generate_contract("Employment Contract", details)
def save_as_pdf(text, filename="transcription.pdf"):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(190, 10, text)

    pdf_path = f"./{filename}"
    pdf.output(pdf_path)
    return pdf_path

# Function to convert text to speech and save as audio file
def text_to_speech(text, filename="transcription_audio.mp3"):
    engine = pyttsx3.init()
    engine.save_to_file(text, filename)
    engine.runAndWait()
    return filename


def legal_dictation():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("🎙️ Speak now... AI is listening.")
        recognizer.adjust_for_ambient_noise(source)
        
        try:
            audio = recognizer.listen(source, timeout=10)  # 10s timeout
            text = recognizer.recognize_google(audio)
            return text
        except sr.WaitTimeoutError:
            return "⏳ No speech detected, please try again."
        except sr.UnknownValueError:
            return "❌ Could not understand speech."
        except sr.RequestError:
            return "⚠️ Error connecting to speech recognition service."






st.set_page_config(page_title="AI Assistant", layout="wide")

# Initialize session state for chat history and selected chat
if "history" not in st.session_state:
    st.session_state.history = []
if "selected_chat" not in st.session_state:
    st.session_state.selected_chat = None
if "new_chat" not in st.session_state:
    st.session_state.new_chat = False

# Sidebar: Chat History Management
st.sidebar.title("📜 Chat History")

# "New Chat" Button
if st.sidebar.button("➕ New Chat"):
    st.session_state.selected_chat = None  # Deselect previous chat
    st.session_state.new_chat = True  # Enable new chat mode
    st.rerun()

# Display stored chat history in the sidebar
if st.session_state.history:
    for i, item in enumerate(st.session_state.history):
        if st.sidebar.button(f"🔹 {item['query']}", key=f"chat_{i}"):
            st.session_state.selected_chat = item  # Store selected chat in session state
            st.session_state.new_chat = False  # Disable new chat mode
            st.rerun()

# Clear History Button
if st.sidebar.button("🗑️ Clear History"):
    st.session_state.history = []
    st.session_state.selected_chat = None
    st.session_state.new_chat = True  # Enable new chat mode
    st.rerun()

# Sidebar Features
st.sidebar.title("🔍 Features")
selected_tab = st.sidebar.radio(
    "Choose a feature:",
    ["💬 AI Chat", "🎙️ Voice Assistant", "📄 Summarize PDF", 
     "📱 QR Code Generator", "📍Access Nearby", "Contract Drafting", "🖊️ Legal Dictation"]
)

# Main Workspace Title
st.title("🤖 Multilingual AI Assistant")
st.divider()

# Chat Input Section (for new chats)
if st.session_state.new_chat:
    user_input = st.text_input("💬 Type your message:", "")
    if st.button("Send"):
        if user_input:
            response = f"🔍 AI Response to: {user_input}"  # Replace with actual AI function call
            chat_entry = {"query": user_input, "response": response}
            st.session_state.history.append(chat_entry)
            st.session_state.selected_chat = chat_entry
            st.session_state.new_chat = False  # Disable new chat mode
            st.rerun()

# Display selected chat on the right
if st.session_state.selected_chat:
    query = st.session_state.selected_chat['query']
    response = st.session_state.selected_chat['response']

    chat_display = f"""
    <div class="chat-display">
        <div class="chat-box query-box">🔍 {query}</div>
        <div class="chat-box response-box">💬 {response}</div>
    </div>
    """

    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    st.markdown(chat_display, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)



### 📌 CHATBOT WITH HISTORY ###
if selected_tab == "💬 AI Chat":
    st.subheader("💬 AI Chat Assistant")

    user_query = st.chat_input("Ask me anything...")

    if user_query:
        target_lang = st.selectbox("Select language:", ["en", "hi", "fr", "es", "de", "ta", "te"], key="chat_lang")

        # Placeholder for bot response animation
        placeholder = st.empty()
        placeholder.markdown(
            """
            <div style="text-align:center; font-size:24px;">
                😊 <span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
            </div>
            <style>
                @keyframes bounce {
                    0%, 100% { transform: translateY(0); }
                    50% { transform: translateY(-5px); }
                }
                .dot {
                    display: inline-block;
                    font-size: 30px;
                    animation: bounce 1.5s infinite ease-in-out alternate;
                }
                .dot:nth-child(2) { animation-delay: 0.2s; }
                .dot:nth-child(3) { animation-delay: 0.4s; }
            </style>
            """,
            unsafe_allow_html=True
        )

        # Fetch response from Gemini AI
        answer = get_gemini_response(user_query, target_lang)

        # Replace animation with actual response
        placeholder.empty()
        st.session_state.history.append({"query": user_query, "response": answer, "feature": "Chat"})

        # Styled response display
        st.markdown(f"**🧑‍💼 You:** {user_query}")
        st.markdown(f"**🤖 Bot:** {answer}")

### 🎙️ VOICE ASSISTANT ###
elif selected_tab == "🎙️ Voice Assistant":
    st.subheader("🎙️ Voice Assistant")

    target_lang = st.selectbox("Select response language:", ["en", "hi", "fr", "es", "de", "ta", "te"], key="voice_lang")

    if st.button("🎤 Start Listening"):
        voice_input = recognize_speech()
        st.text(f"You said: {voice_input}")

        if voice_input:
            answer = get_gemini_response(voice_input, target_lang)
            st.subheader("Answer")
            st.markdown(answer)

            b64_audio = text_to_speech(answer, target_lang)
            st.markdown(f'<audio controls><source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3"></audio>', unsafe_allow_html=True)

            st.session_state.history.append({"query": voice_input, "response": answer, "feature": "Voice"})


### 📄 PDF SUMMARIZATION WITH QUESTION FEATURE ###
elif selected_tab == "📄 Summarize PDF":
    st.subheader("📄 Upload a PDF for Summarization")
    
    uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
    target_lang = st.selectbox("Select language:", ["en", "hi", "fr", "es", "de", "ta", "te"])
    
    if uploaded_file and st.button("📃 Summarize"):
        summarized_text = summarize_pdf(uploaded_file, target_lang)
        st.session_state.pdf_summary = summarized_text  # Store summary in session state
        st.subheader("📜 Summary")
        st.markdown(summarized_text)

        st.session_state.history.append({"query": "PDF Summarization", "response": summarized_text, "feature": "PDF"})

    # **Ask a Question Based on the Summary**
    if "pdf_summary" in st.session_state:
        st.subheader("❓ Ask a Question about the PDF")
        user_question = st.text_input("Enter your question:")

        if user_question:
            full_context = f"Here is a summarized version of a PDF document:\n\n{st.session_state.pdf_summary}\n\nNow, answer this question based on the summary:\n{user_question}"
            answer = get_gemini_response(full_context, target_lang)
            
            st.subheader("🤖 AI's Answer")
            st.markdown(answer)

            st.session_state.history.append({"query": user_question, "response": answer, "feature": "PDF Q&A"})

### 📱 QR CODE GENERATOR ###
elif selected_tab == "📱 QR Code Generator":
    st.subheader("📱 Scan QR Code to Open App")
    
    if st.button("📷 Generate QR Code"):
        qr_image = generate_qr_code()
        img_bytes = BytesIO()
        qr_image.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        st.image(img_bytes, caption="Scan to open app", use_column_width=True)


### 📍 FIND NEARBY LEGAL FIRMS ###
elif selected_tab == "📍Access Nearby":  # Ensure exact match in sidebar
    st.subheader("📍 Find Nearby Legal Firms")

    # Store location persistently inside this section only
    if "user_location" not in st.session_state:
        st.session_state.user_location = None

    # Button to detect location
    if st.button("🔎 Detect My Location"):
        st.write("🔍 Detecting location...")  # Debugging message
        g = geocoder.ip('me')  # Fetch user location

        if g.latlng:
            st.session_state.user_location = g.latlng
            st.success(f"📍 Location Detected: {st.session_state.user_location[0]}, {st.session_state.user_location[1]}")
        else:
            st.error("❌ Could not retrieve location. Please check your internet connection.")
            st.write("Debug: Location retrieval failed, g.latlng returned None.")  # Extra debug output

    # Ensure location is retrieved before asking for legal needs
    if st.session_state.user_location:
        legal_need = st.text_input("Enter your legal need (e.g., 'divorce', 'criminal', 'corporate'):")
        
        if st.button("🔍 Find Nearby Legal Firms") and legal_need:
            latitude, longitude = st.session_state.user_location
            legal_firms_url, specialist_url = get_nearby_legal_firms_and_specialists(latitude, longitude, legal_need)

            st.markdown(f"🌍 [Nearby Legal Firms]({legal_firms_url})")
            st.markdown(f"🔎 [Specialist Lawyers for {legal_need}]({specialist_url})")
        elif not legal_need:
            st.warning("⚠️ Please enter a specific legal need.")
elif selected_tab == "Contract Drafting":
    st.subheader("📝 Generate a Legal Contract")

    contract_type = st.selectbox("Select Contract Type", ["NDA", "Lease", "Employment"])
    details = st.text_area("Enter contract details (e.g., parties involved, terms, duration)")

    if st.button("📝 Generate Contract"):
        if details:
            if contract_type == "NDA":
                contract_text = generate_nda(details)
            elif contract_type == "Lease":
                contract_text = generate_lease(details)
            elif contract_type == "Employment":
                contract_text = generate_employment(details)
            else:
                contract_text = "Invalid contract type selected."

            st.subheader("📜 Generated Contract")
            st.text_area("Contract", contract_text, height=300)

            # Save as PDF
            pdf_file = create_pdf(contract_text, contract_type)
            with open(pdf_file, "rb") as file:
                st.download_button("📥 Download Contract", file, file_name=pdf_file, mime="application/pdf")
        else:
            st.warning("⚠️ Please enter contract details.")
elif selected_tab == "🖊️ Legal Dictation":
    st.subheader("📝 Legal Dictation – Speak, and AI Writes It Down")

    if st.button("🎤 Start Dictation"):
        transcribed_text = legal_dictation()
        st.text_area("📄 Transcribed Text:", transcribed_text, height=200)

        if transcribed_text and not transcribed_text.startswith(("⏳", "❌", "⚠️")):  # Avoid errors for invalid text
            # ✅ Save as PDF
            pdf_file = save_as_pdf(transcribed_text)
            with open(pdf_file, "rb") as file:
                st.download_button("📥 Download as PDF", file, file_name="Legal_Dictation.pdf", mime="application/pdf")


=======
import streamlit as st
import os
import base64
import fitz  # PyMuPDF for PDF processing
import speech_recognition as sr
from gtts import gTTS
from dotenv import load_dotenv
from deep_translator import GoogleTranslator
import google.generativeai as genai
import google.api_core.exceptions  
import langdetect
import qrcode
from io import BytesIO
from PIL import Image
import socket
import geocoder
import re
from fpdf import FPDF  # PDF generation


# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_GOOGLE_API_KEY_HERE")
genai.configure(api_key=GOOGLE_API_KEY)

# Get local IP for QR Code (Streamlit local URL)
hostname = socket.gethostname()
LOCAL_IP = socket.gethostbyname(hostname)

# Initialize session state for history & chat storage toggle
if "history" not in st.session_state:
    st.session_state.history = []
if "show_chat_storage" not in st.session_state:
    st.session_state.show_chat_storage = False  # Toggle button for chat storage

# Function to get Gemini AI response with context tracking
from deep_translator import GoogleTranslator

def get_gemini_response(question, lang="en"):
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")

        # Gather previous conversation history (last 5 exchanges for context)
        context = "\n".join(
            [f"User: {entry['query']}\nBot: {entry['response']}" for entry in st.session_state.history[-5:]]
        )

        # Restrict the chatbot to legal topics
        legal_prompt = (
            "You are a **legal expert** providing **accurate legal advice**. "
            "You should **only answer questions related to law, courts, legal procedures, rights, and justice**. "
            "If a question is **not related to law**, respond with: "
            "'I only provide information related to legal matters. Please ask a law-related question.'"
        )

        # Format query with context
        full_prompt = f"{legal_prompt}\n\nConversation so far:\n{context}\n\nUser's latest question:\n{question}\n\nProvide a response that maintains context."

        response = model.generate_content(full_prompt)
        answer = response.text if response else "Error fetching response."

        # Translate response if necessary
        return GoogleTranslator(source="auto", target=lang).translate(answer)
    
    except google.api_core.exceptions.ResourceExhausted:
        return "API quota exceeded. Please try again later."
    except Exception as e:
        return f"Error: {str(e)}"


# Speech-to-Text (STT) function
def recognize_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("Listening... Speak now.")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    try:
        return recognizer.recognize_google(audio)
    except:
        return "Could not recognize speech."

# Text-to-Speech (TTS) function
def text_to_speech(text, lang="en"):
    try:
        tts = gTTS(text=text, lang=lang)
        audio_bytes = BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        return base64.b64encode(audio_bytes.read()).decode()
    except Exception as e:
        return f"Speech Synthesis Error: {str(e)}"
# Function to split text into smaller chunks
# ✅ Place this function before summarize_pdf()
def redact_sensitive_info(text):
    """Uses Google Gemini AI to identify and redact sensitive info dynamically."""
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = f"Identify and replace any sensitive information in this text with '[REDACTED]'. Only modify sensitive details:\n\n{text}"
        response = model.generate_content(prompt)
        return response.text if response else text  # Return redacted text
    except Exception as e:
        return f"Error in redaction: {str(e)}"

# ✅ Now define summarize_pdf() after redact_sensitive_info()
def summarize_pdf(pdf_file, lang="en", redact=True):
    """Extracts and summarizes a PDF while optionally redacting sensitive info."""
    with fitz.open(stream=pdf_file.read(), filetype="pdf") as doc:
        pdf_text = "\n".join(page.get_text() for page in doc)

    # Detect Language and Translate if Needed
    detected_lang = langdetect.detect(pdf_text)
    if detected_lang != lang:
        pdf_text = GoogleTranslator(source=detected_lang, target=lang).translate(pdf_text)

    # If redaction is enabled, redact sensitive info
    sanitized_text = redact_sensitive_info(pdf_text) if redact else pdf_text

    # Send text (redacted or original) to Gemini AI for summarization
    return get_gemini_response(f"Summarize this:\n\n{sanitized_text}", lang)
#LEGAL FIRM
def get_nearby_legal_firms_and_specialists(latitude, longitude, legal_need):
    if latitude and longitude:
        legal_firms_url = f"https://www.google.com/maps/search/legal+firms/@{latitude},{longitude},15z"
        specialist_url = f"https://www.google.com/maps/search/{legal_need}+lawyer/@{latitude},{longitude},15z"
        return legal_firms_url, specialist_url
    else:
        return None, None
def generate_contract(contract_type, details):
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = f"Generate a {contract_type} contract with the following details:\n{details}"
        response = model.generate_content(prompt)
        return response.text if response else "Error generating contract."
    except Exception as e:
        return f"Error: {str(e)}"

# Function to create a PDF contract
def create_pdf(contract_text, contract_type):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(190, 10, contract_text)

    pdf_filename = f"{contract_type}_contract.pdf"
    pdf.output(pdf_filename)
    return pdf_filename

# Define functions for different contract types
def generate_nda(details):
    return generate_contract("Non-Disclosure Agreement (NDA)", details)

def generate_lease(details):
    return generate_contract("Lease Agreement", details)

def generate_employment(details):
    return generate_contract("Employment Contract", details)
def save_as_pdf(text, filename="transcription.pdf"):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(190, 10, text)

    pdf_path = f"./{filename}"
    pdf.output(pdf_path)
    return pdf_path

# Function to convert text to speech and save as audio file
def text_to_speech(text, filename="transcription_audio.mp3"):
    engine = pyttsx3.init()
    engine.save_to_file(text, filename)
    engine.runAndWait()
    return filename


def legal_dictation():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("🎙️ Speak now... AI is listening.")
        recognizer.adjust_for_ambient_noise(source)
        
        try:
            audio = recognizer.listen(source, timeout=10)  # 10s timeout
            text = recognizer.recognize_google(audio)
            return text
        except sr.WaitTimeoutError:
            return "⏳ No speech detected, please try again."
        except sr.UnknownValueError:
            return "❌ Could not understand speech."
        except sr.RequestError:
            return "⚠️ Error connecting to speech recognition service."






st.set_page_config(page_title="AI Assistant", layout="wide")

# Initialize session state for chat history and selected chat
if "history" not in st.session_state:
    st.session_state.history = []
if "selected_chat" not in st.session_state:
    st.session_state.selected_chat = None
if "new_chat" not in st.session_state:
    st.session_state.new_chat = False

# Sidebar: Chat History Management
st.sidebar.title("📜 Chat History")

# "New Chat" Button
if st.sidebar.button("➕ New Chat"):
    st.session_state.selected_chat = None  # Deselect previous chat
    st.session_state.new_chat = True  # Enable new chat mode
    st.rerun()

# Display stored chat history in the sidebar
if st.session_state.history:
    for i, item in enumerate(st.session_state.history):
        if st.sidebar.button(f"🔹 {item['query']}", key=f"chat_{i}"):
            st.session_state.selected_chat = item  # Store selected chat in session state
            st.session_state.new_chat = False  # Disable new chat mode
            st.rerun()

# Clear History Button
if st.sidebar.button("🗑️ Clear History"):
    st.session_state.history = []
    st.session_state.selected_chat = None
    st.session_state.new_chat = True  # Enable new chat mode
    st.rerun()

# Sidebar Features
st.sidebar.title("🔍 Features")
selected_tab = st.sidebar.radio(
    "Choose a feature:",
    ["💬 AI Chat", "🎙️ Voice Assistant", "📄 Summarize PDF", 
     "📱 QR Code Generator", "📍Access Nearby", "Contract Drafting", "🖊️ Legal Dictation"]
)

# Main Workspace Title
st.title("🤖 Multilingual AI Assistant")
st.divider()

# Chat Input Section (for new chats)
if st.session_state.new_chat:
    user_input = st.text_input("💬 Type your message:", "")
    if st.button("Send"):
        if user_input:
            response = f"🔍 AI Response to: {user_input}"  # Replace with actual AI function call
            chat_entry = {"query": user_input, "response": response}
            st.session_state.history.append(chat_entry)
            st.session_state.selected_chat = chat_entry
            st.session_state.new_chat = False  # Disable new chat mode
            st.rerun()

# Display selected chat on the right
if st.session_state.selected_chat:
    query = st.session_state.selected_chat['query']
    response = st.session_state.selected_chat['response']

    chat_display = f"""
    <div class="chat-display">
        <div class="chat-box query-box">🔍 {query}</div>
        <div class="chat-box response-box">💬 {response}</div>
    </div>
    """

    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    st.markdown(chat_display, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)



### 📌 CHATBOT WITH HISTORY ###
if selected_tab == "💬 AI Chat":
    st.subheader("💬 AI Chat Assistant")

    user_query = st.chat_input("Ask me anything...")

    if user_query:
        target_lang = st.selectbox("Select language:", ["en", "hi", "fr", "es", "de", "ta", "te"], key="chat_lang")

        # Placeholder for bot response animation
        placeholder = st.empty()
        placeholder.markdown(
            """
            <div style="text-align:center; font-size:24px;">
                😊 <span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
            </div>
            <style>
                @keyframes bounce {
                    0%, 100% { transform: translateY(0); }
                    50% { transform: translateY(-5px); }
                }
                .dot {
                    display: inline-block;
                    font-size: 30px;
                    animation: bounce 1.5s infinite ease-in-out alternate;
                }
                .dot:nth-child(2) { animation-delay: 0.2s; }
                .dot:nth-child(3) { animation-delay: 0.4s; }
            </style>
            """,
            unsafe_allow_html=True
        )

        # Fetch response from Gemini AI
        answer = get_gemini_response(user_query, target_lang)

        # Replace animation with actual response
        placeholder.empty()
        st.session_state.history.append({"query": user_query, "response": answer, "feature": "Chat"})

        # Styled response display
        st.markdown(f"**🧑‍💼 You:** {user_query}")
        st.markdown(f"**🤖 Bot:** {answer}")

### 🎙️ VOICE ASSISTANT ###
elif selected_tab == "🎙️ Voice Assistant":
    st.subheader("🎙️ Voice Assistant")

    target_lang = st.selectbox("Select response language:", ["en", "hi", "fr", "es", "de", "ta", "te"], key="voice_lang")

    if st.button("🎤 Start Listening"):
        voice_input = recognize_speech()
        st.text(f"You said: {voice_input}")

        if voice_input:
            answer = get_gemini_response(voice_input, target_lang)
            st.subheader("Answer")
            st.markdown(answer)

            b64_audio = text_to_speech(answer, target_lang)
            st.markdown(f'<audio controls><source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3"></audio>', unsafe_allow_html=True)

            st.session_state.history.append({"query": voice_input, "response": answer, "feature": "Voice"})


### 📄 PDF SUMMARIZATION WITH QUESTION FEATURE ###
elif selected_tab == "📄 Summarize PDF":
    st.subheader("📄 Upload a PDF for Summarization")
    
    uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
    target_lang = st.selectbox("Select language:", ["en", "hi", "fr", "es", "de", "ta", "te"])
    
    if uploaded_file and st.button("📃 Summarize"):
        summarized_text = summarize_pdf(uploaded_file, target_lang)
        st.session_state.pdf_summary = summarized_text  # Store summary in session state
        st.subheader("📜 Summary")
        st.markdown(summarized_text)

        st.session_state.history.append({"query": "PDF Summarization", "response": summarized_text, "feature": "PDF"})

    # **Ask a Question Based on the Summary**
    if "pdf_summary" in st.session_state:
        st.subheader("❓ Ask a Question about the PDF")
        user_question = st.text_input("Enter your question:")

        if user_question:
            full_context = f"Here is a summarized version of a PDF document:\n\n{st.session_state.pdf_summary}\n\nNow, answer this question based on the summary:\n{user_question}"
            answer = get_gemini_response(full_context, target_lang)
            
            st.subheader("🤖 AI's Answer")
            st.markdown(answer)

            st.session_state.history.append({"query": user_question, "response": answer, "feature": "PDF Q&A"})

### 📱 QR CODE GENERATOR ###
elif selected_tab == "📱 QR Code Generator":
    st.subheader("📱 Scan QR Code to Open App")
    
    if st.button("📷 Generate QR Code"):
        qr_image = generate_qr_code()
        img_bytes = BytesIO()
        qr_image.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        st.image(img_bytes, caption="Scan to open app", use_column_width=True)


### 📍 FIND NEARBY LEGAL FIRMS ###
elif selected_tab == "📍Access Nearby":  # Ensure exact match in sidebar
    st.subheader("📍 Find Nearby Legal Firms")

    # Store location persistently inside this section only
    if "user_location" not in st.session_state:
        st.session_state.user_location = None

    # Button to detect location
    if st.button("🔎 Detect My Location"):
        st.write("🔍 Detecting location...")  # Debugging message
        g = geocoder.ip('me')  # Fetch user location

        if g.latlng:
            st.session_state.user_location = g.latlng
            st.success(f"📍 Location Detected: {st.session_state.user_location[0]}, {st.session_state.user_location[1]}")
        else:
            st.error("❌ Could not retrieve location. Please check your internet connection.")
            st.write("Debug: Location retrieval failed, g.latlng returned None.")  # Extra debug output

    # Ensure location is retrieved before asking for legal needs
    if st.session_state.user_location:
        legal_need = st.text_input("Enter your legal need (e.g., 'divorce', 'criminal', 'corporate'):")
        
        if st.button("🔍 Find Nearby Legal Firms") and legal_need:
            latitude, longitude = st.session_state.user_location
            legal_firms_url, specialist_url = get_nearby_legal_firms_and_specialists(latitude, longitude, legal_need)

            st.markdown(f"🌍 [Nearby Legal Firms]({legal_firms_url})")
            st.markdown(f"🔎 [Specialist Lawyers for {legal_need}]({specialist_url})")
        elif not legal_need:
            st.warning("⚠️ Please enter a specific legal need.")
elif selected_tab == "Contract Drafting":
    st.subheader("📝 Generate a Legal Contract")

    contract_type = st.selectbox("Select Contract Type", ["NDA", "Lease", "Employment"])
    details = st.text_area("Enter contract details (e.g., parties involved, terms, duration)")

    if st.button("📝 Generate Contract"):
        if details:
            if contract_type == "NDA":
                contract_text = generate_nda(details)
            elif contract_type == "Lease":
                contract_text = generate_lease(details)
            elif contract_type == "Employment":
                contract_text = generate_employment(details)
            else:
                contract_text = "Invalid contract type selected."

            st.subheader("📜 Generated Contract")
            st.text_area("Contract", contract_text, height=300)

            # Save as PDF
            pdf_file = create_pdf(contract_text, contract_type)
            with open(pdf_file, "rb") as file:
                st.download_button("📥 Download Contract", file, file_name=pdf_file, mime="application/pdf")
        else:
            st.warning("⚠️ Please enter contract details.")
elif selected_tab == "🖊️ Legal Dictation":
    st.subheader("📝 Legal Dictation – Speak, and AI Writes It Down")

    if st.button("🎤 Start Dictation"):
        transcribed_text = legal_dictation()
        st.text_area("📄 Transcribed Text:", transcribed_text, height=200)

        if transcribed_text and not transcribed_text.startswith(("⏳", "❌", "⚠️")):  # Avoid errors for invalid text
            # ✅ Save as PDF
            pdf_file = save_as_pdf(transcribed_text)
            with open(pdf_file, "rb") as file:
                st.download_button("📥 Download as PDF", file, file_name="Legal_Dictation.pdf", mime="application/pdf")


>>>>>>> 6ed5a0610661de02d4c9fa8781a0f9e0d1287d6c
