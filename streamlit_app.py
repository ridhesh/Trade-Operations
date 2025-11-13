import streamlit as st
import requests
import time

FASTAPI_URL = "http://127.0.0.1:8000/analyze"  # Backend endpoint
AUTH_URL = "http://127.0.0.1:8000/auth"        # Get API key
API_KEY = st.session_state.get("api_key", "")

st.set_page_config(page_title="Sectoral Analysis - India", page_icon="📊")
st.title("📊 Trade Opportunities Analysis (India)")
st.markdown("Get real-time sectoral analysis powered by Gemini API & FastAPI.")

# --- API KEY MANAGEMENT ---
def get_api_key():
    if "api_key" not in st.session_state or not st.session_state["api_key"]:
        if st.button("🔐 Get API Key"):
            try:
                r = requests.post(AUTH_URL)
                if r.status_code == 200:
                    api_key = r.json()['api_key']
                    st.session_state["api_key"] = api_key
                    st.success("✅ API Key set. Ready to analyze!")
                else:
                    st.error("Could not obtain API Key. Make sure FastAPI backend is running.")
            except Exception as e:
                st.error(f"Error getting API Key: {e}")

get_api_key()

if "api_key" in st.session_state and st.session_state["api_key"]:
    API_KEY = st.session_state["api_key"]
    st.success(f"API key is active.")

# --- USER INPUT ---
sector = st.text_input(
    "Enter Indian sector (e.g., Pharmaceuticals, IT, Agriculture):",
    placeholder="Pharmaceuticals, IT, Agriculture"
)

analyze_btn = st.button("🔍 Analyze Sector")

# --- FASTAPI CALL ---
def analyze_sector_api(sector_name: str):
    try:
        headers = {"X-API-Key": API_KEY}
        payload = {"sector": sector_name}
        response = requests.post(FASTAPI_URL, headers=headers, json=payload)

        if response.status_code == 429:
            st.warning("⚠️ Too many requests — waiting 10 seconds before retry...")
            time.sleep(10)
            response = requests.post(FASTAPI_URL, headers=headers, json=payload)

        if response.status_code != 200:
            st.error(f"❌ Error {response.status_code}: {response.text}")
            return None

        return response.json()

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        return None

# --- HANDLE USER REQUEST ---
if analyze_btn:
    if not sector or len(sector.strip()) < 2:
        st.error("⚠️ Please enter a valid sector name (min 2 chars).")
    else:
        with st.spinner("🔎 Analyzing sector insights..."):
            result = analyze_sector_api(sector.strip())
        if result:
            st.subheader("📈 Sectoral Insights")
            st.markdown(f"### Sector: {result['sector']}")
            st.markdown(result['markdown_report'])
            if isinstance(result.get('grounding_sources'), list) and result['grounding_sources']:
                st.markdown("### Grounding Sources")
                for src in result['grounding_sources']:
                    st.markdown(f"- [{src['title']}]({src['uri']})")
            st.success("✅ Analysis completed successfully!")

st.caption("Powered by Gemini API & FastAPI | © 2025 Sectoral Insights")
