import streamlit as st
import pandas as pd
from sqlalchemy import text
from storage.db import get_session

st.set_page_config(
    page_title="Plateforme de Veille Financière",
    page_icon="📊",
    layout="wide"
)

@st.cache_data(ttl=300)
def charger_documents(source=None, type_doc=None, limite=50):
    with get_session() as s:
        query = """
            SELECT source, type_document, titre,
                   date_publication, resume, url_source
            FROM documents
            WHERE statut_nlp = 'done'
            AND resume IS NOT NULL
        """
        params = {}
        if source and source != "Toutes":
            query += " AND source = :source"
            params["source"] = source
        if type_doc and type_doc != "Tous":
            query += " AND type_document = :type_doc"
            params["type_doc"] = type_doc
        query += " ORDER BY date_publication DESC LIMIT :l"
        params["l"] = limite
        rows = s.execute(text(query), params).fetchall()
        return pd.DataFrame(rows, columns=[
            "Source", "Type", "Titre",
            "Date", "Résumé", "URL"
        ])

@st.cache_data(ttl=300)
def charger_stats():
    with get_session() as s:
        return s.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN statut_nlp='done' THEN 1 ELSE 0 END) as resumes,
                SUM(CASE WHEN statut_nlp='pending' THEN 1 ELSE 0 END) as pending,
                COUNT(DISTINCT source) as sources
            FROM documents
        """)).fetchone()

# ── Sidebar ──────────────────────────────────────
with st.sidebar:
    st.title("📊 Veille Financière")
    st.caption("Plateforme de veille intelligente augmentée par l'IA")
    st.divider()
    source = st.selectbox(
        "Source", ["Toutes", "BAM", "AMMC", "BOURSE"]
    )
    type_doc = st.selectbox(
        "Type de document",
        ["Tous", "resume_seance", "bulletin_cote",
         "rapport", "communique", "circulaire"]
    )
    limite = st.slider("Nombre de documents", 10, 100, 20)

# ── KPIs ─────────────────────────────────────────
stats = charger_stats()
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total documents", stats.total)
col2.metric("Résumés générés", stats.resumes)
col3.metric("En attente NLP", stats.pending)
col4.metric("Sources actives", stats.sources)

st.divider()

# ── Graphique volume par jour ─────────────────────
st.subheader("📈 Volume de publications par jour")
with get_session() as s:
    df_vol = pd.DataFrame(
        s.execute(text("""
            SELECT date_publication::text as Date, 
                   COUNT(*) as Nombre
            FROM documents
            WHERE date_publication IS NOT NULL
            GROUP BY date_publication
            ORDER BY date_publication
        """)).fetchall(),
        columns=["Date", "Nombre"]
    )
if not df_vol.empty:
    import plotly.express as px
    fig = px.bar(df_vol, x="Date", y="Nombre",
                 labels={"Date": "Date", "Nombre": "Documents"})
    st.plotly_chart(fig, use_container_width=True)

# ── Graphique statut NLP ─────────────────────────
st.subheader("📈 Statut des documents")

with get_session() as s:
    df_statut = pd.DataFrame(
        s.execute(text("""
            SELECT 
                type_document as Type,
                COUNT(*) as Total,
                SUM(CASE WHEN statut_nlp='done' THEN 1 ELSE 0 END) as Résumés,
                SUM(CASE WHEN statut_nlp='pending' THEN 1 ELSE 0 END) as En_attente
            FROM documents
            GROUP BY type_document
        """)).fetchall(),
        columns=["Type", "Total", "Résumés", "En attente"]
    )

import plotly.express as px
fig = px.bar(
    df_statut.melt(id_vars="Type", 
                   value_vars=["Résumés", "En attente"],
                   var_name="Statut", value_name="Nombre"),
    x="Type", y="Nombre", color="Statut", barmode="group",
    color_discrete_map={"Résumés": "#2ecc71", "En attente": "#e74c3c"},
    labels={"Type": "Type de document", "Nombre": "Documents"}
)
st.plotly_chart(fig, use_container_width=True)

# ── Fil des résumés ───────────────────────────────
st.subheader("📄 Dernières publications analysées")
df = charger_documents(source, type_doc, limite)

if df.empty:
    st.info("Aucun document trouvé pour ces filtres.")
else:
    for _, row in df.iterrows():
        with st.expander(
            f"**[{row['Source']}]** {row['Titre']} "
            f"— {row['Date']}"
        ):
            st.write(row["Résumé"])
            if row["URL"]:
                st.markdown(
                    f"[Voir le document original]({row['URL']})"
                )