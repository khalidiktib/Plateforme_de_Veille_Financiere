import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text
from storage.db import get_session

st.set_page_config(
    page_title="Plateforme de Veille Financière",
    page_icon="📊",
    layout="wide"
)

# ── Fonctions de chargement ───────────────────────

@st.cache_data(ttl=300)
def charger_stats():
    with get_session() as s:
        return s.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN statut_nlp='done' 
                    THEN 1 ELSE 0 END) as resumes,
                SUM(CASE WHEN statut_nlp='pending' 
                    THEN 1 ELSE 0 END) as pending,
                COUNT(DISTINCT source) as sources,
                SUM(CASE WHEN classification='RISQUE' 
                    THEN 1 ELSE 0 END) as risques,
                SUM(CASE WHEN classification='OPPORTUNITE' 
                    THEN 1 ELSE 0 END) as opportunites
            FROM documents
        """)).fetchone()

@st.cache_data(ttl=300)
def charger_score_jour():
    with get_session() as s:
        return s.execute(text("""
            SELECT AVG(score_risque) as score_moyen
            FROM documents
            WHERE date_publication = CURRENT_DATE
            AND score_risque IS NOT NULL
        """)).fetchone()

@st.cache_data(ttl=300)
def charger_alertes():
    with get_session() as s:
        rows = s.execute(text("""
            SELECT titre, resume, date_publication, 
                   score_risque, url_source
            FROM documents
            WHERE classification = 'RISQUE'
            AND score_risque >= 2
            AND resume IS NOT NULL
            ORDER BY date_publication DESC
            LIMIT 5
        """)).fetchall()
        return pd.DataFrame(rows, columns=[
            "Titre", "Résumé", "Date",
            "Score", "URL"
        ])

@st.cache_data(ttl=300)
def charger_documents(source=None, classification=None, 
                      limite=20):
    with get_session() as s:
        query = """
            SELECT source, type_document, titre,
                   date_publication, resume, 
                   classification, score_risque, url_source
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
        query += " ORDER BY date_publication DESC LIMIT :l"
        params["l"] = limite
        rows = s.execute(text(query), params).fetchall()
        return pd.DataFrame(rows, columns=[
            "Source", "Type", "Titre", "Date",
            "Résumé", "Classification", "Score", "URL"
        ])

@st.cache_data(ttl=300)
def charger_repartition():
    with get_session() as s:
        rows = s.execute(text("""
            SELECT classification, COUNT(*) as nb
            FROM documents
            WHERE classification IS NOT NULL
            GROUP BY classification
        """)).fetchall()
        return pd.DataFrame(rows, 
                            columns=["Classification", "Nombre"])

# ── Sidebar ───────────────────────────────────────
with st.sidebar:
    st.title("📊 Veille Financière")
    st.caption("Plateforme de veille intelligente "
               "augmentée par l'IA")
    st.divider()
    source = st.selectbox(
        "Source", ["Toutes", "BAM", "AMMC", "BOURSE"]
    )
    classification = st.selectbox(
        "Classification",
        ["Toutes", "RISQUE", "OPPORTUNITE", "NEUTRE"]
    )
    limite = st.slider("Nombre de documents", 10, 100, 20)

# ── KPIs ─────────────────────────────────────────
stats = charger_stats()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Documents collectés", stats.total)
col2.metric("Résumés générés", stats.resumes)
col3.metric("En attente NLP", stats.pending)
col4.metric("🔴 Risques détectés", stats.risques or 0)
col5.metric("🟢 Opportunités", stats.opportunites or 0)

st.divider()

# ── Score du jour ─────────────────────────────────
score_jour = charger_score_jour()
score = score_jour.score_moyen if score_jour.score_moyen else None

col_score, col_repartition = st.columns([1, 2])

with col_score:
    st.subheader("🎯 Score du jour")
    if score:
        if score >= 2.5:
            st.error(f"🔴 Risque ÉLEVÉ\nScore : {score:.1f}/3")
        elif score >= 1.5:
            st.warning(f"🟠 Risque MODÉRÉ\nScore : {score:.1f}/3")
        else:
            st.success(f"🟢 Risque FAIBLE\nScore : {score:.1f}/3")
    else:
        st.info("Aucune donnée pour aujourd'hui")

with col_repartition:
    st.subheader("📊 Répartition des signaux")
    df_rep = charger_repartition()
    if not df_rep.empty:
        fig = px.pie(
            df_rep,
            values="Nombre",
            names="Classification",
            color="Classification",
            color_discrete_map={
                "RISQUE": "#e74c3c",
                "OPPORTUNITE": "#2ecc71",
                "NEUTRE": "#95a5a6"
            }
        )
        fig.update_layout(margin=dict(t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Alertes ───────────────────────────────────────
st.subheader("🚨 Dernières alertes de risque")
df_alertes = charger_alertes()

if df_alertes.empty:
    st.info("Aucune alerte active.")
else:
    for _, row in df_alertes.iterrows():
        niveau = "🔴" if row["Score"] == 3 else "🟠"
        with st.expander(
            f"{niveau} {row['Titre']} — {row['Date']}"
        ):
            st.write(row["Résumé"])
            if row["URL"]:
                st.markdown(
                    f"[Voir le document]({row['URL']})"
                )

st.divider()

# ── Fil des publications ──────────────────────────
st.subheader("📄 Publications analysées")
df = charger_documents(source, classification, limite)

if df.empty:
    st.info("Aucun document pour ces filtres.")
else:
    for _, row in df.iterrows():
        label_map = {
            "RISQUE": "🔴",
            "OPPORTUNITE": "🟢",
            "NEUTRE": "⚪"
        }
        emoji = label_map.get(row["Classification"], "⚪")
        with st.expander(
            f"{emoji} **[{row['Source']}]** {row['Titre']} "
            f"— {row['Date']}"
        ):
            if row["Classification"]:
                st.caption(
                    f"Classification : **{row['Classification']}** "
                    f"| Score risque : **{row['Score']}/3**"
                )
            st.write(row["Résumé"])
            if row["URL"]:
                st.markdown(
                    f"[Voir le document original]({row['URL']})"
                )