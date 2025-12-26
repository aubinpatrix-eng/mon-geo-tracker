import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# --- CONFIGURATION ---
st.set_page_config(page_title="GEO Tracker (Gemini 2.5)", layout="wide")

st.title("🚀 GEO Analytics (Version Gemini 2.5)")
st.markdown("""
**Moteur :** Ce script utilise la version **Gemini 2.5** détectée sur ton compte.
""")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Paramètres")
    api_key = st.text_input("Ta clé API Google (AI Studio)", type="password")
    
    # LISTE MISE À JOUR SELON TA CAPTURE D'ÉCRAN
    available_models = [
        "gemini-2.5-flash",    # LE NOUVEAU (Prioritaire)
        "gemini-2.5-pro",      # Le plus puissant
        "gemini-2.0-flash",    # Backup
        "gemini-1.5-flash"     # Ancien standard
    ]
    
    st.caption("Modèle cible : gemini-2.5-flash")

    # DIAGNOSTIC RAPIDE
    if st.button("Re-vérifier ma connexion"):
        if api_key:
            try:
                genai.configure(api_key=api_key)
                models = genai.list_models()
                found = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
                st.success(f"Connecté ! {len(found)} modèles trouvés.")
            except Exception as e:
                st.error(f"Erreur : {e}")

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

# --- FONCTIONS CORE ---

def get_smart_response(question):
    """Essaie de répondre avec Gemini 2.5, avec ou sans recherche"""
    
    # On boucle pour trouver le bon modèle
    for model_name in available_models:
        try:
            # 1. TENTATIVE AVEC RECHERCHE (Grounding)
            try:
                model = genai.GenerativeModel(model_name, tools='google_search_retrieval')
                prompt = f"Question: {question}. Fais une recherche Google récente. Réponds et liste tes sources URL à la fin."
                response = model.generate_content(prompt)
                return response.text, f"Recherche Web ({model_name}) 🌍"
            except:
                # Si la recherche échoue, on continue sans planter
                pass

            # 2. TENTATIVE STANDARD (Sans recherche)
            model_std = genai.GenerativeModel(model_name)
            response_std = model_std.generate_content(question)
            return response_std.text, f"IA Standard ({model_name}) 🤖"
            
        except Exception:
            continue # On passe au modèle suivant si celui-ci plante (404)
            
    return "Aucun modèle n'a fonctionné.", "Erreur ❌"

def analyze_content(text, brand):
    # Analyse JSON
    judge_model = "gemini-2.5-flash" # On utilise le plus rapide
    try:
        model = genai.GenerativeModel(judge_model, generation_config={"response_mime_type": "application/json"})
        prompt = f"""Analyse ce texte pour la marque "{brand}". Réponds JSON : {{"cited": boolean, "sentiment": string, "sources": string}} Texte : \"\"\"{text}\"\"\""""
        res = model.generate_content(prompt)
        return json.loads(res.text)
    except:
        # Fallback si le 2.5 plante, on tente le 1.5 ou on renvoie une erreur soft
        return {"cited": False, "sentiment": "Erreur Analyse", "sources": "N/A"}

# --- MAIN LOOP ---

if start_btn:
    questions_list = [q.strip() for q in input_questions.split('\n') if q.strip()]
    results = []
    
    progress_bar = st.progress(0)
    status_box = st.empty()
    
    for i, question in enumerate(questions_list):
        status_box.info(f"Traitement : {question}...")
        
        answer_text, source_mode = get_smart_response(question)
        
        if "Erreur" in source_mode:
            data = {"cited": False, "sentiment": "N/A", "sources": "N/A"}
        else:
            data = analyze_content(answer_text, target_brand)
        
        results.append({
            "Question": question,
            "Mode": source_mode,
            "Présence": "✅" if data.get('cited') else "❌",
            "Sources": data.get('sources', 'N/A'),
            "Réponse": answer_text
        })
        progress_bar.progress((i + 1) / len(questions_list))

    status_box.success("Terminé !")
    
    if results:
        df = pd.DataFrame(results)
        st.dataframe(df[["Question", "Mode", "Présence", "Sources"]], use_container_width=True)
