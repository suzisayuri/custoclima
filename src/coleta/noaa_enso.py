"""
Coleta do índice ENSO (El Niño / La Niña) via NOAA — CPC
Fonte  : https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt
Sem autenticação necessária.
Saída  : data/raw/noaa_enso_oni.csv

O que é o ONI (Oceanic Niño Index):
  - Mede a temperatura da superfície do mar no Pacífico Equatorial
  - ONI > +0.5°C por 5 meses = El Niño  → seca no Nordeste brasileiro
  - ONI < -0.5°C por 5 meses = La Niña  → chuvas intensas no Sul brasileiro
  - Esse índice é PREVISÍVEL com 6 a 9 meses de antecedência pelos modelos climáticos
  - Por isso ele é a "chave de previsão" do nosso pipeline

Uso:
  python src/coleta/noaa_enso.py
"""

import sys
import io
import requests
import pandas as pd
from pathlib import Path
import logging

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

URL_ONI = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"

# Cada estação de 3 meses é representada pelo mês central
ESTACAO_PARA_MES = {
    "DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4,
    "AMJ": 5, "MJJ": 6, "JJA": 7, "JAS": 8,
    "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12,
}


def classificar_enso(oni: float) -> str:
    """Classifica o evento ENSO com base no índice ONI."""
    if oni >= 1.5:
        return "el_nino_forte"
    if oni >= 0.5:
        return "el_nino_fraco"
    if oni <= -1.5:
        return "la_nina_forte"
    if oni <= -0.5:
        return "la_nina_fraca"
    return "neutro"


def impacto_brasil(fase: str) -> str:
    """Descreve o impacto esperado no Brasil para cada fase ENSO."""
    impactos = {
        "el_nino_forte": "Seca severa no Nordeste / Chuvas no Sul",
        "el_nino_fraco": "Tendencia de seca no Nordeste",
        "la_nina_forte": "Enchentes no Sul / Chuvas acima do normal no Nordeste",
        "la_nina_fraca": "Tendencia de chuvas intensas no Sul",
        "neutro":        "Sem anomalia climatica prevista",
    }
    return impactos.get(fase, "desconhecido")


def baixar_oni() -> pd.DataFrame:
    """Baixa e processa o arquivo ONI da NOAA."""
    try:
        resp = requests.get(URL_ONI, timeout=20)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao baixar ONI da NOAA: {e}")
        return pd.DataFrame()

    linhas = []
    for linha in resp.text.strip().split("\n"):
        partes = linha.split()
        if len(partes) < 4 or partes[0] == "SEAS":
            continue
        estacao = partes[0]
        ano     = int(partes[1])
        oni     = float(partes[3])  # coluna ANOM

        mes = ESTACAO_PARA_MES.get(estacao)
        if mes is None:
            continue

        # DJF do ano X representa Jan/X (o mês central é Jan)
        periodo = f"{ano}{str(mes).zfill(2)}"

        linhas.append({
            "periodo":  periodo,
            "ano":      ano,
            "mes":      mes,
            "estacao":  estacao,
            "oni":      oni,
            "fase_enso":    classificar_enso(oni),
            "impacto_brasil": impacto_brasil(classificar_enso(oni)),
        })

    return pd.DataFrame(linhas)


def main():
    logger.info("=" * 55)
    logger.info("  AgroClima Brasil — Coleta ENSO/ONI (NOAA)")
    logger.info("=" * 55)

    df = baixar_oni()

    if df.empty:
        logger.error("Nenhum dado coletado.")
        raise SystemExit(1)

    # Filtra para o período de análise e além (inclui dados recentes para previsão)
    df_analise = df[df["ano"] >= 2014].copy().reset_index(drop=True)

    saida = OUTPUT_DIR / "noaa_enso_oni.csv"
    df_analise.to_csv(saida, index=False, encoding="utf-8")

    print(f"\n{'='*60}")
    print("  NOAA ENSO/ONI — Resultado")
    print(f"{'='*60}")
    print(f"  Registros  : {len(df_analise)}")
    print(f"  Periodo    : {df_analise['periodo'].min()} a {df_analise['periodo'].max()}")
    print(f"\n  Distribuicao de fases ENSO (2015-2024):")
    sub = df_analise[df_analise["ano"].between(2015, 2024)]
    for fase, n in sub["fase_enso"].value_counts().items():
        print(f"    {fase:<20} {n:>3} meses")

    ultimo = df_analise.iloc[-1]
    print(f"\n  Ultimo registro disponivel:")
    print(f"    Periodo : {ultimo['periodo']}")
    print(f"    ONI     : {ultimo['oni']:+.2f} C")
    print(f"    Fase    : {ultimo['fase_enso']}")
    print(f"    Impacto : {ultimo['impacto_brasil']}")
    print(f"{'='*60}")

    logger.info("Coleta ENSO concluida.")


if __name__ == "__main__":
    main()
