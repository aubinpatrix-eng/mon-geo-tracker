import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# --- CONFIGURATION ---
st.set_page_config(page_title="GEO Tracker (Gemini 2.0)", layout="wide")

st.title("🚀 GEO Analytics (Version Gemini 2.0 Flash)")
st.markdown("""
**Moteur :** Ce script force l'utilisation des derniers modèles expérimentaux de Google.
Si le mode "Recherche" échoue, il bascule automatiquement sur l'analyse standard.
""")

# --- SIDEBAR & DIAGNOSTIC ---
with st.sidebar:
    st.header("Paramètres")
    api_key = st.text_input("Ta clé API Google (AI Studio)", type="password")
    
    # LISTE PRIORITAIRE (Incluant le "3 Flash" qui est en fait le 2.0 Exp)
    available_models = [
        "gemini-2.0-flash-exp",     # Le fameux nouveau modèle
        "gemini-exp-1206",          # Version expérimentale alternative
        "gemini-1.5-flash",         # Standard
        "gemini-1.5-flash-8b",      # Version légère
        "gemini-1.5-pro"            # Version Pro
    ]
    
    st.caption("Modèles testés : " + ", ".join(available_models))

    st.divider()
    
    # BOUTON DE DEBUG (Pour comprendre l'erreur 404)
    if st.button("🆘 Vérifier ma connexion API"):
        if api_key:
            try:
                genai.configure(api_key=api_key)
                models = genai.list_models()
                found = []
                for m in models:
                    if 'generateContent' in m.supported_generation_methods:
                        found.append(m.name)
                st.success(f"Connexion réussie ! Modèles accessibles ({len(found)}) :")
                st.code("\n".join(found))
            except Exception as e:
                st.error(f"Erreur de connexion : {e}")
        else:
            st.warning("Entre d'abord ta clé API.")

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

# --- FONCTIONS INTELLIGENTES ---

def try_generate_content(prompt, tools=None):
    """Teste les modèles un par un jusqu'à ce que ça marche"""
    last_error = ""
    
    for model_name in available_models:
        try:
            # On instancie le modèle
            if tools:
                model = genai.GenerativeModel(model_name, tools=tools)
            else:
                model = genai.GenerativeModel(model_name)
            
            # On tente la génération
            response = model.generate_content(prompt)
            
            # Vérification de sécurité (si Google bloque la réponse)
            if not response.text:
                return None, f"Bloqué par sécu ({model_name})"
                
            return response.text, model_name 
            
        except Exception as e:
            last_error = str(e)
            continue # On passe au modèle suivant
            
    return None, last_error

def get_smart_response(question):
    # 1. ESSAI AVEC RECHERCHE (Grounding)
    prompt_search = f"Question: {question}. Fais une recherche Google et réponds en citant les URLs sources."
    text, model = try_generate_content(prompt_search, tools='google_search_retrieval')
    
    if text:
        return text, f"Recherche Web ({model}) 🌍"
    
    # 2. ESSAI CLASSIQUE (Si la recherche échoue)
    prompt_std = f"Réponds à cette question : {question}"
    text_std, model_std = try_generate_content(prompt_std)
    
    if text_std:
        return text_std, f"IA Standard ({model_std}) 🤖"
        
    return f"Erreur : {model_std}", "Échec Total ❌"

def analyze_content(text, brand):
    # Analyseur simple en JSON
    model_judge = genai.GenerativeModel("gemini-1.5-flash", generation_config={"response_mime_type": "application/json"})
    prompt = f"""Analyse ce texte pour la marque "{brand}". Réponds en JSON : {{"cited": boolean, "sentiment": string, "sources": string}} Texte : \"\"\"{text}\"\"\""""
    try:
        res = model_judge.generate_content(prompt)
        return json.loads(res.text)
    except:
        return {"cited": False, "sentiment": "Erreur", "sources": "N/A"}

# --- MAIN LOOP ---

if start_btn:
    questions_list = [q.strip() for q in input_questions.split('\n') if q.strip()]
    results = []
    
    progress_bar = st.progress(0)
    status_box = st.empty()
    
    for i, question in enumerate(questions_list):
        status_box.info(f"Traitement : {question}...")
        
        answer_text, source_mode = get_smart_response(question)
        
        if "Échec" in source_mode:
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
