import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# --- CONFIGURATION ---
st.set_page_config(page_title="GEO Domain Tracker", layout="wide")

st.title("🌐 GEO Analytics (Domain Tracker)")
st.markdown("""
**Mode Domaine :** L'outil vérifie si l'IA cite explicitement **ton site web** (ex: `tonsite.com`) dans ses sources ou sa réponse.
""")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Paramètres")
    api_key = st.text_input("Ta clé API Google (AI Studio)", type="password")
    
    # LISTE DE SÉCURITÉ (On garde la stratégie "Increvable")
    search_models = ["gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-pro"]
    backup_model = "gemini-2.5-flash"

if api_key:
    genai.configure(api_key=api_key)
else:
    st.warning("Entre ta clé API Google pour commencer.")
    st.stop()

# --- INPUTS (MODIFIÉS POUR LE DOMAINE) ---
col1, col2 = st.columns(2)
with col1:
    # Changement ici : On demande le DOMAINE
    target_domain = st.text_input("Ton Domaine (ex: nike.com, lemonde.fr)", value="nike.com")
with col2:
    competitors = st.text_input("Concurrents", value="adidas.fr, asics.com")

input_questions = st.text_area(
    "Questions (Simulations)", 
    value="Quelle est la meilleure chaussure de running ?\nOù acheter des baskets de marathon ?"
)

start_btn = st.button("Lancer l'Audit Domaine", type="primary")

# --- FONCTIONS ---

def get_universal_response(question):
    """ Tente la recherche web (Grounding) puis fallback sur IA standard """
    
    # 1. TENTATIVE RECHERCHE WEB
    for model_name in search_models:
        try:
            tools = 'google_search_retrieval'
            model = genai.GenerativeModel(model_name, tools=tools)
            prompt = f"Question: {question}. Fais une recherche Google. Réponds et liste IMPÉRATIVEMENT les URLs sources à la fin."
            
            response = model.generate_content(prompt)
            if not response.text: continue 
            return response.text, f"Recherche Web ({model_name}) 🌍"
            
        except:
            continue

    # 2. BACKUP (IA STANDARD)
    try:
        model_backup = genai.GenerativeModel(backup_model)
        response = model_backup.generate_content(question)
        return response.text, f"IA Standard ({backup_model}) 🤖"
    except Exception as e:
        return f"Erreur : {str(e)}", "Erreur ❌"

def analyze_domain_presence(text, domain):
    """ 
    NOUVEAU JUGE : Vérifie si le DOMAINE spécifique est présent 
    """
    try:
        model = genai.GenerativeModel("gemini-1.5-flash", generation_config={"response_mime_type": "application/json"})
        
        prompt = f"""
        Analyse ce texte généré par une IA.
        
        Objectif : Détecter si le domaine "{domain}" est mentionné ou présent dans les sources.
        (Accepte les sous-domaines comme store.{domain} ou {domain}/blog)
        
        Réponds JSON :
        {{
            "domain_detected": boolean, (Vrai uniquement si {domain} est trouvé)
            "sentiment": string,
            "all_urls_found": list of strings (Liste toutes les URLs citées dans le texte)
        }}
        
        Texte : \"\"\"{text}\"\"\"
        """
        res = model.generate_content(prompt)
        return json.loads(res.text)
    except:
        return {"domain_detected": False, "sentiment": "N/A", "all_urls_found": []}

# --- MAIN LOOP ---

if start_btn:
    questions_list = [q.strip() for q in input_questions.split('\n') if q.strip()]
    results = []
    
    progress_bar = st.progress(0)
    
    for i, question in enumerate(questions_list):
        
        # 1. Génération
        answer_text, mode = get_universal_response(question)
        
        # 2. Analyse du DOMAINE
        if "Erreur" not in mode:
            data = analyze_domain_presence(answer_text, target_domain)
        else:
            data = {"domain_detected": False, "sentiment": "Error", "all_urls_found": []}
        
        # Formatage sources
        sources_list = data.get('all_urls_found', [])
        sources_str = ", ".join(sources_list[:3]) # On affiche les 3 premières
        if not sources_str: sources_str = "Aucune URL citée"

        results.append({
            "Question": question,
            "Mode": mode,
            "Domaine Présent ?": "✅ OUI" if data.get('domain_detected') else "❌ NON",
            "Toutes les Sources": sources_str,
            "Réponse Complète": answer_text
        })
        progress_bar.progress((i + 1) / len(questions_list))

    st.success("Audit terminé !")
    
    if results:
        df = pd.DataFrame(results)
        
        # KPIs
        total_oui = df[df["Domaine Présent ?"] == "✅ OUI"].shape[0]
        st.metric("Taux de Visibilité Domaine", f"{total_oui}/{len(questions_list)}")

        st.dataframe(df[["Question", "Domaine Présent ?", "Toutes les Sources"]], use_container_width=True)
        
        st.divider()
        for index, row in df.iterrows():
            with st.expander(f"Détail : {row['Question']}"):
                st.write(row['Réponse Complète'])
