"""Página 5 — Guia completo do CustoClima"""
import sys
sys.path.insert(0, ".")
import streamlit as st

st.set_page_config(page_title="Entendendo o Site · CustoClima", page_icon="📖", layout="wide")

st.title("📖 Entendendo o Site")
st.markdown("Tudo que você precisa saber para usar o CustoClima com confiança.")
st.divider()

# ── O que é o CustoClima ──────────────────────────────────────────────────────
st.subheader("🌾 O que é o CustoClima?")
st.markdown("""
O **CustoClima** é uma ferramenta de apoio à decisão de compras para **varejistas e restaurantes**.

Ele monitora sinais climáticos — como secas no Nordeste e enchentes no Sul — e traduz esses
sinais em alertas práticos: *quais alimentos tendem a encarecer, em quanto tempo e o que fazer.*

A ideia é simples: o clima afeta a safra, a safra afeta a oferta, a oferta afeta o preço.
Fenômenos como El Niño são previsíveis com meses de antecedência — e essa janela é a
oportunidade para agir antes que o preço chegue ao seu fornecedor.

> ⚠️ O modelo tem **~67% de acurácia em El Niño forte**. Em fases neutras, fica próximo ao acaso.
> Use como orientação estratégica, não como certeza.
""")

st.divider()

# ── Como usar ─────────────────────────────────────────────────────────────────
st.subheader("🧭 Como usar o site — passo a passo")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("""
    <div style='background:#27ae6010; border:1px solid #27ae6040; border-radius:10px; padding:16px; height:180px'>
        <div style='font-size:1.5rem'>1️⃣</div>
        <div style='font-weight:700; margin:8px 0'>Alertas de Compra</div>
        <div style='font-size:0.85rem; color:#555'>
            Comece aqui. Selecione seu perfil (varejista ou restaurante) e veja o semáforo de produtos.
            Vermelho = ação urgente. Verde = compra normal.
        </div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown("""
    <div style='background:#3498db10; border:1px solid #3498db40; border-radius:10px; padding:16px; height:180px'>
        <div style='font-size:1.5rem'>2️⃣</div>
        <div style='font-weight:700; margin:8px 0'>Previsão dos Próximos Meses</div>
        <div style='font-size:0.85rem; color:#555'>
            Veja o que as fontes oficiais (NOAA, CPTEC) estão prevendo para os próximos 6 meses.
            Útil para planejar contratos e compras antecipadas.
        </div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown("""
    <div style='background:#e67e2210; border:1px solid #e67e2240; border-radius:10px; padding:16px; height:180px'>
        <div style='font-size:1.5rem'>3️⃣</div>
        <div style='font-weight:700; margin:8px 0'>O Modelo Acerta?</div>
        <div style='font-size:0.85rem; color:#555'>
            Histórico de preços e resultados do backtesting. Veja com que frequência o modelo
            teria acertado nos últimos 10 anos.
        </div>
    </div>
    """, unsafe_allow_html=True)
with col4:
    st.markdown("""
    <div style='background:#8e44ad10; border:1px solid #8e44ad40; border-radius:10px; padding:16px; height:180px'>
        <div style='font-size:1.5rem'>4️⃣</div>
        <div style='font-weight:700; margin:8px 0'>Como Funciona</div>
        <div style='font-size:0.85rem; color:#555'>
            Para quem quer entender a metodologia. Mostra como o clima se correlaciona com preços,
            com gráficos e dados estatísticos.
        </div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ── O que cada página faz ─────────────────────────────────────────────────────
st.subheader("🗂️ O que cada página faz")

paginas = [
    ("🚨", "Alertas de Compra", "app.py — página inicial",
     "O painel principal. Mostra o semáforo de risco por produto baseado na previsão oficial da NOAA. "
     "Selecione seu perfil (varejista ou restaurante) para ver recomendações específicas. "
     "**Use diariamente ou toda semana para checar se algo mudou.**"),

    ("📅", "Previsão dos Próximos Meses", "Menu lateral → Previsao Proximos Meses",
     "Mostra o que as fontes climáticas oficiais estão prevendo, mês a mês, para os próximos 6 meses. "
     "Inclui os cards da NOAA (EUA), CPTEC/INPE e INMET com dados atualizados automaticamente. "
     "**Use ao planejar contratos com fornecedores ou cardápio da próxima estação.**"),

    ("📊", "O Modelo Acerta?", "Menu lateral → O Modelo Acerta",
     "Mostra o histórico real de variação de preços de 2015 a 2026 e o resultado do backtesting: "
     "o modelo teria acertado? Em quais fases? Com que precisão? "
     "**Use para entender os limites do modelo antes de tomar decisões grandes.**"),

    ("🔬", "Como Funciona", "Menu lateral → Como Funciona",
     "Página técnica para analistas. Mostra o heatmap de correlações entre clima e preço, "
     "a série temporal interativa e a tabela completa de correlações. "
     "**Use se quiser entender por que um alimento específico está em alerta.**"),

    ("📖", "Entendendo o Site", "Menu lateral → Entendendo o Site",
     "Esta página. Glossário, guia de uso e explicação das fontes de dados. "
     "**Compartilhe com novos usuários da equipe.**"),
]

for icone, nome, caminho, descricao in paginas:
    with st.expander(f"{icone} **{nome}** — {caminho}"):
        st.markdown(descricao)

st.divider()

# ── Fontes de dados ───────────────────────────────────────────────────────────
st.subheader("🌐 De onde vêm os dados?")

fontes = [
    ("🇺🇸 NOAA", "National Oceanic and Atmospheric Administration (EUA)",
     "https://www.cpc.ncep.noaa.gov",
     "A principal autoridade mundial em previsão climática. Publica mensalmente o status do ENSO "
     "(El Niño Watch, La Niña Advisory, etc.) com probabilidades para os próximos meses. "
     "É a fonte principal dos alertas do CustoClima."),

    ("🇧🇷 CPTEC/INPE", "Centro de Previsão de Tempo e Estudos Climáticos",
     "http://enos.cptec.inpe.br",
     "Instituto brasileiro de previsão climática, vinculado ao INPE. "
     "Monitora as condições do ENOS (El Niño e La Niña) com foco no Brasil e América do Sul. "
     "Complementa a previsão da NOAA com perspectiva nacional."),

    ("🇧🇷 INMET", "Instituto Nacional de Meteorologia",
     "https://portal.inmet.gov.br",
     "Órgão oficial do governo brasileiro para meteorologia operacional. "
     "Monitora temperatura, chuva e alertas em todo o Brasil. "
     "No CustoClima, serve como referência para dados regionais."),

    ("🏦 BCB / IPCA", "Banco Central do Brasil",
     "https://www.bcb.gov.br",
     "Fornece os dados históricos de variação de preços dos alimentos via IPCA (Índice de Preços "
     "ao Consumidor Amplo), divididos por grupo alimentar: carnes, panificados, horticultura, etc. "
     "É a base para calcular o impacto real no preço de cada produto."),

    ("🌦️ Open-Meteo", "Serviço europeu de dados climáticos históricos",
     "https://open-meteo.com",
     "Fornece dados históricos de precipitação (chuva em mm/mês) para cada estado brasileiro, "
     "de 2015 até hoje, sem necessidade de cadastro. Permite calcular a anomalia de chuva "
     "em relação à média histórica de cada região."),

    ("🛰️ NASA MODIS / AppEEARS", "National Aeronautics and Space Administration (EUA)",
     "https://appeears.earthdatacloud.nasa.gov",
     "Satélite que mede o NDVI (saúde da vegetação) mensalmente em 10 pontos agrícolas do Brasil. "
     "Confirma se uma seca afetou de fato a lavoura, mesmo quando a quantidade de chuva sozinha "
     "não conta a história completa."),
]

for icone_nome, descricao_curta, url, descricao_longa in fontes:
    with st.expander(f"**{icone_nome}** — {descricao_curta}"):
        st.markdown(f"{descricao_longa}\n\n🔗 [{url}]({url})")

st.divider()

# ── Glossário ─────────────────────────────────────────────────────────────────
st.subheader("📚 Glossário de Termos")

termos = {
    "🌊 El Niño": (
        "Aquecimento anormal das águas do Oceano Pacífico Equatorial. "
        "No Brasil, causa **seca no Nordeste** (menos chuva → safra menor → preços sobem). "
        "Previsível com 6 a 9 meses de antecedência."
    ),
    "🌊 La Niña": (
        "Resfriamento anormal do Pacífico — o fenômeno oposto ao El Niño. "
        "No Brasil, causa **enchentes no Sul** (chuva excessiva → perdas na lavoura → preços sobem). "
        "Também previsível com meses de antecedência."
    ),
    "📡 ENSO": (
        "El Niño–Oscilação Sul. Nome técnico do fenômeno que engloba El Niño e La Niña. "
        "Quando vir 'ENSO', pense: 'o estado do clima do Pacífico que afeta o Brasil'."
    ),
    "📊 ONI (Oceanic Niño Index)": (
        "Número que mede a intensidade do ENSO. "
        "**Acima de +0,5** = El Niño. **Abaixo de -0,5** = La Niña. **Entre -0,5 e +0,5** = Neutro. "
        "Quanto mais longe do zero, mais intenso o fenômeno."
    ),
    "🌧️ Precipitação": (
        "Quantidade de chuva medida em milímetros por mês (mm/mês). "
        "Precipitação abaixo da média histórica = seca. Acima da média = excesso de chuva."
    ),
    "🛰️ NDVI": (
        "Normalized Difference Vegetation Index — índice de saúde da vegetação medido por satélite. "
        "Quanto mais alto, mais verde e produtiva a lavoura. "
        "Uma lavoura pode estar sofrendo mesmo com alguma chuva — o NDVI captura isso."
    ),
    "📈 IPCA": (
        "Índice de Preços ao Consumidor Amplo — o índice oficial de inflação do Brasil. "
        "No CustoClima, usamos o IPCA dividido por grupo alimentar (carnes, panificados, etc.) "
        "para medir a variação real de preço de cada categoria."
    ),
    "🔗 Correlação": (
        "Medida de quanto uma variável (ex: chuva) está associada a outra (ex: preço). "
        "Vai de -0,5 a +0,5. Acima de 0,30 em valor absoluto = sinal forte e confiável. "
        "Próximo de zero = relação fraca, pode ser coincidência."
    ),
    "⏱️ Lag / Defasagem": (
        "Quantos meses depois do evento climático o preço reage. "
        "'Lag 3 meses' significa: uma seca hoje tende a encarecer o produto daqui a 3 meses. "
        "É justamente essa janela que permite agir antes que o preço suba."
    ),
    "🧪 Backtesting": (
        "Teste do modelo com dados históricos. Pergunta: 'Se eu tivesse usado esse modelo de 2015 "
        "a 2026, teria acertado as altas de preço?' "
        "O resultado é expresso em acurácia (%). 67% em El Niño forte é o principal resultado."
    ),
    "📋 El Niño Watch / Advisory": (
        "Classificação oficial da NOAA. "
        "**Watch** = condições favoráveis para El Niño nos próximos meses (fique atento). "
        "**Advisory** = El Niño já está ativo e deve continuar (agir agora). "
        "**Warning** = fase intensa em curso."
    ),
}

col_a, col_b = st.columns(2)
termos_lista = list(termos.items())
metade = len(termos_lista) // 2 + len(termos_lista) % 2

for i, (termo, definicao) in enumerate(termos_lista):
    col = col_a if i < metade else col_b
    with col:
        with st.expander(f"**{termo}**"):
            st.markdown(definicao)

st.divider()
st.caption(
    "CustoClima — projeto acadêmico FIAP · "
    "Dados: NOAA · CPTEC/INPE · INMET · BCB · Open-Meteo · NASA MODIS · "
    "Modelo com 67% de acurácia para El Niño forte."
)
