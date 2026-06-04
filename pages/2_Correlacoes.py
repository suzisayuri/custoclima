"""Página 2 — Correlações clima × preço"""
import sys
sys.path.insert(0, ".")

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from utils.dados import carregar_correlacoes, carregar_correlacoes_ndvi, carregar_precos, carregar_precipitacao, carregar_ndvi

st.set_page_config(page_title="Correlações · CustoClima", page_icon="📊", layout="wide")

st.title("📊 Correlações Clima × Preço")
st.markdown(
    "Mostra **quais alimentos** sobem de preço após eventos climáticos, "
    "**com quantos meses de antecedência** o sinal aparece, "
    "e **quão confiável** é essa relação historicamente."
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

with st.expander("❓ Qual a diferença entre Precipitação e NDVI?"):
    st.markdown("""
    **🌧️ Precipitação** — mede quanto choveu naquele mês (em mm).
    Detecta seca ou excesso de chuva rapidamente, a partir de estações meteorológicas.
    É o sinal mais direto: choveu menos → lavoura em risco.

    **🛰️ NDVI (NASA)** — mede a saúde da vegetação por satélite.
    Não mede chuva — mede se a planta está de fato verde e saudável.
    Uma lavoura pode estar sofrendo mesmo com alguma chuva (solo raso, calor extremo),
    e o NDVI capta isso onde a precipitação não vê.

    **Qual usar?**
    - Use **Precipitação** para detectar seca ou enchente logo que acontece.
    - Use **NDVI** para confirmar que a safra foi realmente prejudicada.
    - Quando os dois sinais concordam → confiança maior no alerta.

    > Na análise histórica deste projeto, a precipitação vence como preditor de preço
    > em 18 dos 20 produtos. O NDVI ganha em horticultura, onde a saúde da planta
    > é mais determinante do que a quantidade de chuva em si.
    """)

# ── Heatmap produto × lag ─────────────────────────────────────────────────────
st.subheader("🔥 Heatmap — Produto × Defasagem (meses)")

with st.expander("❓ Como ler este heatmap"):
    st.markdown("""
    **Cada linha é um alimento. Cada coluna é "daqui a quantos meses o preço reage".**

    **As cores:**
    - 🔴 **Vermelho** — seca encarece esse alimento. Quanto mais escuro, mais forte o sinal.
    - 🔵 **Azul** — excesso de chuva encarece esse alimento (ex.: enchentes no Sul).
    - ⬜ **Branco** — o clima não ajuda a prever este alimento neste prazo.

    **Os números (-0,35 / -0,28...):**
    Indicam a força do sinal. Ignore o sinal de menos — o que importa é o tamanho:
    - Acima de **0,30** → sinal forte, confiável para planejar
    - Entre **0,15 e 0,30** → sinal moderado, use com cautela
    - Abaixo de **0,15** → sinal fraco, pode ser coincidência

    **Exemplo prático:**
    Célula *Panificados × 2 meses* vermelha e escura = uma seca no Nordeste hoje tende a encarecer farinha e pão **daqui a 2 meses**.
    ✅ Ação: antecipar contrato com o fornecedor ou reforçar estoque de farinha.

    ---
    **❓ Por que o sinal de 2-3 meses é mais forte do que o de 1 mês?**

    No Brasil, os preços sobem rápido — mas de forma **desigual**. No primeiro mês após uma seca,
    alguns fornecedores já repassam o aumento, outros ainda não. Essa variação desigual gera ruído
    na estatística e enfraquece o sinal.

    Em 2-3 meses, o mercado inteiro já se ajustou: o aumento está disseminado, consistente e
    previsível — e é aí que a correlação histórica fica mais forte.

    **Para varejistas e restaurantes:** isso significa que o momento certo de agir é
    **assim que o sinal climático aparece** — não espere o preço subir para reagir.
    Use esses 2-3 meses para fechar contratos de preço fixo, antecipar pedidos ou
    substituir itens no cardápio antes que o fornecedor reajuste a tabela.
    """)

def preparar_heatmap(df, col_r, regiao):
    sub = df.copy()
    if apenas_sig:
        sub = sub[sub["significativo"].astype(bool)]
    if regiao != "Ambas":
        sub = sub[sub["regiao"] == regiao]
    col_lag = "lag_meses" if "lag_meses" in sub.columns else "defasagem_meses"
    sub = sub[sub[col_lag] > 0]  # remove lag0 — sem valor para planejamento
    if sub.empty:
        return None
    pivot = sub.pivot_table(index="produto", columns=col_lag, values=col_r, aggfunc="mean")
    pivot.columns = [f"{c} mês" if c == 1 else f"{c} meses" for c in pivot.columns]
    pivot.index   = pivot.index.str.replace("IPCA - ", "")
    return pivot

if sinal_sel in ["Precipitação", "Ambos"]:
    pivot = preparar_heatmap(df_corr, "r_pearson", regiao_sel)
    if pivot is not None:
        st.markdown("**Precipitação → Preço**")
        fig_h = px.imshow(
            pivot, text_auto=".2f", aspect="auto",
            color_continuous_scale="RdBu",
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
        st.caption("🔴 Vermelho = seca encarece · 🔵 Azul = excesso de chuva encarece · ⬜ Branco = sem relação clara")

if sinal_sel in ["NDVI (NASA)", "Ambos"]:
    pivot_n = preparar_heatmap(df_corr_ndvi, "r_ndvi_preco", regiao_sel)
    if pivot_n is not None:
        st.markdown("**NDVI Satelital (NASA) → Preço**")
        fig_n = px.imshow(
            pivot_n, text_auto=".2f", aspect="auto",
            color_continuous_scale="RdBu",
            color_continuous_midpoint=0, zmin=-0.5, zmax=0.5,
            labels={"color": "r de Pearson"},
        )
        fig_n.update_layout(
            height=max(280, len(pivot_n)*36),
            margin=dict(l=0,r=0,t=0,b=0),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_n, use_container_width=True)
        st.caption("🔴 Vermelho = vegetação abaixo do normal encarece · 🔵 Azul = vegetação excessiva encarece · Sinal independente da precipitação")

st.divider()

# ── Série temporal interativa ─────────────────────────────────────────────────
st.subheader("📈 Série Temporal — Clima × Preço")

with st.expander("❓ Como ler este gráfico"):
    st.markdown("""
    **🟥 Barras vermelhas** — variação mensal do preço do produto escolhido.
    Barra para cima = preço subiu naquele mês. Para baixo = preço caiu.

    **Linha colorida** — o sinal climático da região:
    - 🔵 Azul (Precipitação): quantidade de chuva. Linha caindo = menos chuva = seca.
    - 🟢 Verde (NDVI): saúde da vegetação. Linha caindo = lavoura sofrendo.

    **O que procurar:**
    Observe se a linha climática cai e, **2 a 3 meses depois**, as barras de preço sobem.
    Esse é o padrão que o modelo detecta. Se você ver isso acontecendo agora,
    é o momento de agir antes que o preço chegue ao seu fornecedor.
    """)

col_p, col_r, col_l = st.columns(3)
with col_p:
    produtos_disp = sorted(df_preco["produto"].dropna().unique())
    prod_sel = st.selectbox("Produto", [p.replace("IPCA - ","") for p in produtos_disp])
    prod_full = next((p for p in produtos_disp if prod_sel in p), produtos_disp[0])
with col_r:
    reg_ser = st.selectbox("Região (clima)", ["Nordeste", "Sul"])
with col_l:
    sinal_ser = st.radio("Sinal climático", ["Precipitação", "NDVI"], horizontal=True)

anos_disp = sorted(df_preco["data"].dt.year.unique())
col_ini, col_fim = st.columns(2)
with col_ini:
    ano_ini_ser = st.selectbox("De", anos_disp, index=0, key="ser_ini")
with col_fim:
    ano_fim_ser = st.selectbox("Até", anos_disp, index=len(anos_disp)-1, key="ser_fim")

df_prod = df_preco[
    (df_preco["produto"] == prod_full) &
    (df_preco["data"].dt.year >= ano_ini_ser) &
    (df_preco["data"].dt.year <= ano_fim_ser)
].sort_values("data")

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

with st.expander("❓ Como ler esta tabela"):
    st.markdown("""
    | Coluna | O que significa | Como usar |
    |---|---|---|
    | **Alimento** | Categoria do produto no IPCA | O produto que vai sofrer impacto no preço |
    | **Região** | De onde vem o sinal climático | Nordeste = El Niño/seca · Sul = La Niña/enchente |
    | **Aviso com antecedência** | Quantos meses antes o clima já "avisa" | Ex.: 3 meses → você tem 3 meses para agir |
    | **Força do sinal** | Quão forte é a relação histórica | ⭐⭐⭐ Forte = confie mais · ⭐ Fraco = use com cautela |
    | **Confiabilidade** | Se a relação é estatisticamente real | Alta = certamente não é coincidência |
    | **O que esperar** | Tradução prática do sinal | Seca encarece ou chuva encarece |

    **Regra prática:** foque nas linhas com "Força do sinal ⭐⭐⭐" e "Aviso com antecedência ≥ 2 meses".
    São estas que permitem ação concreta antes da alta chegar ao mercado.
    """)

df_tab = df_corr[df_corr["significativo"].astype(bool)].copy()
df_tab["produto"] = df_tab["produto"].str.replace("IPCA - ", "")
col_lag = "defasagem_meses" if "defasagem_meses" in df_tab.columns else "lag_meses"

df_tab["o_que_esperar"] = df_tab["r_pearson"].apply(
    lambda r: "🔴 Seca encarece" if r < -0.15 else "🌧️ Chuva excessiva encarece" if r > 0.15 else "Relação fraca"
)
df_tab["forca_sinal"] = df_tab["r_pearson"].apply(
    lambda r: "⭐⭐⭐ Forte"   if abs(r) >= 0.35 else
              "⭐⭐ Moderado"  if abs(r) >= 0.25 else
              "⭐ Fraco"
)
df_tab["confiabilidade"] = df_tab["p_valor"].apply(
    lambda p: "🟢 Alta"   if p < 0.001 else
              "🟡 Média"  if p < 0.05  else
              "🔴 Baixa"
)

if regiao_sel != "Ambas":
    df_tab = df_tab[df_tab["regiao"] == regiao_sel]

st.dataframe(
    df_tab[["produto", "regiao", col_lag, "forca_sinal", "confiabilidade", "o_que_esperar"]]
    .rename(columns={
        "produto":        "Alimento",
        "regiao":         "Região",
        col_lag:          "Aviso com antecedência (meses)",
        "forca_sinal":    "Força do sinal",
        "confiabilidade": "Confiabilidade",
        "o_que_esperar":  "O que esperar",
    })
    .sort_values("Força do sinal", ascending=True)
    .reset_index(drop=True),
    use_container_width=True,
    height=380,
)
