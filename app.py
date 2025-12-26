import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# --- CONFIGURATION ---
st.set_page_config(page_title="GEO Tracker (Mode Grounding)", layout="wide")

st.title("🌍 GEO Analytics Tracker (avec Google Search)")
st.markdown("""
**Moteur :** Gemini 1.5 Flash + **Google Search Grounding**.
**Ce qui change :** L'IA va chercher sur le vrai web pour répondre. On peut donc voir **QUELS SITES** te citent.
""")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Paramètres")
    api_key = st.text_input("Ta clé API Google (AI Studio)", type="password")
    
    # On garde Flash, c'est le meilleur ratio vitesse/gratuit
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

start_btn = st.button("Lancer l'Audit GEO (Live Web)", type="primary")

# --- FONCTIONS INTELLIGENTES ---

def get_gemini_search_response(question):
    """
    SIMULATEUR : Utilise l'outil Google Search pour répondre avec des faits réels.
    """
    try:
        # On active l'outil de recherche Google (Grounding)
        tools = 'google_search_retrieval'
        model = genai.GenerativeModel(model_name, tools=tools)
        
        # On force l'IA à explicitement montrer ses sources dans le texte
        prompt = f"""
        Agis comme un moteur de recherche IA avancé.
        Question : {question}
        
        Consignes :
        1. Fais une recherche Google pour trouver des informations récentes.
        2. Réponds à la question de manière utile pour l'utilisateur.
        3. IMPORTANT : À la fin, liste explicitement les URL des sources que tu as utilisées.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erreur Grounding : {e}"

def analyze_response_with_sources(llm_answer, brand):
    """
    JUGE : Analyse le texte pour trouver la marque ET les sources (URL)
    """
    generation_config = {"response_mime_type": "application/json"}
    model_judge = genai.GenerativeModel(model_name, generation_config=generation_config)
    
    prompt = f"""
    Tu es un analyste de données. Analyse la réponse IA ci-dessous.
    
    Marque cible : "{brand}"
    
    Réponds avec ce JSON exact :
    {{
        "cited": boolean, (La marque est-elle citée ?)
        "sentiment": string, (Positif/Neutre/Négatif)
        "sources_urls": list of strings, (Extrais toutes les URLs ou noms de domaine cités dans le texte qui recommandent ou parlent du sujet)
        "rank_impression": integer
    }}
    
    Texte à analyser :
    \"\"\"{llm_answer}\"\"\"
    """
    
    try:
        response = model_judge.generate_content(prompt)
        return json.loads(response.text)
    except Exception as e:
        return {"cited": False, "sentiment": "Error", "sources_urls": [], "rank_impression": 0}

# --- MAIN LOOP ---

if start_btn:
    questions_list = [q.strip() for q in input_questions.split('\n') if q.strip()]
    results = []
    
    progress_bar = st.progress(0)
    st_status = st.status("Recherche Google en cours...", expanded=True)
    
    for i, question in enumerate(questions_list):
        st_status.write(f"🌍 Recherche pour : {question}")
        
        # 1. Appel avec Grounding (Recherche Web réelle)
        llm_text = get_gemini_search_response(question)
        
        # 2. Analyse
        analysis = analyze_response_with_sources(llm_text, target_brand)
        
        # Nettoyage des sources pour l'affichage (on garde juste les domaines parfois c'est plus propre)
        sources_clean = ", ".join(analysis.get('sources_urls', [])[:3]) # On garde les 3 premières
        
        row = {
            "Question": question,
            "Présence": "✅" if analysis.get('cited') else "❌",
            "Sources (Influenceurs)": sources_clean, # NOUVEAU
            "Sentiment": analysis.get('sentiment'),
            "Réponse Complète": llm_text 
        }
        results.append(row)
        progress_bar.progress((i + 1) / len(questions_list))

    st_status.update(label="Audit Terminé !", state="complete", expanded=False)

    # --- RESULTS ---
    st.divider()
    if results:
        df = pd.DataFrame(results)
        
        # Affichage du tableau
        st.subheader("Résultats avec Sources Identifiées")
        st.dataframe(
            df[["Question", "Présence", "Sentiment", "Sources (Influenceurs)"]], 
            use_container_width=True
        )
        
        # Petit tuto d'interprétation
        st.info("💡 **Astuce GEO :** La colonne 'Sources' te montre les sites que l'IA a lus pour construire sa réponse. Si tu veux être cité par l'IA, tu dois obtenir des articles ou des liens sur ces sites précis (C'est ça, le GEO !).")

        with st.expander("Voir les réponses complètes"):
            for r in results:
                st.markdown(f"**Q: {r['Question']}**")
                st.markdown(r['Réponse Complète'])
                st.divider()
