"""
CustoClima — Do clima ao supermercado
Painel executivo: semáforo de risco por produto para varejistas e restaurantes
"""
import sys
sys.path.insert(0, ".")

import streamlit as st
import plotly.graph_objects as go
from utils.dados import (
    carregar_alertas, carregar_oni,
    buscar_previsao_enso_noaa, buscar_status_cptec,
)

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

segmento = st.radio(
    "**Meu perfil:**",
    ["🏪 Varejista", "🍽️ Restaurante"],
    horizontal=True,
    help="Adapta a linguagem das recomendações ao seu tipo de negócio.",
)

st.divider()

# ── Dados ─────────────────────────────────────────────────────────────────────
df_alertas = carregar_alertas()
df_oni     = carregar_oni()
noaa       = buscar_previsao_enso_noaa()
cptec      = buscar_status_cptec()

# ONI que vai guiar o semáforo: previsão NOAA quando disponível, medido como fallback
oni_base = df_oni.sort_values("periodo").iloc[-1]
oni_medido = float(oni_base["oni"])
oni_para_calculo = noaa["oni_sugerido"] if noaa["ok"] else oni_medido

# ── Banner de status + fontes oficiais ────────────────────────────────────────
if noaa["ok"]:
    cor_b, titulo_b = noaa["cor"], f"{noaa['icone']} {noaa['fase']}"
    desc_b = noaa["impacto"]
    prob_b = f" &nbsp;·&nbsp; {noaa['probabilidade']}" if noaa.get("probabilidade") else ""
else:
    FASE_MAP = {
        "el_nino_forte": ("#e74c3c", "⚠️ El Niño forte", "Alto risco de seca no Nordeste."),
        "el_nino_fraco": ("#e67e22", "⚠️ El Niño fraco", "Tendência de seca no Nordeste."),
        "la_nina_forte": ("#2980b9", "⚠️ La Niña forte", "Alto risco de enchentes no Sul."),
        "la_nina_fraca": ("#5dade2", "⚠️ La Niña fraca", "Tendência de chuvas no Sul."),
        "neutro":        ("#27ae60", "✅ Clima estável", "Sem anomalia climática significativa."),
    }
    cor_b, titulo_b, desc_b = FASE_MAP.get(
        str(oni_base["fase_enso"]),
        ("#27ae60", "✅ Clima estável", "Sem anomalia climática significativa.")
    )
    prob_b = ""

st.markdown(f"""
<div style='background:{cor_b}10; border:1px solid {cor_b}50;
            padding:14px 20px; border-radius:10px; margin-bottom:12px'>
    <span style='font-size:1.05rem; font-weight:700; color:{cor_b}'>{titulo_b}</span>
    <span style='font-size:0.92rem; color:#555; margin-left:12px'>{desc_b}{prob_b}</span>
</div>
""", unsafe_allow_html=True)

# Cards NOAA + CPTEC + INMET
col_noaa, col_cptec, col_inmet = st.columns(3)

with col_noaa:
    if noaa["ok"]:
        prob_card = f"<br><span style='font-size:0.76rem;color:#888'>{noaa['probabilidade']}</span>" if noaa.get("probabilidade") else ""
        st.markdown(f"""
        <a href='{noaa['fonte_url']}' target='_blank' style='text-decoration:none'>
        <div style='background:{noaa['cor']}0d; border:1px solid {noaa['cor']}40;
                    border-radius:10px; padding:12px; height:110px'>
            <div style='font-size:0.72rem; color:#999; margin-bottom:3px'>🇺🇸 NOAA (EUA)</div>
            <div style='font-weight:700; color:{noaa['cor']}'>{noaa['icone']} {noaa['fase']}</div>
            <div style='font-size:0.8rem; color:#555; margin-top:3px; line-height:1.3'>
                {noaa['impacto']}{prob_card}
            </div>
        </div></a>""", unsafe_allow_html=True)

with col_cptec:
    if cptec["ok"]:
        st.markdown(f"""
        <a href='{cptec['url']}' target='_blank' style='text-decoration:none'>
        <div style='background:{cptec['cor']}0d; border:1px solid {cptec['cor']}40;
                    border-radius:10px; padding:12px; height:110px; overflow:hidden'>
            <div style='font-size:0.72rem; color:#999; margin-bottom:3px'>🇧🇷 CPTEC/INPE</div>
            <div style='font-weight:700; color:{cptec['cor']}'>{cptec['icone']} {cptec['fase']}</div>
            <div style='font-size:0.78rem; color:#555; margin-top:3px; line-height:1.3'>
                {(cptec.get('resumo','')[:110] + '…') if cptec.get('resumo') else ''}
            </div>
        </div></a>""", unsafe_allow_html=True)

with col_inmet:
    st.markdown("""
    <a href='https://portal.inmet.gov.br/monitoramento' target='_blank' style='text-decoration:none'>
    <div style='background:#8e44ad0d; border:1px solid #8e44ad40;
                border-radius:10px; padding:12px; height:110px'>
        <div style='font-size:0.72rem; color:#999; margin-bottom:3px'>🇧🇷 INMET</div>
        <div style='font-weight:700; color:#8e44ad'>🌡️ Monitoramento Climático</div>
        <div style='font-size:0.8rem; color:#555; margin-top:3px; line-height:1.3'>
            Temperaturas, alertas e chuvas por estado.<br>
            <span style='font-size:0.73rem;color:#bbb'>Clique para acessar →</span>
        </div>
    </div></a>""", unsafe_allow_html=True)

st.markdown("<div style='font-size:0.72rem; color:#bbb; margin-top:4px; margin-bottom:16px'>"
            "Fontes atualizadas automaticamente a cada 12h</div>", unsafe_allow_html=True)

# ── Semáforo — calculado com o ONI previsto da NOAA ───────────────────────────
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


def recalcular_direcao(df, oni_previsto):
    """Recalcula direcao_preco e confianca baseado no ONI previsto (NOAA)."""
    df = df.copy()
    for idx, row in df.iterrows():
        r = float(row["r_precip_preco"])
        regiao = row["regiao"]
        if oni_previsto >= 0.5 and regiao == "Nordeste" and r < 0:
            df.at[idx, "direcao_preco"] = "ALTA"
            df.at[idx, "confianca"] = "alta" if abs(oni_previsto) >= 1.0 else "media"
        elif oni_previsto <= -0.5 and regiao == "Sul" and r > 0:
            df.at[idx, "direcao_preco"] = "ALTA"
            df.at[idx, "confianca"] = "alta" if abs(oni_previsto) >= 1.0 else "media"
        else:
            df.at[idx, "direcao_preco"] = "ESTAVEL"
    return df


def mensagem_dinamica(nome, direcao, segmento, horizonte):
    if direcao == "ESTAVEL":
        return ACAO_ESTAVEL[segmento]
    h = f"{horizonte - 1}-{horizonte} meses"
    if "Varejista" in segmento:
        return (f"Risco de alta em {nome.lower()} nos próximos {h}. "
                f"Considere antecipar contratos com fornecedores.")
    return (f"Risco de alta em {nome.lower()} nos próximos {h}. "
            f"Avalie substituições no cardápio ou compra antecipada.")


def nivel_produto(grupo):
    altas = grupo[grupo["direcao_preco"] == "ALTA"]
    if not altas.empty:
        row = altas.sort_values("pct_confianca", ascending=False).iloc[0]
        return ("ALTO" if row["confianca"] == "alta" else "MODERADO"), row
    quedas = grupo[grupo["direcao_preco"] == "QUEDA"]
    if not quedas.empty:
        return "QUEDA", quedas.iloc[0]
    return "ESTAVEL", grupo.iloc[0]


df_calc = recalcular_direcao(
    df_alertas[~df_alertas["produto"].str.contains("Geral", case=False)],
    oni_para_calculo,
)

produtos_status = []
for produto, grupo in df_calc.groupby("produto"):
    nivel, row = nivel_produto(grupo)
    nome    = produto.replace("IPCA - ", "").lower()
    icone_p = ICONE_PRODUTO.get(nome, "🛒")
    mensagem = mensagem_dinamica(nome, nivel, segmento, int(row["horizonte_meses"]))
    produtos_status.append((nivel, nome.title(), icone_p, mensagem,
                            int(row["horizonte_meses"]), row["regiao"]))

ordem = {"ALTO": 0, "MODERADO": 1, "QUEDA": 2, "ESTAVEL": 3}
produtos_status.sort(key=lambda x: ordem[x[0]])
n_ativos = sum(1 for p in produtos_status if p[0] in ("ALTO", "MODERADO"))

fonte_label = "previsão NOAA" if noaa["ok"] else "ONI medido"
if n_ativos:
    st.subheader(f"⚠️ {n_ativos} produto{'s' if n_ativos > 1 else ''} em alerta")
else:
    st.subheader("✅ Todos os produtos estáveis agora")
st.caption(f"Baseado na {fonte_label} · Altere o perfil acima para ver recomendações por segmento")

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
            <div style='font-size:1rem; font-weight:700; margin-bottom:6px'>{icone_p} {nome}</div>
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
        "Modelo calibrado com dados de 2015–2026."
    )

st.caption(
    "Dados: NOAA · CPTEC/INPE · BCB · Open-Meteo · NASA MODIS · "
    "67% de acurácia para El Niño forte · "
    "Use o menu lateral para análises detalhadas."
)
