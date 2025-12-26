import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="GEO Tracker (Mode Auto-Fix)", layout="wide")

st.title("🔧 GEO Analytics Tracker (Mode Auto-Fix)")
st.markdown("""
**Statut :** Ce script teste automatiquement plusieurs versions de Gemini pour contourner les erreurs 404.
""")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Paramètres")
    api_key = st.text_input("Ta clé API Google (AI Studio)", type="password")
    
    # LISTE DE SECOURS : L'outil va tester ces modèles un par un
    available_models = [
        "gemini-1.5-flash-latest", # Le plus récent
        "gemini-1.5-flash",        # L'alias standard
        "gemini-1.5-flash-001",    # La version spécifique (souvent plus stable)
        "gemini-pro"               # La vieille version (marche toujours)
    ]
    
    st.caption(f"Modèles qui seront testés : {', '.join(available_models)}")

if api_key:
    genai.configure(api_key=api_key)
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

# --- FONCTIONS INTELLIGENTES (AVEC ROTATION DE MODÈLES) ---

def try_generate_content(prompt, tools=None):
    """
    Cette fonction essaie tous les modèles de la liste jusqu'à ce qu'un fonctionne.
    """
    last_error = ""
    
    for model_name in available_models:
        try:
            # On tente de configurer le modèle
            if tools:
                model = genai.GenerativeModel(model_name, tools=tools)
            else:
                model = genai.GenerativeModel(model_name)
                
            # On lance la génération
            response = model.generate_content(prompt)
            
            # Si on arrive ici, c'est que ça a marché !
            return response.text, model_name 
            
        except Exception as e:
            # Si ça plante, on note l'erreur et on passe au modèle suivant dans la boucle
            last_error = str(e)
            continue
            
    # Si tout a échoué
    return None, last_error

def get_smart_response(question):
    # TENTATIVE 1 : Mode Recherche (Grounding)
    prompt_search = f"""
    Question : {question}
    Fais une recherche Google récente. Réponds et liste tes sources URL à la fin.
    """
    
    text, used_model = try_generate_content(prompt_search, tools='google_search_retrieval')
    
    if text:
        return text, f"Recherche Web ({used_model}) 🌍"
    
    # TENTATIVE 2 : Mode Fallback (Si la recherche plante partout)
    prompt_standard = f"Tu es un expert. Réponds à cette question : {question}"
    text_std, used_model_std = try_generate_content(prompt_standard)
    
    if text_std:
        return text_std, f"IA Standard ({used_model_std}) 🤖"
        
    return f"Erreur Fatale : {used_model_std}", "Échec ❌"

def analyze_content(text, brand):
    # Pour l'analyse JSON, on utilise le modèle Flash standard sans outils
    model_judge = genai.GenerativeModel("gemini-1.5-flash-latest", generation_config={"response_mime_type": "application/json"})
    
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
        # Fallback manuel si le JSON plante
        return {"cited": False, "sentiment": "Erreur Analyse", "sources_detected": "N/A"}

# --- MAIN LOOP ---

if start_btn:
    questions_list = [q.strip() for q in input_questions.split('\n') if q.strip()]
    results = []
    
    progress_bar = st.progress(0)
    status_box = st.empty()
    
    for i, question in enumerate(questions_list):
        status_box.info(f"Traitement : {question}...")
        
        # 1. Récupération intelligente
        answer_text, source_mode = get_smart_response(question)
        
        # 2. Analyse
        # Si l'étape 1 a échoué, on ne lance pas l'analyse
        if "Échec" in source_mode:
            data = {"cited": False, "sentiment": "N/A", "sources_detected": "N/A"}
        else:
            data = analyze_content(answer_text, target_brand)
        
        row = {
            "Question": question,
            "Mode": source_mode,
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
