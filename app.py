"""
AgroClima Brasil — Monitor de Risco Alimentar
Página principal: Alertas e status atual do ENSO
"""
import sys
sys.path.insert(0, ".")

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.dados import (
    carregar_alertas, carregar_oni, carregar_precipitacao,
    COORDS_ESTADOS, FASE_EMOJI,
)

st.set_page_config(
    page_title="AgroClima Brasil",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.markdown("""
<h1 style='color:#27ae60; margin-bottom:0'>🌾 AgroClima Brasil</h1>
<p style='color:#666; font-size:1.1rem; margin-top:4px'>
Monitor de risco alimentar baseado em dados climáticos e de satélite NASA
</p>
""", unsafe_allow_html=True)
st.divider()

# ── Carrega dados ─────────────────────────────────────────────────────────────
df_alertas = carregar_alertas()
df_oni     = carregar_oni()
df_precip  = carregar_precipitacao()

ultimo_oni = df_oni.sort_values("periodo").iloc[-1]
oni_val    = float(ultimo_oni["oni"])
fase       = str(ultimo_oni["fase_enso"])
emoji      = FASE_EMOJI.get(fase, "⚪")

alertas_alta = df_alertas[df_alertas["direcao_preco"] == "ALTA"].copy()

# ── Status ENSO ───────────────────────────────────────────────────────────────
st.subheader("Status Climático Atual")

col1, col2, col3, col4 = st.columns(4)

with col1:
    cor_oni = "#e74c3c" if oni_val >= 0.5 else "#3498db" if oni_val <= -0.5 else "#27ae60"
    st.markdown(f"""
    <div style='background:{cor_oni}15; border-left:4px solid {cor_oni};
                padding:16px; border-radius:8px; height:110px'>
        <div style='font-size:0.85rem; color:#666'>Índice ONI (ENSO)</div>
        <div style='font-size:2rem; font-weight:bold; color:{cor_oni}'>{oni_val:+.2f}°C</div>
        <div style='font-size:0.9rem'>{emoji} {fase.replace("_", " ").title()}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    n_alertas = len(alertas_alta)
    cor_alerta = "#e74c3c" if n_alertas > 0 else "#27ae60"
    st.markdown(f"""
    <div style='background:{cor_alerta}15; border-left:4px solid {cor_alerta};
                padding:16px; border-radius:8px; height:110px'>
        <div style='font-size:0.85rem; color:#666'>Alertas Ativos</div>
        <div style='font-size:2rem; font-weight:bold; color:{cor_alerta}'>{n_alertas}</div>
        <div style='font-size:0.9rem'>produtos em risco</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    precip_nord = df_precip[df_precip["regiao"] == "Nordeste"]["precipitacao_mm_total"].iloc[-12:].mean()
    st.markdown(f"""
    <div style='background:#3498db15; border-left:4px solid #3498db;
                padding:16px; border-radius:8px; height:110px'>
        <div style='font-size:0.85rem; color:#666'>Precipitação Nordeste</div>
        <div style='font-size:2rem; font-weight:bold; color:#3498db'>{precip_nord:.0f} mm</div>
        <div style='font-size:0.9rem'>média últimos 12 meses</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    periodo_ref = str(ultimo_oni["periodo"])
    ano, mes = periodo_ref[:4], periodo_ref[4:]
    st.markdown(f"""
    <div style='background:#95a5a615; border-left:4px solid #95a5a6;
                padding:16px; border-radius:8px; height:110px'>
        <div style='font-size:0.85rem; color:#666'>Última atualização</div>
        <div style='font-size:2rem; font-weight:bold; color:#95a5a6'>{mes}/{ano}</div>
        <div style='font-size:0.9rem'>Fonte: NOAA / BCB / NASA</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Alertas ───────────────────────────────────────────────────────────────────
col_alertas, col_mapa = st.columns([1, 1])

with col_alertas:
    st.subheader("📢 Alertas de Preço")

    if alertas_alta.empty:
        st.success("""
        ✅ **Nenhum alerta crítico no momento.**

        O ENSO está em fase neutra. Quando El Niño ou La Niña se
        desenvolverem, os alertas aparecerão aqui com antecedência
        de 2 a 6 meses.

        **Exemplo de alerta em El Niño forte:**
        > Risco alto de alta em carnes e peixes nos próximos 2-3 meses. Confiança: 67%.
        """)
    else:
        for _, row in alertas_alta.sort_values("pct_confianca", ascending=False).iterrows():
            nivel = row["confianca"]
            cor   = "#e74c3c" if nivel == "alta" else "#e67e22"
            icon  = "🔴" if nivel == "alta" else "🟠"
            st.markdown(f"""
            <div style='background:{cor}12; border:1px solid {cor}40;
                        padding:14px 16px; border-radius:8px; margin-bottom:10px'>
                <div style='font-weight:600; color:{cor}'>{icon} {row['mensagem_alerta']}</div>
                <div style='font-size:0.8rem; color:#888; margin-top:4px'>
                    Região: {row['regiao']} &nbsp;|&nbsp;
                    Produto: {row['produto'].replace('IPCA - ','')} &nbsp;|&nbsp;
                    Horizonte: {row['horizonte_meses']} meses
                </div>
            </div>
            """, unsafe_allow_html=True)

with col_mapa:
    st.subheader("🗺️ Mapa de Risco por Região")

    # Monta pontos para o mapa
    pontos = []
    for estado, (lat, lon, cidade) in COORDS_ESTADOS.items():
        regiao = "Nordeste" if estado not in ["RS","SC","PR"] else "Sul"

        # Determina risco com base nos alertas ativos para a região
        alertas_reg = df_alertas[df_alertas["regiao"] == regiao]
        tem_alta = (alertas_reg["direcao_preco"] == "ALTA").any()
        n_alta   = (alertas_reg["direcao_preco"] == "ALTA").sum()

        if tem_alta and regiao == "Nordeste" and n_alta >= 5:
            nivel, cor, size = "ALTO",     "#e74c3c", 18
        elif tem_alta:
            nivel, cor, size = "MODERADO", "#e67e22", 14
        else:
            nivel, cor, size = "NORMAL",   "#27ae60", 10

        pontos.append({
            "lat": lat, "lon": lon,
            "cidade": cidade, "estado": estado,
            "regiao": regiao, "nivel": nivel,
            "cor": cor, "size": size,
            "texto": f"{estado} — {nivel}",
        })

    df_map = pd.DataFrame(pontos)

    fig_map = go.Figure()
    fig_map.add_trace(go.Scattergeo(
        lat=df_map["lat"],
        lon=df_map["lon"],
        text=df_map["texto"],
        mode="markers+text",
        textposition="top center",
        textfont=dict(size=9),
        marker=dict(
            size=df_map["size"],
            color=df_map["cor"],
            opacity=0.85,
            line=dict(width=1, color="white"),
        ),
        hovertemplate="<b>%{text}</b><extra></extra>",
    ))
    fig_map.update_layout(
        geo=dict(
            scope="south america",
            center=dict(lat=-12, lon=-48),
            projection_scale=2.8,
            showland=True, landcolor="#f5f5dc",
            showocean=True, oceancolor="#d6eaf8",
            showcoastlines=True, coastlinecolor="#bdc3c7",
            showcountries=True, countrycolor="#bdc3c7",
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=350,
        paper_bgcolor="rgba(0,0,0,0)",
    )

    # Legenda manual
    for nivel, cor in [("ALTO","#e74c3c"),("MODERADO","#e67e22"),("NORMAL","#27ae60")]:
        fig_map.add_trace(go.Scattergeo(
            lat=[None], lon=[None], mode="markers",
            marker=dict(size=10, color=cor),
            name=nivel, showlegend=True,
        ))
    fig_map.update_layout(
        legend=dict(orientation="h", y=-0.05, x=0.1, font=dict(size=10))
    )

    st.plotly_chart(fig_map, use_container_width=True)

# ── ONI Recente (mini chart) ─────────────────────────────────────────────────
st.subheader("📈 Índice ENSO — Últimos 36 meses")
df_oni_rec = df_oni.sort_values("data").tail(36)

fig_oni = go.Figure()
fig_oni.add_hrect(y0=0.5, y1=3,   fillcolor="#e74c3c", opacity=0.08, line_width=0)
fig_oni.add_hrect(y0=-3,  y1=-0.5,fillcolor="#3498db", opacity=0.08, line_width=0)
fig_oni.add_hline(y=0, line_dash="dash", line_color="gray", line_width=0.8)
fig_oni.add_hline(y=0.5,  line_dash="dot", line_color="#e74c3c", line_width=0.6,
                  annotation_text="El Niño", annotation_position="right")
fig_oni.add_hline(y=-0.5, line_dash="dot", line_color="#3498db", line_width=0.6,
                  annotation_text="La Niña", annotation_position="right")
fig_oni.add_trace(go.Scatter(
    x=df_oni_rec["data"], y=df_oni_rec["oni"],
    fill="tozeroy",
    line=dict(color="#27ae60", width=2),
    fillcolor="rgba(39,174,96,0.15)",
    name="ONI",
))
fig_oni.update_layout(
    height=220, margin=dict(l=0,r=60,t=10,b=0),
    yaxis=dict(title="°C", range=[-2.5,2.5]),
    showlegend=False,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig_oni, use_container_width=True)

st.caption(
    "Fontes: NOAA (ENSO/ONI), BCB (IPCA), Open-Meteo (precipitação), "
    "NASA MODIS AppEEARS (NDVI) · Modelo com 67% de acurácia para El Niño forte"
)
