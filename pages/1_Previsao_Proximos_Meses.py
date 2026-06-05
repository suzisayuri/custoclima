"""Página 1 — ENSO, Precipitação e NDVI"""
import sys
sys.path.insert(0, ".")

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
from utils.dados import (carregar_oni, carregar_precipitacao, carregar_ndvi,
                         carregar_corr_oni_precip, buscar_previsao_enso_noaa,
                         buscar_status_cptec)


st.title("📅 Previsão dos Próximos Meses")
st.markdown("O que o clima indica para os próximos meses — baseado em dados da NOAA, CPTEC e NASA.")
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

# ── Projeção climática ────────────────────────────────────────────────────────
st.subheader("📅 Projeção Climática — Próximos 6 Meses")

st.warning(
    "⚠️ Projeção baseada em padrões históricos (2015–2026) — não substitui previsão oficial. "
    "Acurácia: ~67% em El Niño forte · ~50% em fase neutra. "
    "Use como orientação de planejamento, não como certeza."
)

# ── Fontes oficiais ───────────────────────────────────────────────────────────
st.markdown("**🌐 Fontes oficiais consultadas agora:**")
noaa_d  = buscar_previsao_enso_noaa()
cptec_d = buscar_status_cptec()

col_noaa, col_cptec, col_inmet = st.columns(3)

with col_noaa:
    if noaa_d["ok"]:
        prob = f"<br><span style='font-size:0.78rem;color:#888'>{noaa_d['probabilidade']}</span>" if noaa_d.get("probabilidade") else ""
        st.markdown(f"""
        <a href='{noaa_d['fonte_url']}' target='_blank' style='text-decoration:none'>
        <div style='background:{noaa_d['cor']}10; border:1px solid {noaa_d['cor']}40;
                    border-radius:10px; padding:14px; height:130px'>
            <div style='font-size:0.75rem; color:#888; margin-bottom:4px'>🇺🇸 NOAA (EUA)</div>
            <div style='font-weight:700; color:{noaa_d['cor']}'>{noaa_d['icone']} {noaa_d['fase']}</div>
            <div style='font-size:0.82rem; color:#555; margin-top:4px; line-height:1.3'>{noaa_d['impacto']}{prob}</div>
        </div></a>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<div style='border:1px solid #eee;border-radius:10px;padding:14px;color:#aaa'>NOAA indisponível</div>", unsafe_allow_html=True)

with col_cptec:
    if cptec_d["ok"]:
        resumo_curto = cptec_d.get("resumo", "")[:130] + "…" if cptec_d.get("resumo") else ""
        st.markdown(f"""
        <a href='{cptec_d['url']}' target='_blank' style='text-decoration:none'>
        <div style='background:{cptec_d['cor']}10; border:1px solid {cptec_d['cor']}40;
                    border-radius:10px; padding:14px; height:130px; overflow:hidden'>
            <div style='font-size:0.75rem; color:#888; margin-bottom:4px'>🇧🇷 CPTEC/INPE (Brasil)</div>
            <div style='font-weight:700; color:{cptec_d['cor']}'>{cptec_d['icone']} {cptec_d['fase']}</div>
            <div style='font-size:0.78rem; color:#555; margin-top:4px; line-height:1.3'>{resumo_curto}</div>
        </div></a>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<div style='border:1px solid #eee;border-radius:10px;padding:14px;color:#aaa'>CPTEC indisponível</div>", unsafe_allow_html=True)

with col_inmet:
    st.markdown(f"""
    <a href='https://portal.inmet.gov.br/monitoramento' target='_blank' style='text-decoration:none'>
    <div style='background:#8e44ad10; border:1px solid #8e44ad40;
                border-radius:10px; padding:14px; height:130px'>
        <div style='font-size:0.75rem; color:#888; margin-bottom:4px'>🇧🇷 INMET (Brasil)</div>
        <div style='font-weight:700; color:#8e44ad'>🌡️ Monitoramento Climático</div>
        <div style='font-size:0.82rem; color:#555; margin-top:4px; line-height:1.3'>
            Temperaturas, chuvas e alertas meteorológicos por estado.<br>
            <span style='font-size:0.75rem;color:#aaa'>Clique para acessar →</span>
        </div>
    </div></a>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

ultimo_oni = df_oni.sort_values("periodo").iloc[-1]
oni_medido = float(ultimo_oni["oni"])

# ── Busca previsão oficial da NOAA ────────────────────────────────────────────
noaa = buscar_previsao_enso_noaa()

if noaa["ok"]:
    cor, icone = noaa["cor"], noaa["icone"]
    prob_txt = f" &nbsp;·&nbsp; {noaa['probabilidade']}" if noaa.get("probabilidade") else ""
    st.markdown(f"""
    <div style='background:{cor}10; border:1px solid {cor}50;
                padding:14px 18px; border-radius:10px; margin-bottom:12px'>
        <div style='font-size:1rem; font-weight:700; color:{cor}'>{icone} {noaa['fase']}</div>
        <div style='font-size:0.9rem; color:#444; margin-top:4px'>{noaa['impacto']}{prob_txt}</div>
        <div style='font-size:0.75rem; color:#aaa; margin-top:6px'>
            Fonte: <a href='{noaa['fonte_url']}' target='_blank'
            style='color:#aaa'>NOAA Climate Prediction Center</a>
            &nbsp;·&nbsp; atualizado automaticamente a cada 12h
        </div>
    </div>
    """, unsafe_allow_html=True)
    oni_atual = noaa["oni_sugerido"]
else:
    st.info("Não foi possível conectar à NOAA agora. Usando ONI medido.")
    oni_atual = oni_medido

# Confiança baseada na previsão em uso
if abs(oni_atual) >= 1.0:
    conf_label, conf_cor = "~67% — fase forte (maior confiança)", "#e67e22"
elif abs(oni_atual) >= 0.5:
    conf_label, conf_cor = "~55% — fase fraca (confiança moderada)", "#f39c12"
else:
    conf_label, conf_cor = "~50% — fase neutra (próximo ao acaso)", "#95a5a6"

st.markdown(
    f"<div style='font-size:0.82rem; color:{conf_cor}; margin-bottom:10px'>"
    f"🎯 <b>Confiança do modelo:</b> {conf_label}</div>",
    unsafe_allow_html=True,
)

df_corr_oni = carregar_corr_oni_precip()

hoje      = pd.Timestamp.today()
NOMES_MES = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

colunas_mes = []
proj = {"Nordeste": [], "Sul": []}

for lag in range(1, 7):
    mes_futuro = hoje + pd.DateOffset(months=lag)
    colunas_mes.append(f"{NOMES_MES[mes_futuro.month - 1]}/{str(mes_futuro.year)[2:]}")

    for regiao in ["Nordeste", "Sul"]:
        row = df_corr_oni[
            (df_corr_oni["regiao"] == regiao) &
            (df_corr_oni["lag_meses"] == lag)
        ]

        if row.empty or not bool(row.iloc[0]["significativo"]):
            proj[regiao].append(("🟢", "Normal", "#27ae60", "Sem sinal histórico neste prazo"))
            continue

        r     = float(row.iloc[0]["r_oni_precip"])
        sinal = r * oni_atual

        if regiao == "Nordeste":
            if sinal < -0.25:
                proj[regiao].append(("🔴", "Seca provável",  "#e74c3c", "Precipitação esperada bem abaixo da média histórica"))
            elif sinal < -0.10:
                proj[regiao].append(("🟡", "Atenção: seca",  "#f39c12", "Tendência de precipitação abaixo da média"))
            elif sinal > 0.10:
                proj[regiao].append(("🔵", "Chuvas acima",   "#3498db", "Tendência de precipitação acima da média"))
            else:
                proj[regiao].append(("🟢", "Normal",         "#27ae60", "Sem anomalia esperada"))
        else:  # Sul
            if sinal > 0.25:
                proj[regiao].append(("🔴", "Enchente provável", "#e74c3c", "Precipitação esperada muito acima da média histórica"))
            elif sinal > 0.10:
                proj[regiao].append(("🟡", "Atenção: chuvas",   "#f39c12", "Tendência de precipitação acima da média"))
            elif sinal < -0.10:
                proj[regiao].append(("🟡", "Atenção: seca",     "#f39c12", "Tendência de precipitação abaixo da média no Sul"))
            else:
                proj[regiao].append(("🟢", "Normal",            "#27ae60", "Sem anomalia esperada"))

# Cabeçalho de meses
cols_h = st.columns([1.4] + [1] * 6)
cols_h[0].markdown("")
for i, mes in enumerate(colunas_mes):
    cols_h[i + 1].markdown(
        f"<div style='text-align:center; font-size:0.82rem; font-weight:700; color:#555'>{mes}</div>",
        unsafe_allow_html=True,
    )

# Linhas por região
for regiao, emoji_reg in [("Nordeste", "🌵"), ("Sul", "🌧️")]:
    cols_r = st.columns([1.4] + [1] * 6)
    cols_r[0].markdown(
        f"<div style='font-size:0.88rem; font-weight:700; padding-top:14px'>{emoji_reg} {regiao}</div>",
        unsafe_allow_html=True,
    )
    for i, (icone, label, cor, detalhe) in enumerate(proj[regiao]):
        cols_r[i + 1].markdown(f"""
        <div title='{detalhe}'
             style='background:{cor}12; border:1px solid {cor}50; border-radius:8px;
                    padding:8px 4px; text-align:center; margin:2px 0'>
            <div style='font-size:1.3rem; line-height:1'>{icone}</div>
            <div style='font-size:0.68rem; color:{cor}; font-weight:700;
                        line-height:1.3; margin-top:3px'>{label}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown(
    "<div style='font-size:0.76rem; color:#aaa; margin-top:8px'>"
    "🟢 Normal &nbsp;·&nbsp; 🟡 Atenção &nbsp;·&nbsp; "
    "🔴 Risco alto &nbsp;·&nbsp; 🔵 Chuvas acima da média &nbsp;·&nbsp; "
    "Passe o mouse sobre cada célula para detalhes."
    "</div>",
    unsafe_allow_html=True,
)

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
st.subheader("🛰️ NDVI — Anomalia de Vegetação (NASA MODIS)")
st.caption(
    "Desvio percentual em relação à média histórica da região. "
    "Barras vermelhas = vegetação abaixo do normal (sinal de seca). "
    "Barras verdes = acima do normal (boa umidade)."
)

# Média histórica calculada sobre TODA a série da região (referência fixa)
media_hist_ndvi = df_ndvi[df_ndvi["regiao"] == regiao_sel]["ndvi_medio_regiao"].mean()

df_n = df_ndvi[
    (df_ndvi["regiao"] == regiao_sel) &
    (df_ndvi["ano"] >= ano_ini) &
    (df_ndvi["ano"] <= ano_fim)
].copy()
df_n["data"] = pd.to_datetime(df_n["periodo"], format="%Y%m")
df_n["anomalia_pct"] = (df_n["ndvi_medio_regiao"] - media_hist_ndvi) / media_hist_ndvi * 100

if not df_n.empty:
    cores = df_n["anomalia_pct"].apply(
        lambda v: "#e74c3c" if v < -10 else "#e67e22" if v < 0 else "#27ae60"
    )

    fig_ndvi = go.Figure()
    fig_ndvi.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1,
                       annotation_text=f"Média histórica (NDVI={media_hist_ndvi:.3f})",
                       annotation_position="right")
    fig_ndvi.add_hrect(y0=-100, y1=-10, fillcolor="#e74c3c", opacity=0.05, line_width=0)
    fig_ndvi.add_hrect(y0=10,   y1=100, fillcolor="#27ae60", opacity=0.05, line_width=0)

    fig_ndvi.add_trace(go.Bar(
        x=df_n["data"],
        y=df_n["anomalia_pct"],
        marker_color=cores,
        name="Anomalia NDVI (%)",
        hovertemplate="<b>%{x|%b/%Y}</b><br>Anomalia: %{y:.1f}%<extra></extra>",
    ))
    fig_ndvi.update_layout(
        height=290,
        yaxis=dict(title="Anomalia em relação à média histórica (%)", zeroline=False),
        margin=dict(l=0, r=120, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_ndvi, use_container_width=True)

    idx_min = df_n["anomalia_pct"].idxmin()
    idx_max = df_n["anomalia_pct"].idxmax()
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Média histórica (NDVI)", f"{media_hist_ndvi:.3f}")
    col_b.metric(
        "Pior seca (anomalia)",
        f"{df_n.loc[idx_min, 'anomalia_pct']:.1f}%",
        f"{df_n.loc[idx_min, 'periodo']}",
        delta_color="inverse",
    )
    col_c.metric(
        "Melhor umidade (anomalia)",
        f"{df_n.loc[idx_max, 'anomalia_pct']:.1f}%",
        f"{df_n.loc[idx_max, 'periodo']}",
    )
