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
