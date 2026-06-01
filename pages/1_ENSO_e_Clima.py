"""Página 1 — ENSO, Precipitação e NDVI"""
import sys
sys.path.insert(0, ".")

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.dados import carregar_oni, carregar_precipitacao, carregar_ndvi

st.set_page_config(page_title="ENSO & Clima · AgroClima", page_icon="🌧️", layout="wide")

st.title("🌧️ ENSO, Precipitação e Vegetação")
st.markdown("Histórico dos sinais climáticos que alimentam o modelo de previsão.")
st.divider()

df_oni    = carregar_oni()
df_precip = carregar_precipitacao()
df_ndvi   = carregar_ndvi()

# ── Seletor de período ────────────────────────────────────────────────────────
anos = sorted(df_oni["ano"].unique())
col1, col2 = st.columns([1, 3])
with col1:
    ano_ini = st.selectbox("De", anos, index=anos.index(2015))
    ano_fim = st.selectbox("Até", anos, index=len(anos)-1)

# ── ONI histórico ─────────────────────────────────────────────────────────────
st.subheader("📡 Índice ONI — El Niño / La Niña")

df_oni_f = df_oni[(df_oni["ano"] >= ano_ini) & (df_oni["ano"] <= ano_fim)]

fig_oni = go.Figure()
fig_oni.add_hrect(y0=0.5,  y1=3,   fillcolor="#e74c3c", opacity=0.08, line_width=0)
fig_oni.add_hrect(y0=-3,   y1=-0.5,fillcolor="#3498db", opacity=0.08, line_width=0)
fig_oni.add_hline(y=0,    line_dash="dash", line_color="gray",    line_width=0.8)
fig_oni.add_hline(y=0.5,  line_dash="dot",  line_color="#e74c3c", line_width=0.7)
fig_oni.add_hline(y=-0.5, line_dash="dot",  line_color="#3498db", line_width=0.7)

fig_oni.add_trace(go.Scatter(
    x=df_oni_f["data"], y=df_oni_f["oni"],
    name="ONI", line=dict(color="#2c3e50", width=2),
))
fig_oni.add_trace(go.Scatter(
    x=df_oni_f["data"], y=df_oni_f["oni"].where(df_oni_f["oni"] >= 0.5),
    fill="tozeroy", fillcolor="rgba(231,76,60,0.25)",
    line=dict(width=0), name="El Niño",
))
fig_oni.add_trace(go.Scatter(
    x=df_oni_f["data"], y=df_oni_f["oni"].where(df_oni_f["oni"] <= -0.5),
    fill="tozeroy", fillcolor="rgba(52,152,219,0.25)",
    line=dict(width=0), name="La Niña",
))
fig_oni.update_layout(
    height=280, yaxis=dict(title="Anomalia (°C)", range=[-2.8, 2.8]),
    margin=dict(l=0,r=0,t=0,b=0),
    legend=dict(orientation="h", y=1.1),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig_oni, use_container_width=True)

with st.expander("O que é o ONI?"):
    st.markdown("""
    O **Oceanic Niño Index (ONI)** mede a anomalia de temperatura da superfície
    do Oceano Pacífico Equatorial.
    - **ONI ≥ +0.5** por 5 meses consecutivos = **El Niño** → seca no Nordeste
    - **ONI ≤ -0.5** por 5 meses consecutivos = **La Niña** → enchentes no Sul
    - É previsível com **6 a 9 meses de antecedência**, por isso é o coração do modelo.
    """)

st.divider()

# ── Precipitação ──────────────────────────────────────────────────────────────
st.subheader("🌧️ Precipitação Mensal por Região")

col_reg, col_tip = st.columns([2, 1])
with col_reg:
    regiao_sel = st.radio("Região", ["Nordeste", "Sul"], horizontal=True)
with col_tip:
    tipo_vis = st.radio("Visualização", ["Média regional", "Por estado"], horizontal=True)

df_p = df_precip[
    (df_precip["regiao"] == regiao_sel) &
    (df_precip["ano"] >= ano_ini) &
    (df_precip["ano"] <= ano_fim)
].copy()
df_p["data"] = pd.to_datetime(df_p["periodo"], format="%Y%m")

if tipo_vis == "Média regional":
    df_media = df_p.groupby("data")["precipitacao_mm_total"].mean().reset_index()
    media_hist = df_media["precipitacao_mm_total"].mean()

    fig_p = go.Figure()
    fig_p.add_hline(y=media_hist, line_dash="dash", line_color="gray",
                    line_width=1, annotation_text=f"Média: {media_hist:.0f}mm")
    fig_p.add_trace(go.Bar(
        x=df_media["data"], y=df_media["precipitacao_mm_total"],
        marker_color=df_media["precipitacao_mm_total"].apply(
            lambda v: "#e74c3c" if v < media_hist * 0.5 else
                      "#3498db" if v > media_hist * 1.5 else "#7fb3d3"
        ),
        name="Precipitação",
    ))
    fig_p.update_layout(
        height=280, yaxis_title="mm/mês",
        margin=dict(l=0,r=0,t=0,b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_p, use_container_width=True)
    st.caption("🔴 Vermelho = abaixo de 50% da média (seca) · 🔵 Azul escuro = acima de 150% (excesso)")
else:
    fig_p2 = px.line(
        df_p, x="data", y="precipitacao_mm_total",
        color="estado", title=f"Precipitação por estado — {regiao_sel}",
        labels={"precipitacao_mm_total": "mm/mês", "data": ""},
    )
    fig_p2.update_layout(height=300, margin=dict(l=0,r=0,t=30,b=0),
                         paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_p2, use_container_width=True)

st.divider()

# ── NDVI (NASA) ───────────────────────────────────────────────────────────────
st.subheader("🛰️ NDVI — Saúde da Vegetação (NASA MODIS)")
st.caption("Índice de vegetação obtido por satélite. Quanto mais alto, mais verde e produtiva a lavoura.")

df_n = df_ndvi[
    (df_ndvi["regiao"] == regiao_sel) &
    (df_ndvi["ano"] >= ano_ini) &
    (df_ndvi["ano"] <= ano_fim)
].copy()
df_n["data"] = pd.to_datetime(df_n["periodo"], format="%Y%m")

if not df_n.empty:
    fig_ndvi = go.Figure()
    fig_ndvi.add_hrect(y0=0,   y1=0.1,  fillcolor="#e74c3c", opacity=0.10, line_width=0,
                        annotation_text="Seco crítico", annotation_position="left")
    fig_ndvi.add_hrect(y0=0.1, y1=0.3,  fillcolor="#e67e22", opacity=0.07, line_width=0)
    fig_ndvi.add_hrect(y0=0.5, y1=1.0,  fillcolor="#27ae60", opacity=0.07, line_width=0,
                        annotation_text="Saudável", annotation_position="left")

    fig_ndvi.add_trace(go.Scatter(
        x=df_n["data"], y=df_n["ndvi_medio_regiao"],
        fill="tozeroy", fillcolor="rgba(39,174,96,0.2)",
        line=dict(color="#27ae60", width=2),
        name="NDVI médio",
    ))
    fig_ndvi.update_layout(
        height=270, yaxis=dict(title="NDVI (0=seco, 1=verde)", range=[0, 0.8]),
        margin=dict(l=0,r=0,t=0,b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_ndvi, use_container_width=True)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("NDVI médio", f"{df_n['ndvi_medio_regiao'].mean():.3f}")
    col_b.metric("Mínimo histórico", f"{df_n['ndvi_medio_regiao'].min():.3f}",
                 f"{df_n.loc[df_n['ndvi_medio_regiao'].idxmin(),'periodo']}")
    col_c.metric("Máximo histórico", f"{df_n['ndvi_medio_regiao'].max():.3f}",
                 f"{df_n.loc[df_n['ndvi_medio_regiao'].idxmax(),'periodo']}")
