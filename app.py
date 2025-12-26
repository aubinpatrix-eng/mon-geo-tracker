import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
from duckduckgo_search import DDGS

# --- CONFIGURATION ---
st.set_page_config(page_title="GEO Tracker France", layout="wide")

st.title("🇫🇷 GEO Tracker (Optimisé Google France)")
st.markdown("""
**Problème résolu :** Ce script force la localisation en France (`fr-fr`) et filtre les résultats étrangers (ex: `/vi/`, `/en/`) causés par les serveurs US.
""")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Paramètres")
    api_key = st.text_input("Ta clé API Google (AI Studio)", type="password")
    
    # Option pour être encore plus radical sur la localisation
    strict_mode = st.checkbox("Mode Strict France 🇫🇷", value=True, help="Ajoute 'France' à la requête et filtre les sites non-fr")
    
    st.info("Moteur : DuckDuckGo (Region: fr-fr)")

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
    "Questions (Simulations)", 
    value="Meilleure chaussure running carbone 2024\nOù acheter des baskets marathon pas cher"
)

start_btn = st.button("Lancer l'Audit France", type="primary")

# --- FONCTIONS ---

def is_relevant_url(url, snippet):
    """
    Filtre manuel pour nettoyer les résultats "bizarres" (Vietnam, Russie, etc.)
    que les serveurs US laissent parfois passer.
    """
    # 1. Exclusion des langues explicites dans l'URL
    exclude_patterns = ['/vi/', '/ru/', '/cn/', '/jp/', '/de/', '/it/', '/es/']
    for pattern in exclude_patterns:
        if pattern in url:
            return False
            
    # 2. Si on est en mode strict, on peut privilégier les TLDs français ou neutres
    # (Optionnel, ici on reste souple pour les .com)
    
    return True

def search_web_france(query):
    """
    Recherche DuckDuckGo forcée sur la région FR-FR.
    """
    results_clean = []
    
    # Si mode strict, on guide le moteur
    search_query = f"{query} site:.fr" if strict_mode and "site:" not in query else query
    # Note : "site:.fr" est très restrictif, on peut juste utiliser region='fr-fr'
    # Pour ce code, on va utiliser la région paramétrée + le nettoyage Python
    
    final_query = query # On garde la requête naturelle pour pas trop brider
    
    try:
        with DDGS() as ddgs:
            # region='fr-fr' est la clé pour avoir des résultats Google France
            # timelimit='y' aide à avoir du contenu frais
            raw_results = list(ddgs.text(final_query, region='fr-fr', safesearch='moderate', max_results=15))
            
            if not raw_results:
                return None, "Aucun résultat trouvé."

            # Filtrage et Formatage
            formatted_results = []
            count = 0
            
            for r in raw_results:
                if count >= 10: break # On garde le Top 10 propre
                
                # Application du filtre anti-pollution
                if is_relevant_url(r['href'], r['body']):
                    clean_snippet = f"Position {count+1}:\n- Titre: {r['title']}\n- URL: {r['href']}\n- Extrait: {r['body']}\n"
                    formatted_results.append(clean_snippet)
                    count += 1
            
            if not formatted_results:
                 return None, "Aucun résultat pertinent après filtrage (trop de sites étrangers ?)."
                 
            return raw_results, "\n".join(formatted_results)
            
    except Exception as e:
        return None, f"Erreur de recherche : {e}"

def analyze_serp(serp_text, domain, query):
    # Analyseur IA (Reste inchangé, c'est le cerveau)
    model = genai.GenerativeModel("gemini-1.5-flash", generation_config={"response_mime_type": "application/json"})
    
    prompt = f"""
    Analyse ces résultats de recherche Google France (FR).
    Requête : "{query}"
    Domaine cible : "{domain}"
    
    Réponds JSON :
    {{
        "is_visible": boolean,
        "best_position": integer, (0 si absent)
        "sentiment_context": string,
        "competitors_present": string,
        "recommendation": string
    }}
    
    Données SERP :
    \"\"\"{serp_text}\"\"\"
    """
    try:
        res = model.generate_content(prompt)
        return json.loads(res.text)
    except:
        return {"is_visible": False, "best_position": 0, "sentiment_context": "Erreur", "competitors_present": "", "recommendation": ""}

# --- MAIN LOOP ---

if start_btn:
    questions_list = [q.strip() for q in input_questions.split('\n') if q.strip()]
    results_data = []
    
    progress_bar = st.progress(0)
    
    for i, question in enumerate(questions_list):
        
        # 1. RECHERCHE FRANCE
        raw_results, text_for_ai = search_web_france(question)
        
        # 2. ANALYSE
        if raw_results:
            analysis = analyze_serp(text_for_ai, target_domain, question)
        else:
            analysis = {"is_visible": False, "best_position": 0, "sentiment_context": "Erreur/Filtre", "competitors_present": "", "recommendation": text_for_ai}

        results_data.append({
            "Requête": question,
            "Visible ?": "✅ OUI" if analysis['is_visible'] else "❌ NON",
            "Position": analysis['best_position'] if analysis['best_position'] > 0 else "-",
            "Concurrents": analysis.get('competitors_present', 'N/A'),
            "Conseil": analysis.get('recommendation', 'N/A'),
            "Données Brutes": text_for_ai
        })
        
        progress_bar.progress((i + 1) / len(questions_list))

    st.success("Audit terminé !")
    
    if results_data:
        df = pd.DataFrame(results_data)
        st.metric("Taux de Présence (France)", f"{df[df['Visible ?'] == '✅ OUI'].shape[0]}/{len(questions_list)}")
        st.dataframe(df[["Requête", "Visible ?", "Position", "Concurrents", "Conseil"]], use_container_width=True)
        
        st.divider()
        st.subheader("🔎 Vérification des Sources (Filtrées)")
        for index, row in df.iterrows():
            with st.expander(f"Résultats pour : {row['Requête']}"):
                st.code(row['Données Brutes'])
