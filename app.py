import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# --- CONFIGURATION ---
st.set_page_config(page_title="GEO Tracker (Mode Robuste)", layout="wide")

st.title("🛡️ GEO Analytics Tracker (Mode Robuste)")
st.markdown("""
**Statut :** Ce tracker est équipé d'un "Filet de sécurité". 
Il tente d'abord la recherche Google réelle. Si l'API échoue, il bascule sur l'analyse IA standard.
""")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Paramètres")
    api_key = st.text_input("Ta clé API Google (AI Studio)", type="password")
    
    # On utilise le nom de modèle le plus standard
    model_name = "gemini-1.5-flash"

if api_key:
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"Erreur clé API : {e}")
        st.stop()
else:
    st.warning("Entre ta clé API Google pour commencer.")
    st.stop()

# --- INPUTS ---
col1, col2 = st.columns(2)
with col1:
    target_brand = st.text_input("Ta Marque", value="Nike")
with col2:
    competitors = st.text_input("Concurrents", value="Adidas, Asics")

input_questions = st.text_area(
    "Questions (Simulations)", 
    value="Quelle est la meilleure chaussure de running ?\nTop 3 marques de sport pour le marathon"
)

start_btn = st.button("Lancer l'Audit", type="primary")

# --- FONCTIONS INTELLIGENTES (AVEC FILET DE SECURITÉ) ---

def get_smart_response(question):
    """
    Tente la recherche Google. Si ça plante (404), bascule en mode standard.
    """
    # TENTATIVE 1 : Mode Recherche (Grounding)
    try:
        tools = 'google_search_retrieval'
        # On spécifie explicitement la version 'models/' pour aider l'API
        model = genai.GenerativeModel(f'models/{model_name}', tools=tools)
        
        prompt = f"""
        Question : {question}
        Fais une recherche Google récente. Réponds et liste tes sources URL à la fin.
        """
        response = model.generate_content(prompt)
        return response.text, "Recherche Web 🌍"
        
    except Exception as e:
        # TENTATIVE 2 : Mode Fallback (Standard)
        # Si le mode recherche échoue, on passe ici silencieusement
        try:
            model_fallback = genai.GenerativeModel(f'models/{model_name}') # Pas de tools
            prompt_fallback = f"Tu es un expert. Réponds à cette question : {question}"
            response = model_fallback.generate_content(prompt_fallback)
            return response.text, "IA Standard 🤖 (Backup)"
        except Exception as e2:
            return f"Erreur critique : {e2}", "Erreur ❌"

def analyze_content(text, brand):
    """Extrait les données (JSON)"""
    model_judge = genai.GenerativeModel(f'models/{model_name}', generation_config={"response_mime_type": "application/json"})
    
    prompt = f"""
    Analyse ce texte pour la marque "{brand}".
    Réponds en JSON :
    {{
        "cited": boolean,
        "sentiment": string,
        "sources_detected": string (Liste les domaines ou 'Aucune source' si absent)
    }}
    Texte : \"\"\"{text}\"\"\"
    """
    try:
        res = model_judge.generate_content(prompt)
        return json.loads(res.text)
    except:
        return {"cited": False, "sentiment": "Erreur", "sources_detected": "N/A"}

# --- MAIN LOOP ---

if start_btn:
    questions_list = [q.strip() for q in input_questions.split('\n') if q.strip()]
    results = []
    
    progress_bar = st.progress(0)
    status_box = st.empty() # Zone de texte dynamique
    
    for i, question in enumerate(questions_list):
        status_box.info(f"Traitement : {question}...")
        
        # 1. Récupération intelligente
        answer_text, source_mode = get_smart_response(question)
        
        # 2. Analyse
        data = analyze_content(answer_text, target_brand)
        
        row = {
            "Question": question,
            "Mode": source_mode, # On affiche si on a réussi à utiliser Google ou non
            "Présence": "✅" if data.get('cited') else "❌",
            "Sources": data.get('sources_detected', 'N/A'),
            "Réponse": answer_text
        }
        results.append(row)
        progress_bar.progress((i + 1) / len(questions_list))

    status_box.success("Terminé !")

    # --- RESULTS ---
    st.divider()
    if results:
        df = pd.DataFrame(results)
        st.dataframe(df[["Question", "Mode", "Présence", "Sources"]], use_container_width=True)
        
        with st.expander("Voir les détails"):
            st.table(df)
