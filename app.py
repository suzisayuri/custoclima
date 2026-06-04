"""
CustoClima — Do clima ao supermercado
Painel executivo: semáforo de risco por produto para varejistas e restaurantes
"""
import sys
sys.path.insert(0, ".")

import streamlit as st
import plotly.graph_objects as go
from utils.dados import carregar_alertas, carregar_oni

st.set_page_config(
    page_title="CustoClima",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.markdown("""
<h1 style='color:#27ae60; margin-bottom:0'>🌾 CustoClima</h1>
<p style='color:#666; font-size:1.05rem; margin-top:4px'>
Do clima ao supermercado — planejamento de compras com antecedência
</p>
""", unsafe_allow_html=True)

# ── Seletor de perfil ─────────────────────────────────────────────────────────
segmento = st.radio(
    "**Meu perfil:**",
    ["🏪 Varejista", "🍽️ Restaurante"],
    horizontal=True,
    help="Adapta a linguagem das recomendações ao seu tipo de negócio.",
)
col_msg = "mensagem_varejista" if "Varejista" in segmento else "mensagem_restaurante"

st.divider()

# ── Carrega dados ─────────────────────────────────────────────────────────────
df_alertas = carregar_alertas()
df_oni     = carregar_oni()

if col_msg not in df_alertas.columns:
    col_msg = "mensagem_alerta"

ultimo_oni = df_oni.sort_values("periodo").iloc[-1]
fase_oni   = str(ultimo_oni["fase_enso"])

# ── Banner de status climático ────────────────────────────────────────────────
FASE_INFO = {
    "el_nino_forte": ("#e74c3c", "⚠️ El Niño forte",
                      "Alto risco de seca no Nordeste. Acompanhe os alertas de preço abaixo."),
    "el_nino_fraco": ("#e67e22", "⚠️ El Niño fraco",
                      "Tendência de seca no Nordeste. Fique atento a altas de preço nos próximos meses."),
    "la_nina_forte": ("#2980b9", "⚠️ La Niña forte",
                      "Alto risco de enchentes no Sul. Produtos da região podem encarecer."),
    "la_nina_fraca": ("#5dade2", "⚠️ La Niña fraca",
                      "Tendência de chuvas acima do normal no Sul. Monitore o impacto em preços."),
    "neutro":        ("#27ae60", "✅ Clima estável",
                      "Nenhuma anomalia climática significativa no momento. Planeje compras normalmente."),
}
cor_e, titulo_e, desc_e = FASE_INFO.get(
    fase_oni, ("#27ae60", "✅ Clima estável", "Nenhuma anomalia climática significativa.")
)

st.markdown(f"""
<div style='background:{cor_e}10; border:1px solid {cor_e}50;
            padding:14px 20px; border-radius:10px; margin-bottom:8px'>
    <span style='font-size:1.05rem; font-weight:700; color:{cor_e}'>{titulo_e}</span>
    <span style='font-size:0.92rem; color:#555; margin-left:12px'>{desc_e}</span>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Semáforo de produtos ───────────────────────────────────────────────────────
ICONE_PRODUTO = {
    "acucares e derivados":         "🍬",
    "aves e ovos":                  "🥚",
    "carnes e peixes":              "🥩",
    "cereais, leguminosas e oleag": "🌾",
    "frutas":                       "🍎",
    "horticultura":                 "🥦",
    "leite e derivados":            "🥛",
    "oleos e gorduras":             "🫙",
    "panificados":                  "🍞",
}

COR_NIVEL = {
    "ALTO":    ("#e74c3c", "🔴", "RISCO ALTO"),
    "MODERADO":("#e67e22", "🟠", "RISCO MODERADO"),
    "QUEDA":   ("#2980b9", "🔵", "TENDÊNCIA DE QUEDA"),
    "ESTAVEL": ("#27ae60", "🟢", "ESTÁVEL"),
}

ACAO_ESTAVEL = {
    "🏪 Varejista":   "Compra no ritmo normal. Sem necessidade de ação antecipada.",
    "🍽️ Restaurante": "Cardápio normal. Nenhuma substituição necessária por pressão de custo.",
}


def nivel_produto(grupo):
    altas = grupo[grupo["direcao_preco"] == "ALTA"]
    if not altas.empty:
        row = altas.sort_values("pct_confianca", ascending=False).iloc[0]
        return ("ALTO" if row["confianca"] == "alta" else "MODERADO"), row
    quedas = grupo[grupo["direcao_preco"] == "QUEDA"]
    if not quedas.empty:
        return "QUEDA", quedas.iloc[0]
    return "ESTAVEL", grupo.iloc[0]


# Exclui "Geral" — não é um produto acionável
df_prod = df_alertas[~df_alertas["produto"].str.contains("Geral", case=False)]

produtos_status = []
for produto, grupo in df_prod.groupby("produto"):
    nivel, row = nivel_produto(grupo)
    nome    = produto.replace("IPCA - ", "").lower()
    icone_p = ICONE_PRODUTO.get(nome, "🛒")
    mensagem = (
        ACAO_ESTAVEL[segmento]
        if nivel == "ESTAVEL"
        else (row[col_msg] if col_msg in row.index else row["mensagem_alerta"])
    )
    produtos_status.append((nivel, nome.title(), icone_p, mensagem,
                            int(row["horizonte_meses"]), row["regiao"]))

ordem = {"ALTO": 0, "MODERADO": 1, "QUEDA": 2, "ESTAVEL": 3}
produtos_status.sort(key=lambda x: ordem[x[0]])

n_ativos = sum(1 for p in produtos_status if p[0] in ("ALTO", "MODERADO"))

if n_ativos:
    st.subheader(f"⚠️ {n_ativos} produto{'s' if n_ativos > 1 else ''} em alerta")
else:
    st.subheader("✅ Todos os produtos estáveis agora")

cols = st.columns(3)
for i, (nivel, nome, icone_p, mensagem, horizonte, regiao) in enumerate(produtos_status):
    cor, icone_n, label = COR_NIVEL[nivel]
    rodape = (
        f"<div style='font-size:0.75rem; color:#aaa; margin-top:8px'>"
        f"Horizonte: {horizonte} meses &nbsp;·&nbsp; {regiao}</div>"
        if nivel != "ESTAVEL" else ""
    )
    with cols[i % 3]:
        st.markdown(f"""
        <div style='background:{cor}0d; border-left:5px solid {cor};
                    padding:14px 16px; border-radius:8px; margin-bottom:12px; min-height:140px'>
            <div style='font-size:1rem; font-weight:700; margin-bottom:6px'>
                {icone_p} {nome}
            </div>
            <div style='display:inline-block; background:{cor}20; color:{cor};
                        font-size:0.72rem; font-weight:700; padding:2px 9px;
                        border-radius:12px; margin-bottom:8px; letter-spacing:0.3px'>
                {icone_n} {label}
            </div>
            <div style='font-size:0.87rem; color:#444; line-height:1.45'>{mensagem}</div>
            {rodape}
        </div>
        """, unsafe_allow_html=True)

st.divider()

# ── Gráfico ONI colapsado ─────────────────────────────────────────────────────
with st.expander("📊 Como está o clima agora? (índice ENSO — últimos 36 meses)"):
    df_oni_rec = df_oni.sort_values("data").tail(36)
    fig_oni = go.Figure()
    fig_oni.add_hrect(y0=0.5,  y1=3,   fillcolor="#e74c3c", opacity=0.08, line_width=0)
    fig_oni.add_hrect(y0=-3,   y1=-0.5,fillcolor="#3498db", opacity=0.08, line_width=0)
    fig_oni.add_hline(y=0,    line_dash="dash", line_color="gray",    line_width=0.8)
    fig_oni.add_hline(y=0.5,  line_dash="dot",  line_color="#e74c3c", line_width=0.6,
                      annotation_text="El Niño", annotation_position="right")
    fig_oni.add_hline(y=-0.5, line_dash="dot",  line_color="#3498db", line_width=0.6,
                      annotation_text="La Niña", annotation_position="right")
    fig_oni.add_trace(go.Scatter(
        x=df_oni_rec["data"], y=df_oni_rec["oni"],
        fill="tozeroy",
        line=dict(color="#27ae60", width=2),
        fillcolor="rgba(39,174,96,0.15)",
        name="ONI",
    ))
    fig_oni.update_layout(
        height=200, margin=dict(l=0, r=80, t=10, b=0),
        yaxis=dict(title="", range=[-2.5, 2.5]),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_oni, use_container_width=True)
    st.caption(
        "Acima de +0.5 = El Niño (seca no Nordeste) · "
        "Abaixo de -0.5 = La Niña (enchentes no Sul) · "
        "Modelo calibrado com dados de 2015–2024."
    )

st.caption(
    "Dados: NOAA · BCB · Open-Meteo · NASA MODIS · "
    "67% de acurácia para El Niño forte · "
    "Use o menu lateral para análises detalhadas."
)
