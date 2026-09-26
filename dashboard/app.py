import os
import re
import json
import socket
import urllib.parse
import pandas as pd
import streamlit as st
import plotly.express as px
from sqlalchemy import text
from storage.db import get_session

st.set_page_config(
    page_title="Plateforme de Veille Financière",
    page_icon="📊",
    layout="wide"
)

# ── Fonctions Utilitaires ─────────────────────────

def verifier_connexion():
    try:
        socket.getaddrinfo("aws-0-eu-west-3.pooler.supabase.com", 5432)
    except socket.gaierror:
        st.error("✗ Supabase inaccessible — vérifie ton réseau ou VPN")
        st.stop()

def surligner(texte: str, mot: str) -> str:
    if not mot or not texte:
        return texte or ""
    pattern = re.compile(re.escape(mot), re.IGNORECASE)
    return pattern.sub(f"**{mot}**", texte)

def nettoyer_titre(titre, date=None) -> str:
    """Décode les URLs dans les titres et nettoie les valeurs Null/None."""
    if not titre or str(titre).strip() in ["None", "(PDF) — None", ""]:
        titre_propre = "Document sans titre"
    else:
        titre_propre = urllib.parse.unquote_plus(str(titre)).strip()
        if titre_propre.endswith("— None"):
            titre_propre = titre_propre[:-6].strip()

    if date:
        date_str = date.strftime("%d/%m/%Y") if hasattr(date, "strftime") else str(date)
        return f"{titre_propre} — {date_str}"
    return titre_propre

# ── Fonctions de chargement ───────────────────────

@st.cache_data(ttl=300)
def charger_stats():
    verifier_connexion()
    with get_session() as s:
        return s.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN statut_nlp='done' THEN 1 ELSE 0 END) as resumes,
                SUM(CASE WHEN statut_nlp='pending' THEN 1 ELSE 0 END) as pending,
                COUNT(DISTINCT source) as sources,
                SUM(CASE WHEN classification='RISQUE' THEN 1 ELSE 0 END) as risques,
                SUM(CASE WHEN classification='OPPORTUNITE' THEN 1 ELSE 0 END) as opportunites
            FROM documents
        """)).fetchone()

@st.cache_data(ttl=300)
def charger_score_jour():
    verifier_connexion()
    with get_session() as s:
        return s.execute(text("""
            SELECT AVG(niveau_impact) as score_moyen,
            MAX(date_publication) as date_reference
            FROM documents
            WHERE date_publication = (
                SELECT MAX(date_publication) FROM documents
            )
            AND niveau_impact IS NOT NULL
        """)).fetchone()

# La derniere alerte a ete generee
'''
@st.cache_data(ttl=3600)
def charger_derniere_alerte():
    with get_session() as s:
        return s.execute(text("""
            SELECT niveau, titre, message, sources_citees
            FROM alertes_synthese
            WHERE date_generation >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY date_generation DESC
            LIMIT 1
        """)).fetchone()

'''
@st.cache_data(ttl=3600)
def charger_derniere_alerte():
    with get_session() as s:
        return s.execute(text("""
            SELECT niveau, titre, message, sources_citees, date_generation
            FROM alertes_synthese
            ORDER BY date_generation DESC
            LIMIT 1
        """)).fetchone()

@st.cache_data(ttl=3600)
def charger_urls_sources(titres_sources):
    if not titres_sources:
        return []
    titres_list = list(titres_sources) if isinstance(titres_sources, (list, set)) else json.loads(titres_sources)
    if not titres_list:
        return []
    with get_session() as s:
        return s.execute(text("""
            SELECT titre, url_source, source
            FROM documents
            WHERE titre = ANY(:titres)
        """), {"titres": titres_list}).fetchall()

@st.cache_data(ttl=300)
def charger_alertes():
    verifier_connexion()
    with get_session() as s:
        rows = s.execute(text("""
            SELECT titre, resume, date_publication, niveau_impact, url_source, justification_impact
            FROM documents
            WHERE classification = 'RISQUE'
            AND niveau_impact >= 2
            AND resume IS NOT NULL
            ORDER BY date_publication DESC
            LIMIT 5
        """)).fetchall()
        return pd.DataFrame(rows, columns=["Titre", "Résumé", "Date", "Score", "URL", "Justification"])

@st.cache_data(ttl=300)
def charger_documents(source=None, classification=None, recherche=None, limite=20):
    with get_session() as s:
        query = """
            SELECT source, type_document, titre, date_publication, 
                   resume, classification, niveau_impact, url_source, justification_impact
            FROM documents
            WHERE statut_nlp = 'done'
            AND resume IS NOT NULL
        """
        params = {}
        if source and source != "Toutes":
            query += " AND source = :source"
            params["source"] = source
        if classification and classification != "Toutes":
            query += " AND classification = :classification"
            params["classification"] = classification
        if recherche:
            query += """ AND (
                resume ILIKE :recherche 
                OR titre ILIKE :recherche
                OR texte_nettoye ILIKE :recherche
            )"""
            params["recherche"] = f"%{recherche}%"
        query += " ORDER BY date_publication DESC LIMIT :l"
        params["l"] = limite
        rows = s.execute(text(query), params).fetchall()
        return pd.DataFrame(rows, columns=["Source", "Type", "Titre", "Date", "Résumé", "Classification", "Impact", "URL", "Justification"])

@st.cache_data(ttl=300)
def charger_repartition():
    verifier_connexion()
    with get_session() as s:
        rows = s.execute(text("""
            SELECT classification, COUNT(*) as nb
            FROM documents
            WHERE classification IS NOT NULL
            GROUP BY classification
        """)).fetchall()
        return pd.DataFrame(rows, columns=["Classification", "Nombre"])

@st.cache_data(ttl=300)
def charger_signaux_faibles():
    with get_session() as s:
        rows = s.execute(text("""
            SELECT 
                id, titre, source, date_publication, url_source,
                signal_info->>'secteur' as secteur,
                signal_info->>'type_signal' as type_signal,
                signal_info->>'resume_signal' as resume_signal,
                signal_info->>'explication' as explication,
                signal_info->'mots_cles' as mots_cles,
                COALESCE(signal_info->>'force_signal', signal_info->>'niveau') as force_signal
            FROM documents
            WHERE signal_info IS NOT NULL
            AND (signal_info->>'est_signal_faible')::boolean = true
            ORDER BY date_publication DESC
            LIMIT 10
        """)).fetchall()
        return pd.DataFrame(rows, columns=[
            "ID", "Titre", "Source", "Date", "URL", 
            "Secteur", "Type", "Résumé Signal", "Explication", "Mots-clés", "Force Signal"
        ])

# ── Sidebar ───────────────────────────────────────
with st.sidebar:
    st.title("📊 Veille Financière")
    st.caption("Plateforme de veille intelligente augmentée par l'IA")
    st.divider()
    
    recherche = st.text_input(
        "🔍 Rechercher un mot-clé",
        placeholder="ex: liquidité, dividende, sanction..."
    )
    
    source = st.selectbox("Source", ["Toutes", "BAM", "AMMC", "BOURSE"])
    classification = st.selectbox("Classification", ["Toutes", "RISQUE", "OPPORTUNITE", "NEUTRE"])
    limite = st.slider("Nombre de documents", 0, 1000, 1)


# ── Alerte Synthèse Hebdomadaire Encadrée ──────────
alerte = charger_derniere_alerte()
if alerte:
    sources_titres = alerte.sources_citees
    if isinstance(sources_titres, str):
        try:
            sources_titres = json.loads(sources_titres)
        except Exception:
            sources_titres = []

    docs_sources = charger_urls_sources(sources_titres)
    
    # Calcul du nombre de documents analysés pour l'accroche
    nb_docs = len(docs_sources) if docs_sources else len(sources_titres)

    config = {
        "risque": {
            "badge": "🔴 RISQUE POTENTIEL DÉTECTÉ",
            "bg": "#fde8e8",
            "color": "#9b1c1c",
            "border": "#f8b4b4"
        },
        "opportunite": {
            "badge": "🟢 OPPORTUNITÉ DÉTECTÉE",
            "bg": "#def7ec",
            "color": "#03543f",
            "border": "#84e1bc"
        },
        "neutre": {
            "badge": "ℹ️ CLIMAT DU MARCHÉ",
            "bg": "#e1effe",
            "color": "#1e429f",
            "border": "#a4cafe"
        }
    }.get(alerte.niveau, {
        "badge": "ℹ️ SYNTHÈSE HEBDOMADAIRE",
        "bg": "#f3f4f6",
        "color": "#374151",
        "border": "#d1d5db"
    })

    with st.container(border=True):
        st.markdown(
            f"<span style='background-color:{config['bg']}; color:{config['color']}; "
            f"border: 1px solid {config['border']}; padding: 4px 12px; border-radius: 20px; "
            f"font-weight: 600; font-size: 0.78em; text-transform: uppercase; letter-spacing: 0.5px;'>"
            f"{config['badge']}</span>",
            unsafe_allow_html=True
        )

        st.markdown(f"### {alerte.titre}")
        
        # 💡 Ajout du message introductif descriptif et dynamique
        st.markdown(
            f"<p style='font-size:0.95em; color:#4b5563; margin-bottom:12px; font-style: italic;'>"
            f"💡 <b>Contexte de veille :</b> D'après l'analyse croisée des <b>{nb_docs} publications</b> "
            f"collectées cette semaine sur le marché financier marocain, on remarque ce qui suit :"
            f"</p>",
            unsafe_allow_html=True
        )

        st.markdown(f"<p style='font-size:1.02em; line-height:1.6; color:#2c3e50;'>{alerte.message}</p>", unsafe_allow_html=True)

        if docs_sources:
            st.markdown("<p style='font-size:0.85em; font-weight:600; margin-top:12px; color:#6b7280;'>📄 Documents sources analysés (cliquer pour ouvrir) :</p>", unsafe_allow_html=True)
            badges_html = []
            for doc in docs_sources:
                # Sécurisation des espaces dans les URLs pour éviter de casser le lien cliquable
                raw_url = doc.url_source if doc.url_source else "#"
                url = urllib.parse.quote(raw_url, safe=":/%?=#&")
                
                titre_nettoye = nettoyer_titre(doc.titre)
                titre_court = (titre_nettoye[:55] + "...") if len(titre_nettoye) > 55 else titre_nettoye
                badges_html.append(
                    f"<a href='{url}' target='_blank' style='display: inline-block; "
                    f"background-color: #ffffff; color: #1f2937; padding: 5px 12px; "
                    f"margin: 3px 6px 3px 0; border-radius: 6px; text-decoration: none; "
                    f"font-size: 0.8em; border: 1px solid #e5e7eb; font-weight: 500; box-shadow: 0 1px 2px rgba(0,0,0,0.05);'>"
                    f"🔗 [{doc.source}] {titre_court}</a>"
                )
            st.markdown("".join(badges_html), unsafe_allow_html=True)
        elif sources_titres:
            st.caption(f"Sources citées : {', '.join(sources_titres)}")

        st.caption("🤖 *Synthèse automatique basée sur les documents collectés lors des 7 à 14 derniers jours.*")

    st.divider()


# ── KPIs ─────────────────────────────────────────
stats = charger_stats()

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    with st.container(border=True):
        st.metric("Documents", stats.total, help="Total des documents collectés")
with col2:
    with st.container(border=True):
        st.metric("Résumés générés", stats.resumes)
with col3:
    with st.container(border=True):
        st.metric("En attente NLP", stats.pending)
with col4:
    with st.container(border=True):
        st.metric("Risques", stats.risques or 0, delta="🔴 Risque", delta_color="inverse")
with col5:
    with st.container(border=True):
        st.metric("Opportunités", stats.opportunites or 0, delta="🟢 Opportunité", delta_color="normal")

st.divider()


# ── Score du jour & Répartition ───────────────────
score_jour = charger_score_jour()
score = score_jour.score_moyen if score_jour and score_jour.score_moyen else None

col_score, col_repartition = st.columns([1, 2])

with col_score:
    st.subheader("🎯 Impact moyen du jour")
    with st.container(border=True):
        if score:
            date_ref = score_jour.date_reference.strftime('%d/%m/%Y')
            if score >= 2.5:
                st.error(f"🔴 **Impact ÉLEVÉ**\n\nImpact moyen : **{score:.1f}/3**\n\n*({date_ref})*")
            elif score >= 1.5:
                st.warning(f"🟠 **Impact MODÉRÉ**\n\nImpact moyen : **{score:.1f}/3**\n\n*({date_ref})*")
            else:
                st.success(f"🟢 **Impact FAIBLE**\n\nImpact moyen : **{score:.1f}/3**\n\n*({date_ref})*")
        else:
            st.info("Aucun document disponible.")


with col_repartition:
    st.subheader("📊 Répartition des signaux")
    df_rep = charger_repartition()
    if not df_rep.empty:
        fig = px.pie(
            df_rep,
            values="Nombre",
            names="Classification",
            color="Classification",
            hole=0.5,
            color_discrete_map={
                "RISQUE": "#e74c3c",
                "OPPORTUNITE": "#2ecc71",
                "NEUTRE": "#95a5a6"
            }
        )
        fig.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            height=220,
            showlegend=True
        )
        st.plotly_chart(fig, use_container_width=True)

st.divider()


# ── Alertes de risque ─────────────────────────────
st.subheader("🚨 Dernières alertes de risque")
df_alertes = charger_alertes()

if df_alertes.empty:
    st.info("Aucune alerte de risque détectée récemment.")
else:
    for _, row in df_alertes.iterrows():
        niveau = "🔴" if row["Score"] == 3 else "🟠"
        titre_affiche = nettoyer_titre(row["Titre"], row["Date"])
        with st.expander(f"{niveau} {titre_affiche}"):
            st.write(row["Résumé"])
            if pd.notnull(row["Justification"]) and row["Justification"]:
                st.caption(f"💡 **Justification d'impact ({row['Score']}/3) :** {row['Justification']}")
            if row["URL"]:
                st.markdown(f"[🔗 Voir le document original]({row['URL']})")

st.divider()


# ── Signaux Faibles ───────────────────────────────
st.subheader("📡 Signaux faibles & Tendances émergentes")
st.caption("Alerte précoce sur des changements sectoriels ou réglementaires discrets.")

df_signaux = charger_signaux_faibles()

if df_signaux.empty:
    st.info("Aucun signal faible détecté pour le moment.")
else:
    for _, row in df_signaux.iterrows():
        badge_color = "🔴" if row["Type"] == "RISQUE_EMERGENT" else "🟢"
        titre_net = nettoyer_titre(row["Titre"])
        force = row["Force Signal"] 
        txt_nettete = f" *(Netteté : {force}/3)*" if pd.notnull(force) and str(force) != "N/A" else ""
        
        with st.container(border=True):
            col_sec, col_src = st.columns([3, 1])
            with col_sec:
                st.markdown(f"**{badge_color} [{row['Secteur']}]** — *{row['Résumé Signal']}*{txt_nettete}")
            with col_src:
                st.caption(f"📍 {row['Source']} · {row['Date']}")
            
            st.write(f"🔍 **Analyse :** {row['Explication']}")
            
            # Affichage des tags mots-clés
            mots = row["Mots-clés"]
            if isinstance(mots, str):
                try:
                    mots = json.loads(mots)
                except Exception:
                    mots = []
            if mots:
                tags_html = "".join([f"<span style='background-color:#eef2f6; color:#334155; padding:2px 8px; border-radius:4px; font-size:0.75em; margin-right:4px;'>#{m}</span>" for m in mots])
                st.markdown(tags_html, unsafe_allow_html=True)
            
            if row["URL"]:
                st.markdown(f"[🔗 Consulter la source]({row['URL']})")
st.divider()


# ── Fil des Publications ──────────────────────────
st.subheader("📄 Publications analysées")

if recherche:
    st.caption(f"Résultats de recherche pour : « {recherche} »")

df = charger_documents(source, classification, recherche, limite)

if df.empty:
    if recherche:
        st.warning(f"Aucun document ne contient le mot-clé « {recherche} »")
    else:
        st.info("Aucun document correspondant à ces filtres.")
else:
    label_map = {"RISQUE": "🔴", "OPPORTUNITE": "🟢", "NEUTRE": "⚪"}
    for _, row in df.iterrows():
        emoji = label_map.get(row["Classification"], "⚪")
        titre_clean = nettoyer_titre(row["Titre"], row["Date"])
        
        with st.expander(f"{emoji} **[{row['Source']}]** {titre_clean}"):
            if row["Classification"]:
                impact_text = f" | Niveau d'impact : **{row['Impact']}/3**" if pd.notnull(row["Impact"]) else ""
                st.caption(f"Classification : **{row['Classification']}**{impact_text}")
            
            if pd.notnull(row["Justification"]) and row["Justification"]:
                st.markdown(f"💡 **Justification d'impact :** {row['Justification']}")
            
            resume_affiche = surligner(row["Résumé"], recherche) if recherche else row["Résumé"]
            st.markdown(resume_affiche)
            
            if row["URL"]:
                # Encode uniquement les espaces et caractères spéciaux de l'URL
                url_securisee = urllib.parse.quote(row["URL"], safe=":/%?=#&")
                st.markdown(f"[🔗 Voir le document original]({url_securisee})")