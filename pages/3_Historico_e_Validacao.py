"""Página 3 — Histórico de preços e validação do modelo"""
import sys
sys.path.insert(0, ".")

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.dados import carregar_precos, carregar_backtesting, carregar_oni

st.set_page_config(page_title="Histórico · CustoClima", page_icon="🔍", layout="wide")

st.title("🔍 Histórico de Preços e Validação do Modelo")
st.markdown(
    "Histórico real de variação de preços por produto (BCB/IPCA) e "
    "resultado do backtesting — o modelo teria acertado no passado?"
)
st.divider()

df_preco = carregar_precos()
df_bt    = carregar_backtesting()
df_oni   = carregar_oni()

# ── Histórico de preços ───────────────────────────────────────────────────────
st.subheader("💰 Variação Mensal de Preço por Produto (2015–2024)")

produtos_disp = sorted(df_preco["produto"].dropna().unique())
prods_sel = st.multiselect(
    "Selecione produtos",
    [p.replace("IPCA - ", "") for p in produtos_disp],
    default=["Carnes e peixes", "Horticultura", "Panificados"],
)
prods_full = [p for p in produtos_disp if p.replace("IPCA - ", "") in prods_sel]

df_sel = df_preco[df_preco["produto"].isin(prods_full)].copy()
df_sel["produto_curto"] = df_sel["produto"].str.replace("IPCA - ", "")

if not df_sel.empty:
    fig_hist = px.line(
        df_sel, x="data", y="variacao_mensal_pct",
        color="produto_curto",
        labels={"variacao_mensal_pct": "Variação (%)", "data": "", "produto_curto": "Produto"},
    )
    fig_hist.add_hline(y=0, line_dash="dash", line_color="gray", line_width=0.8)
    fig_hist.update_layout(
        height=320, margin=dict(l=0,r=0,t=0,b=0),
        legend=dict(orientation="h", y=1.1),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_hist, use_container_width=True)

    # Métricas rápidas
    cols = st.columns(len(prods_full))
    for i, prod in enumerate(prods_full):
        sub = df_preco[df_preco["produto"] == prod]["variacao_mensal_pct"]
        cols[i].metric(
            prod.replace("IPCA - ", ""),
            f"{sub.mean():+.2f}%/mês",
            f"máx: {sub.max():+.1f}%",
        )

st.divider()

# ── Backtesting ───────────────────────────────────────────────────────────────
st.subheader("🎯 Backtesting — O Modelo Teria Acertado?")
st.markdown(
    "Simulação mês a mês: o modelo teria previsto corretamente a direção "
    "do preço (ALTA / QUEDA / ESTÁVEL) com base no ENSO de cada período?"
)

# Acurácia por fase ENSO
col_a, col_b = st.columns([1, 2])

with col_a:
    st.markdown("**Acurácia por fase ENSO**")
    resumo_fase = (
        df_bt.groupby("fase_enso")["acerto"]
        .agg(acertos="sum", total="count")
        .assign(acuracia=lambda x: (x["acertos"] / x["total"] * 100).round(1))
        .sort_values("acuracia", ascending=False)
        .reset_index()
    )
    resumo_fase["fase_enso"] = resumo_fase["fase_enso"].str.replace("_", " ").str.title()

    for _, row in resumo_fase.iterrows():
        cor = "#27ae60" if row["acuracia"] >= 60 else "#e67e22" if row["acuracia"] >= 50 else "#e74c3c"
        barra = int(row["acuracia"] / 5)
        st.markdown(f"""
        <div style='margin-bottom:8px'>
            <div style='font-size:0.85rem'>{row['fase_enso']}</div>
            <div style='background:#eee; border-radius:4px; height:20px; position:relative'>
                <div style='background:{cor}; width:{row['acuracia']}%;
                            height:100%; border-radius:4px; display:flex; align-items:center;
                            padding-left:6px; color:white; font-size:0.75rem; font-weight:600'>
                    {row['acuracia']:.0f}%
                </div>
            </div>
            <div style='font-size:0.75rem; color:#888'>{row['acertos']}/{row['total']} previsões</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style='background:#f0f4f0; padding:10px; border-radius:6px; margin-top:12px;
                font-size:0.82rem; color:#555'>
        📌 <b>El Niño forte = 67%</b> — sinal mais confiável<br>
        Referência: 50% = acaso puro
    </div>
    """, unsafe_allow_html=True)

with col_b:
    st.markdown("**Acurácia por produto**")
    resumo_prod = (
        df_bt.groupby(["produto", "regiao"])["acerto"]
        .agg(acertos="sum", total="count")
        .assign(acuracia=lambda x: (x["acertos"] / x["total"] * 100).round(1))
        .sort_values("acuracia", ascending=False)
        .reset_index()
    )
    resumo_prod["produto_curto"] = resumo_prod["produto"].str.replace("IPCA - ", "")
    resumo_prod["label"] = resumo_prod["produto_curto"] + " [" + resumo_prod["regiao"] + "]"

    fig_acc = go.Figure(go.Bar(
        x=resumo_prod["acuracia"],
        y=resumo_prod["label"],
        orientation="h",
        marker_color=resumo_prod["acuracia"].apply(
            lambda v: "#27ae60" if v >= 60 else "#e67e22" if v >= 50 else "#e74c3c"
        ),
        text=resumo_prod["acuracia"].apply(lambda v: f"{v:.0f}%"),
        textposition="outside",
    ))
    fig_acc.add_vline(x=50, line_dash="dash", line_color="gray",
                      annotation_text="50% (acaso)", annotation_position="top")
    fig_acc.update_layout(
        height=max(300, len(resumo_prod)*28),
        margin=dict(l=0,r=60,t=0,b=0),
        xaxis=dict(range=[0, 100], title="Acurácia (%)"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_acc, use_container_width=True)

st.divider()

# ── Eventos históricos ────────────────────────────────────────────────────────
st.subheader("📅 Eventos Climáticos Históricos no Dataset")

eventos = [
    ("2015-2016", "El Niño forte — pior seca do Nordeste em 50 anos",    "🔴", "201507", "201612"),
    ("2017-2018", "La Niña fraca — relativa normalidade",                 "🟢", "201701", "201812"),
    ("2020-2021", "La Niña moderada — chuvas acima da média no Sul",       "🔵", "202009", "202108"),
    ("2022",      "La Niña — terceiro ano consecutivo",                    "🔵", "202201", "202212"),
    ("2023-2024", "El Niño moderado + enchentes históricas RS (mai/2024)", "🟠", "202307", "202406"),
]

periodo_col = df_bt["periodo_previsao"].astype(str)
for periodo, descricao, emoji, ini, fim in eventos:
    sub = df_bt[
        (periodo_col >= ini) &
        (periodo_col <= fim)
    ]
    acc = sub["acerto"].mean() * 100 if len(sub) > 0 else 0
    cor_acc = "#27ae60" if acc >= 60 else "#e67e22" if acc >= 50 else "#e74c3c"

    st.markdown(f"""
    <div style='display:flex; align-items:center; padding:10px 14px;
                border:1px solid #ddd; border-radius:8px; margin-bottom:8px;
                background:#fafafa'>
        <div style='font-size:1.4rem; margin-right:12px'>{emoji}</div>
        <div style='flex:1'>
            <b>{periodo}</b> — {descricao}
        </div>
        <div style='text-align:right; min-width:90px'>
            <span style='font-size:1.1rem; font-weight:bold; color:{cor_acc}'>{acc:.0f}%</span>
            <br><span style='font-size:0.75rem; color:#888'>acurácia modelo</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.caption(
    "Modelo principal: Nordeste (El Niño forte → 67%). "
    "Sul classificado como 'módulo experimental' — requer previsão diária de precipitação para melhorar."
)
