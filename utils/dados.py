"""Funções de carregamento de dados compartilhadas entre as páginas."""
import pandas as pd
import streamlit as st
from pathlib import Path

ROOT = Path(__file__).parent.parent
RAW  = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"


@st.cache_data
def carregar_alertas() -> pd.DataFrame:
    df = pd.read_csv(PROC / "previsao_alertas.csv")
    return df


@st.cache_data
def carregar_oni() -> pd.DataFrame:
    df = pd.read_csv(RAW / "noaa_enso_oni.csv", dtype={"periodo": str})
    df["data"] = pd.to_datetime(df["periodo"], format="%Y%m")
    return df


@st.cache_data
def carregar_precipitacao() -> pd.DataFrame:
    return pd.read_csv(RAW / "openmeteo_precipitacao.csv", dtype={"periodo": str})


@st.cache_data
def carregar_ndvi() -> pd.DataFrame:
    return pd.read_csv(RAW / "nasa_ndvi_regioes.csv", dtype={"periodo": str})


@st.cache_data
def carregar_correlacoes() -> pd.DataFrame:
    df = pd.read_csv(PROC / "correlacao_resultados.csv")
    if "lag" in df.columns:
        df = df.rename(columns={"lag": "defasagem_meses"})
    return df


@st.cache_data
def carregar_correlacoes_ndvi() -> pd.DataFrame:
    return pd.read_csv(PROC / "correlacao_ndvi.csv")


@st.cache_data
def carregar_precos() -> pd.DataFrame:
    df = pd.read_csv(PROC / "fato_preco.csv", dtype={"periodo": str})
    if "id_categoria" in df.columns:
        df = df.rename(columns={"id_categoria": "id_produto",
                                "categoria": "produto"})
    df["data"] = pd.to_datetime(df["periodo"], format="%Y%m")
    return df


@st.cache_data
def carregar_backtesting() -> pd.DataFrame:
    return pd.read_csv(PROC / "backtesting_v2.csv")


@st.cache_data
def carregar_corr_oni_precip() -> pd.DataFrame:
    return pd.read_csv(PROC / "correlacao_oni_precip.csv")


@st.cache_data(ttl=3600 * 12)  # atualiza a cada 12 horas
def buscar_previsao_enso_noaa() -> dict:
    """Busca o status oficial do ENSO no NOAA CPC e retorna em linguagem simples."""
    import re, html as html_lib, requests

    try:
        url = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml"
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        text = r.text

        # ── Status (Watch / Advisory / Neutral) ──────────────────────────────
        match = re.search(
            r'ENSO Alert System Status:.*?<span[^>]*>(.*?)</span>', text, re.DOTALL
        )
        status_raw = html_lib.unescape(match.group(1)).strip() if match else ""
        status_raw = re.sub(r'<[^>]+>', '', status_raw).strip()

        # ── Probabilidade ──────────────────────────────────────────────────────
        match_prob = re.search(r'(\d+)&#37;\s*chance in ([A-Za-z\-]+\s+\d{4})', text)
        probabilidade = None
        if match_prob:
            pct   = match_prob.group(1)
            prazo = match_prob.group(2)
            probabilidade = f"{pct}% de chance em {prazo}"

        # ── Mapeia status → linguagem do gestor ───────────────────────────────
        s = status_raw.upper()
        if "EL NI" in s and "ADVISORY" in s:
            fase, oni_sug, cor, icone = "El Niño confirmado", 1.0, "#e74c3c", "🔴"
            impacto = "Seca no Nordeste em andamento. Risco alto de alta nos preços."
        elif "EL NI" in s and "WATCH" in s:
            fase, oni_sug, cor, icone = "El Niño previsto", 0.7, "#e67e22", "🟠"
            impacto = "El Niño deve se desenvolver em breve. Prepare-se para seca no Nordeste."
        elif "LA NI" in s and "ADVISORY" in s:
            fase, oni_sug, cor, icone = "La Niña confirmada", -1.0, "#2980b9", "🔵"
            impacto = "La Niña em andamento. Risco de enchentes no Sul."
        elif "LA NI" in s and "WATCH" in s:
            fase, oni_sug, cor, icone = "La Niña prevista", -0.7, "#5dade2", "🔵"
            impacto = "La Niña deve se desenvolver. Atenção a chuvas acima do normal no Sul."
        else:
            fase, oni_sug, cor, icone = "Neutro", 0.0, "#27ae60", "🟢"
            impacto = "Nenhuma anomalia climática significativa prevista."

        return {
            "ok":           True,
            "status_raw":   status_raw,
            "fase":         fase,
            "oni_sugerido": oni_sug,
            "cor":          cor,
            "icone":        icone,
            "impacto":      impacto,
            "probabilidade": probabilidade,
            "fonte_url":    url,
        }

    except Exception as exc:
        return {"ok": False, "erro": str(exc)}


# Coordenadas dos estados para o mapa
COORDS_ESTADOS = {
    "CE": (-3.72,  -38.54, "Fortaleza"),
    "PE": (-8.05,  -34.88, "Recife"),
    "RN": (-5.80,  -35.21, "Natal"),
    "BA": (-12.97, -38.50, "Salvador"),
    "PB": (-7.12,  -34.84, "Joao Pessoa"),
    "MA": (-2.53,  -44.30, "Sao Luis"),
    "PI": (-5.09,  -42.80, "Teresina"),
    "AL": (-9.67,  -35.74, "Maceio"),
    "SE": (-10.95, -37.07, "Aracaju"),
    "RS": (-30.03, -51.23, "Porto Alegre"),
    "SC": (-27.60, -48.55, "Florianopolis"),
    "PR": (-25.43, -49.27, "Curitiba"),
}

COR_RISCO = {
    "ALTO":     "#e74c3c",
    "MODERADO": "#e67e22",
    "BAIXO":    "#f1c40f",
    "NORMAL":   "#2ecc71",
}

FASE_EMOJI = {
    "el_nino_forte": "🔴",
    "el_nino_fraco": "🟠",
    "neutro":        "🟢",
    "la_nina_fraca": "🔵",
    "la_nina_forte": "🟣",
}
