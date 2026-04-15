import streamlit as st
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from google import genai
import requests
import re
import time
import socket

# --- UI Setup ---
st.set_page_config(page_title="Smart-Search (beta)", layout="wide")

# Custom CSS for UI Polish (Minimalist Corporate Theme)
st.markdown("""
    <style>
    .stTextArea textarea {
        border: 1px solid #cccccc !important;
        border-radius: 6px !important;
        transition: all 0.2s ease-in-out;
        font-family: 'Inter', sans-serif;
    }
    .stTextArea textarea:focus {
        border: 1px solid #115740 !important;
        box-shadow: 0 0 8px rgba(17, 87, 64, 0.15) !important;
    }
    div.stButton > button:first-child {
        background-color: #115740;
        color: white;
        border-radius: 6px;
        height: 2.8em;
        font-weight: 500;
        transition: 0.2s;
        border: none;
    }
    div.stButton > button:first-child:hover {
        background-color: #0d4533;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center; color: #115740; font-weight: 600;'>Call Report Smart Analyst</h1>", unsafe_allow_html=True)
st.markdown("<hr style='border: 1px solid #eaeaea; margin-top: 0;'>", unsafe_allow_html=True)

# --- BigQuery Connection ---
@st.cache_resource
def get_bq_client():
    """Initializes a BigQuery client using your service account secrets."""
    try:
        credentials = service_account.Credentials.from_service_account_info(st.secrets["gcp_service_account"])
        return bigquery.Client(credentials=credentials, project=credentials.project_id)
    except Exception as e:
        st.error(f"BigQuery Authentication Failed: {e}")
        return None

client = get_bq_client()
PROJECT_ID = st.secrets["gcp_service_account"]["project_id"]
DATASET = st.secrets.get("BQ_DATASET", "ffiec_data")

# --- Helper: Updated Schema & Rules for BigQuery ---
def get_schema_context():
    return f"""
    BIGQUERY SCHEMA (Standard SQL):
    1. Table: `{PROJECT_ID}.{DATASET}.call_reports_financials` (f)
       - Columns: idrssd (INT), report_date (STRING 'MM/DD/YYYY'), concept_reference (STRING MDRM code), value (STRING)
    2. Table: `{PROJECT_ID}.{DATASET}.call_reports_por` (p)
       - Columns: idrssd (INT), bank_name (STRING)
    3. Table: `{PROJECT_ID}.{DATASET}.mdrm_dictionary` (d)
       - Columns: concept_reference (STRING MDRM code), item_name (STRING description)
    
    MAPPING PROTOCOL:
    - ALWAYS Join `f` and `d` on `f.concept_reference = d.concept_reference`.
    - To map user terms to the dictionary, use: `WHERE LOWER(d.item_name) LIKE LOWER('%[Metric Name]%')`.
    - This ensures that 'Total Assets', 'total assets', and 'TOTAL ASSETS' all map correctly to the same MDRM ID.

    SQL RULES:
    - Use BACKTICKS and FULL QUALIFIED NAMES: `{PROJECT_ID}.{DATASET}.table_name`.
    - DATE FILTERING: `report_date` is a STRING ('MM/DD/YYYY'). Use `f.report_date LIKE '%YYYY'` for year filters.
    - DATA TYPES: 'value' is a STRING. ALWAYS use `SAFE_CAST(f.value AS FLOAT64)` for calculations.
    - Return ONLY raw SQL starting with SELECT.
    - DO NOT include any introductory text, explanations, or 'Sure!' in your response.
    - Return ONLY the SQL code.
    - If using Markdown, wrap the code in ```sql blocks.
    """
    
# --- Helper: Check if Ollama is running ---
def is_ollama_online(url="localhost", port=11434):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex((url, port)) == 0
    except:
        return False

# --- Configuration Sidebar ---
with st.sidebar:
    st.header("Engine Settings")
    search_engine = st.radio("Select Search Engine:", ["Gemini (Cloud)", "Ollama (Local)"])
    
    if search_engine == "Gemini (Cloud)":
        try:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success("Gemini Key loaded successfully.")
        except:
            api_key = st.text_input("Enter Gemini API Key", type="password")
        model_choice = st.selectbox("Model:", ["gemini-2.5-flash", "gemini-2.5-pro"])
    else:
        if is_ollama_online():
            st.success("Ollama Service: ONLINE")
            try:
                tags = requests.get("http://localhost:11434/api/tags").json()
                models = [m['name'] for m in tags.get('models', [])]
                model_choice = st.selectbox("Local Model:", models if models else ["llama3"])
            except:
                model_choice = st.text_input("Model Name:", value="llama3")
        else:
            st.error("Ollama Service: OFFLINE")
            st.info("Run `brew services start ollama` in terminal.")
            model_choice = "llama3"
        
        ollama_url = st.text_input("Ollama Endpoint URL:", value="http://localhost:11434/api/generate")

    st.divider()
    if st.button("Clear Application Cache"):
        st.cache_data.clear()
        st.success("Cache Cleared.")

# --- AI Logic Wrapper ---
@st.cache_data(show_spinner=False)
def get_ai_response(engine_type, model_id, prompt, schema, _api_key=None, _url=None):
    full_prompt = f"{schema}\n\nUser Question/Context: {prompt}"
    
    if engine_type == "Gemini (Cloud)":
        client = genai.Client(api_key=_api_key)
        response = client.models.generate_content(model=model_id, contents=full_prompt)
        return response.text
    else:
        payload = {
            "model": model_id, 
            "prompt": full_prompt, 
            "stream": False  # Must be false to get a single JSON object back
        }
        try:
            response = requests.post(_url, json=payload, timeout=180)
            response.raise_for_status()  # Check for 404 or 500 errors
            return response.json().get("response", "Error: No response field found")
        except Exception as e:
            return f"Ollama Connection Error: {e}"

# --- UI Tabs ---
tab1, tab2 = st.tabs(["AI Smart Search", "Database Statistics"])

with tab2:
    st.subheader("Database Overview")
    try:
        # Standard BigQuery query format
        total_query = f"SELECT COUNT(*) as total FROM `{PROJECT_ID}.{DATASET}.call_reports_financials`"
        count_rows = client.query(total_query).to_dataframe().iloc[0]['total']
        
        st.metric("Financial Records Indexed", f"{count_rows:,}")
        
        st.write("### Financial Data Sample")
        sample_query = f"SELECT * FROM `{PROJECT_ID}.{DATASET}.call_reports_financials` LIMIT 5"
        sample = client.query(sample_query).to_dataframe()
        st.dataframe(sample, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading statistics: {e}")

with tab1:
    st.subheader("Query Interface")
    user_query = st.text_area(
        "Enter your query parameters:", 
        placeholder="e.g., Which banks reported the highest Total Assets (RCFD2170) on 12312023?",
    )

    if st.button("Execute Analysis", use_container_width=True):
        if search_engine == "Gemini (Cloud)" and not api_key:
            st.error("API Key required.")
        elif not user_query:
            st.warning("Please enter a question.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                # 1. GENERATE SQL
                status_text.info("Generating BigQuery SQL...")
                progress_bar.progress(25)
                
                raw_sql = get_ai_response(
                    search_engine, model_choice, user_query, get_schema_context(),
                    _api_key=(api_key if search_engine == "Gemini (Cloud)" else None),
                    _url=(ollama_url if search_engine == "Ollama (Local)" else None)
                )
                # DEBUG LINE:
                with st.expander("Raw AI Output (Debug)"):
                    st.text(raw_sql)
                
                # sql_match = re.search(r"(SELECT\s.*)", raw_sql, re.DOTALL | re.IGNORECASE)
                sql_match = re.search(r"```sql\s*(.*?)\s*```|```\s*(.*?)\s*```|(SELECT\s+.*)", raw_sql, re.DOTALL | re.IGNORECASE)

                if sql_match:
                    # Check groups in order: Markdown SQL, generic Markdown, or raw SELECT
                    clean_sql = sql_match.group(1) or sql_match.group(2) or sql_match.group(3)
                    clean_sql = clean_sql.strip()
                    clean_sql = re.sub(r"```.*", "", clean_sql, flags=re.DOTALL).strip()
                else:
                    clean_sql = ""

                # 2. VALIDATION & EXECUTION
                if clean_sql:
                    st.markdown("**Generated BigQuery Query:**")
                    st.code(clean_sql, language="sql")

                    status_text.info("Querying BigQuery...")
                    progress_bar.progress(50)
                    
                    try:
                        # Now clean_sql is guaranteed to have a value
                        df = client.query(clean_sql).to_dataframe()
                        
                        if df.empty:
                            st.warning("No records found. Check your mapping or date filter.")
                        else:
                            # 3. SUMMARIZE
                            status_text.info("Summarizing results...")
                            progress_bar.progress(75)
                            
                            summary_prompt = f"Summarize this data for the user: {df.head(5).to_string()}"
                            answer = get_ai_response(
                                search_engine, model_choice, summary_prompt, "Be a helpful financial analyst.",
                                _api_key=(api_key if search_engine == "Gemini (Cloud)" else None),
                                _url=(ollama_url if search_engine == "Ollama (Local)" else None)
                            )
                            
                            progress_bar.progress(100)
                            status_text.empty()
                            
                            st.markdown("### Analyst Summary")
                            st.info(answer)
                            st.dataframe(df, use_container_width=True)
                            pass
                    except Exception as e:
                        st.error(f"BigQuery execution error: {e}")
                else:
                    # This prevents the '400: Required parameter missing' error
                    st.error("Ollama failed to produce a valid SELECT statement. Try rephrasing or check your prompt.")

            except Exception as e:
                st.error(f"Analysis Failed: {e}")