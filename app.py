import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
from duckduckgo_search import DDGS

# --- CONFIGURATION ---
st.set_page_config(page_title="GEO Tracker Pro (Architecture RAG)", layout="wide")

st.title("🕵️ GEO Tracker Pro (Architecture Perplexity)")
st.markdown("""
**La différence :** Au lieu de prier pour que l'IA cherche, ce script **force** une recherche Web réelle (Top 10 résultats) 
puis demande à l'IA d'analyser ta visibilité à l'intérieur.
""")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Paramètres")
    api_key = st.text_input("Ta clé API Google (AI Studio)", type="password")
    
    # Ici, on n'a plus besoin de modèle "Recherche", un modèle rapide suffit pour l'analyse
    model_name = "gemini-1.5-flash" 
    
    st.info("Moteur d'analyse : Gemini 1.5 Flash (Rapide & Gratuit)")

if api_key:
    genai.configure(api_key=api_key)
else:
    st.warning("Entre ta clé API Google pour commencer.")
    st.stop()

# --- INPUTS ---
col1, col2 = st.columns(2)
with col1:
    target_domain = st.text_input("Ton Domaine (ex: nike.com)", value="nike.com")
with col2:
    competitors = st.text_input("Concurrents", value="adidas.fr, asics.com")

input_questions = st.text_area(
    "Questions Commerciales (Intention d'achat)", 
    value="Meilleure chaussure running carbone 2024\nOù acheter des baskets marathon pas cher\nComparatif chaussures running pro"
)

start_btn = st.button("Lancer l'Audit Pro", type="primary")

# --- FONCTIONS ---

def search_web_real(query):
    """
    Simule une vraie recherche utilisateur via DuckDuckGo.
    Récupère les 10 premiers résultats (Titres + URLs + Résumés).
    """
    results_text = ""
    try:
        with DDGS() as ddgs:
            # On récupère 10 résultats
            results = list(ddgs.text(query, region='fr-fr', safesearch='off', max_results=10))
            
            if not results:
                return None, "Aucun résultat trouvé."

            # On formate ça proprement pour l'IA
            formatted_results = []
            for i, r in enumerate(results):
                clean_snippet = f"Position {i+1}:\n- Titre: {r['title']}\n- URL: {r['href']}\n- Extrait: {r['body']}\n"
                formatted_results.append(clean_snippet)
            
            return results, "\n".join(formatted_results)
            
    except Exception as e:
        return None, f"Erreur de recherche : {e}"

def analyze_serp_dominance(serp_text, domain, query):
    """
    L'IA agit comme un analyste SEO. Elle lit les résultats de recherche bruts.
    """
    model = genai.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json"})
    
    prompt = f"""
    Tu es un expert GEO (Generative Engine Optimization).
    Voici les résultats de recherche bruts pour la requête : "{query}".
    
    Ton objectif est d'analyser la visibilité du domaine : "{domain}".
    
    Données SERP (Search Engine Results Page) :
    \"\"\"{serp_text}\"\"\"
    
    Réponds impérativement avec ce JSON :
    {{
        "is_visible": boolean, (Est-ce que le domaine {domain} apparait dans les 10 résultats ?)
        "best_position": integer, (La position la plus haute trouvée, sinon 0)
        "sentiment_context": string, (Comment le domaine est présenté dans l'extrait ? Positif/Neutre/Absent)
        "competitors_present": string, (Liste les autres domaines majeurs présents)
        "recommendation": string (Conseil court pour améliorer la visibilité sur cette requête)
    }}
    """
    
    try:
        res = model.generate_content(prompt)
        return json.loads(res.text)
    except Exception as e:
        return {"is_visible": False, "best_position": 0, "sentiment_context": "Erreur Analyse", "recommendation": str(e)}

# --- MAIN LOOP ---

if start_btn:
    questions_list = [q.strip() for q in input_questions.split('\n') if q.strip()]
    results_data = []
    
    progress_bar = st.progress(0)
    
    for i, question in enumerate(questions_list):
        
        # 1. VRAIE RECHERCHE (Python)
        raw_results, text_for_ai = search_web_real(question)
        
        # 2. ANALYSE IA (Gemini)
        if raw_results:
            analysis = analyze_serp_dominance(text_for_ai, target_domain, question)
        else:
            analysis = {"is_visible": False, "best_position": 0, "sentiment_context": "Erreur Search", "competitors_present": "", "recommendation": "Vérifier la recherche"}

        # Stockage
        results_data.append({
            "Requête": question,
            "Visible ?": "✅ OUI" if analysis['is_visible'] else "❌ NON",
            "Position": analysis['best_position'] if analysis['best_position'] > 0 else "-",
            "Concurrents": analysis.get('competitors_present', 'N/A'),
            "Conseil GEO": analysis.get('recommendation', 'N/A'),
            "Raw Data": text_for_ai # Pour le debug
        })
        
        progress_bar.progress((i + 1) / len(questions_list))

    st.success("Audit terminé !")
    
    if results_data:
        df = pd.DataFrame(results_data)
        
        # KPIs
        visible_count = df[df["Visible ?"] == "✅ OUI"].shape[0]
        st.metric("Taux de Présence (Top 10)", f"{visible_count}/{len(questions_list)}")
        
        # Tableau Principal
        st.dataframe(
            df[["Requête", "Visible ?", "Position", "Concurrents", "Conseil GEO"]],
            use_container_width=True
        )
        
        st.divider()
        st.subheader("🔍 Preuve des Résultats (Ce que l'IA a lu)")
        
        for index, row in df.iterrows():
            with st.expander(f"Détail SERP : {row['Requête']}"):
                if row['Visible ?'] == "✅ OUI":
                    st.success(f"Bravo ! Trouvé en position {row['Position']}")
                else:
                    st.error("Absent du Top 10.")
                
                st.text("Voici les 10 résultats analysés :")
                st.code(row['Raw Data'], language="text")
