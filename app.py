import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# --- CONFIGURATION ---
st.set_page_config(page_title="GEO Tracker (Final)", layout="wide")

st.title("🌍 GEO Analytics (Mode Sources Réelles)")
st.markdown("""
**État :** Connecté.
**Objectif :** Forcer l'affichage des URLs sources et du texte complet.
""")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Paramètres")
    api_key = st.text_input("Ta clé API Google (AI Studio)", type="password")
    
    # On utilise le modèle 2.0 Flash qui est très fiable pour le Search
    # (Le 2.5 est parfois capricieux avec les outils pour l'instant)
    search_model = "gemini-2.0-flash" 
    
    st.info(f"Moteur de recherche actif : {search_model}")

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

def get_web_response(question):
    """
    Force la recherche Google avec le modèle 2.0 Flash
    """
    try:
        # Configuration spécifique pour activer le Grounding (Recherche)
        tools = 'google_search_retrieval'
        model = genai.GenerativeModel(search_model, tools=tools)
        
        prompt = f"""
        Tu es un analyste de marché.
        Question : {question}
        
        Consignes STRICTES :
        1. Utilise l'outil Google Search pour trouver des réponses ACTUELLES.
        2. Cite explicitement les URLs des sites que tu as consultés dans le texte.
        3. Réponds de manière détaillée.
        """
        
        response = model.generate_content(prompt)
        
        # Vérification si des sources sont attachées aux métadonnées (le vrai Grounding)
        try:
            sources = response.candidates[0].grounding_metadata.search_entry_point.rendered_content
        except:
            sources = None
            
        return response.text, "Recherche Web 🌍 (Activée)"
    except Exception as e:
        # Fallback si le Search plante
        return f"Erreur Search: {str(e)}", "Erreur ❌"

def analyze_content(text, brand):
    # Analyseur JSON
    try:
        model = genai.GenerativeModel("gemini-2.0-flash", generation_config={"response_mime_type": "application/json"})
        prompt = f"""
        Analyse ce texte.
        Marque cible : "{brand}"
        
        Extrais les domaines (ex: runnersworld.com) cités dans le texte.
        
        Réponds JSON :
        {{
            "cited": boolean, 
            "sentiment": string, 
            "sources_urls": list of strings (Liste les domaines trouvés dans le texte)
        }}
        Texte : \"\"\"{text}\"\"\"
        """
        res = model.generate_content(prompt)
        return json.loads(res.text)
    except:
        return {"cited": False, "sentiment": "N/A", "sources_urls": []}

# --- MAIN LOOP ---

if start_btn:
    questions_list = [q.strip() for q in input_questions.split('\n') if q.strip()]
    results = []
    
    progress_bar = st.progress(0)
    
    for i, question in enumerate(questions_list):
        
        # 1. Appel Web
        answer_text, mode = get_web_response(question)
        
        # 2. Extraction Data
        if "Erreur" not in mode:
            data = analyze_content(answer_text, target_brand)
        else:
            data = {"cited": False, "sources_urls": [], "sentiment": "Error"}
            # On utilise le texte d'erreur comme réponse pour debug
            answer_text = mode 

        # Nettoyage des sources
        sources_str = ", ".join(data.get('sources_urls', []))
        if not sources_str:
            sources_str = "Aucune source détectée"

        results.append({
            "Question": question,
            "Mode": mode,
            "Présence": "✅" if data.get('cited') else "❌",
            "Sources Détectées": sources_str,
            "Réponse Complète": answer_text # On garde le texte entier
        })
        progress_bar.progress((i + 1) / len(questions_list))

    # --- AFFICHAGE ---
    st.success("Audit terminé !")
    
    if results:
        df = pd.DataFrame(results)
        
        # Tableau principal
        st.dataframe(
            df[["Question", "Mode", "Présence", "Sources Détectées"]], 
            use_container_width=True
        )
        
        st.divider()
        st.subheader("📖 Lecture des Réponses Complètes")
        
        # BOUCLE D'AFFICHAGE DU TEXTE
        for index, row in df.iterrows():
            with st.expander(f"Q: {row['Question']} (Voir le texte généré)"):
                st.markdown(f"**Sources trouvées :** {row['Sources Détectées']}")
                st.info(row['Réponse Complète']) # Affiche tout le texte ici
