"""Página 2 — Correlações clima × preço"""
import sys
sys.path.insert(0, ".")

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from utils.dados import carregar_correlacoes, carregar_correlacoes_ndvi, carregar_precos, carregar_precipitacao, carregar_ndvi

st.set_page_config(page_title="Correlações · AgroClima", page_icon="📊", layout="wide")

st.title("📊 Correlações Clima × Preço")
st.markdown(
    "Mostra como eventos climáticos impactam o preço dos alimentos, "
    "com qual defasagem (lag) e qual alimento é mais sensível."
)
st.divider()

df_corr      = carregar_correlacoes()
df_corr_ndvi = carregar_correlacoes_ndvi()
df_preco     = carregar_precos()
df_precip    = carregar_precipitacao()
df_ndvi      = carregar_ndvi()

# ── Filtros ───────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    regiao_sel = st.selectbox("Região", ["Nordeste", "Sul", "Ambas"])
with col2:
    apenas_sig = st.toggle("Somente significativos (p < 0.05)", value=True)
with col3:
    sinal_sel = st.radio("Sinal climático", ["Precipitação", "NDVI (NASA)", "Ambos"],
                         horizontal=True)

# ── Heatmap produto × lag ─────────────────────────────────────────────────────
st.subheader("🔥 Heatmap — Produto × Defasagem (meses)")

def preparar_heatmap(df, col_r, regiao):
    sub = df.copy()
    if apenas_sig:
        sub = sub[sub["significativo"].astype(bool)]
    if regiao != "Ambas":
        sub = sub[sub["regiao"] == regiao]
    if sub.empty:
        return None
    pivot = sub.pivot_table(index="produto", columns="lag_meses" if "lag_meses" in sub.columns else "defasagem_meses",
                            values=col_r, aggfunc="mean")
    pivot.columns = [f"lag{c}" for c in pivot.columns]
    pivot.index   = pivot.index.str.replace("IPCA - ", "")
    return pivot

if sinal_sel in ["Precipitação", "Ambos"]:
    pivot = preparar_heatmap(df_corr, "r_pearson", regiao_sel)
    if pivot is not None:
        st.markdown("**Precipitação → Preço**")
        fig_h = px.imshow(
            pivot, text_auto=".2f", aspect="auto",
            color_continuous_scale="RdBu_r",
            color_continuous_midpoint=0, zmin=-0.5, zmax=0.5,
            labels={"color": "r de Pearson"},
        )
        fig_h.update_layout(
            height=max(280, len(pivot)*36),
            margin=dict(l=0,r=0,t=0,b=0),
            coloraxis_colorbar=dict(title="r", len=0.6),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_h, use_container_width=True)
        st.caption("Azul = mais chuva → preço cai (seca encarece) · Vermelho = mais chuva → preço sobe")

if sinal_sel in ["NDVI (NASA)", "Ambos"]:
    pivot_n = preparar_heatmap(df_corr_ndvi, "r_ndvi_preco", regiao_sel)
    if pivot_n is not None:
        st.markdown("**NDVI Satelital (NASA) → Preço**")
        fig_n = px.imshow(
            pivot_n, text_auto=".2f", aspect="auto",
            color_continuous_scale="RdBu_r",
            color_continuous_midpoint=0, zmin=-0.5, zmax=0.5,
            labels={"color": "r de Pearson"},
        )
        fig_n.update_layout(
            height=max(280, len(pivot_n)*36),
            margin=dict(l=0,r=0,t=0,b=0),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_n, use_container_width=True)
        st.caption("NDVI cai (seca) = r negativo = preço sobe · Sinal independente da precipitação")

st.divider()

# ── Série temporal interativa ─────────────────────────────────────────────────
st.subheader("📈 Série Temporal — Clima × Preço")
st.markdown("Compare visualmente a queda no NDVI ou na precipitação com a alta de preço meses depois.")

col_p, col_r, col_l = st.columns(3)
with col_p:
    produtos_disp = sorted(df_preco["produto"].dropna().unique())
    prod_sel = st.selectbox("Produto", [p.replace("IPCA - ","") for p in produtos_disp])
    prod_full = next((p for p in produtos_disp if prod_sel in p), produtos_disp[0])
with col_r:
    reg_ser = st.selectbox("Região (clima)", ["Nordeste", "Sul"])
with col_l:
    sinal_ser = st.radio("Sinal climático", ["Precipitação", "NDVI"], horizontal=True)

df_prod = df_preco[df_preco["produto"] == prod_full].sort_values("data")

if sinal_ser == "Precipitação":
    df_clima_ser = (
        df_precip[df_precip["regiao"] == reg_ser]
        .groupby("periodo")["precipitacao_mm_total"].mean().reset_index()
    )
    df_clima_ser["data"] = pd.to_datetime(df_clima_ser["periodo"], format="%Y%m")
    y_clima = "precipitacao_mm_total"
    nome_y2 = "Precipitação (mm/mês)"
    cor2    = "#3498db"
else:
    df_clima_ser = df_ndvi[df_ndvi["regiao"] == reg_ser].copy()
    df_clima_ser["data"] = pd.to_datetime(df_clima_ser["periodo"], format="%Y%m")
    y_clima = "ndvi_medio_regiao"
    nome_y2 = "NDVI (0=seco, 1=verde)"
    cor2    = "#27ae60"

merged = df_prod.merge(df_clima_ser[["data", y_clima]], on="data", how="inner")

if not merged.empty:
    fig_ser = go.Figure()
    fig_ser.add_trace(go.Bar(
        x=merged["data"], y=merged["variacao_mensal_pct"],
        name="Variação preço (%)",
        marker_color="#e74c3c", opacity=0.6,
        yaxis="y",
    ))
    fig_ser.add_trace(go.Scatter(
        x=merged["data"], y=merged[y_clima],
        name=nome_y2,
        line=dict(color=cor2, width=2),
        yaxis="y2",
    ))
    fig_ser.update_layout(
        height=300,
        yaxis=dict(title="Variação preço (%)", color="#e74c3c"),
        yaxis2=dict(title=nome_y2, overlaying="y", side="right", color=cor2),
        legend=dict(orientation="h", y=1.1),
        margin=dict(l=0,r=0,t=10,b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_ser, use_container_width=True)

st.divider()

# ── Tabela de resultados ──────────────────────────────────────────────────────
st.subheader("📋 Tabela de Correlações Significativas")

df_tab = df_corr[df_corr["significativo"].astype(bool)].copy()
df_tab["produto"] = df_tab["produto"].str.replace("IPCA - ", "")
col_lag = "defasagem_meses" if "defasagem_meses" in df_tab.columns else "lag_meses"
df_tab["interpretacao"] = df_tab["r_pearson"].apply(
    lambda r: "Seca encarece" if r < -0.15 else "Chuva encarece" if r > 0.15 else "Relação fraca"
)

if regiao_sel != "Ambas":
    df_tab = df_tab[df_tab["regiao"] == regiao_sel]

st.dataframe(
    df_tab[["produto", "regiao", col_lag, "r_pearson", "p_valor", "interpretacao"]]
    .rename(columns={
        "produto": "Produto", "regiao": "Região",
        col_lag: "Lag (meses)", "r_pearson": "r de Pearson",
        "p_valor": "p-valor", "interpretacao": "Interpretação",
    })
    .sort_values("r de Pearson", key=abs, ascending=False)
    .reset_index(drop=True),
    use_container_width=True,
    height=350,
)
