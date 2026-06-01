"""
Coleta de precipitação histórica via Open-Meteo Historical Weather API
Fonte  : https://archive-api.open-meteo.com/v1/archive
Sem autenticação necessária — API gratuita e aberta.
Saída  : data/raw/openmeteo_precipitacao.csv

Por que Open-Meteo em vez do INMET:
  - INMET exige token de cadastro e retorna dados por estação (não por estado)
  - Open-Meteo fornece dados gridados (ERA5 reanalysis) para qualquer coordenada,
    cobre 1940–presente, sem limite de requisições e sem autenticação.
  - Para o projeto, usamos a capital de cada estado como ponto representativo.

Estados cobertos:
  Nordeste — CE, PE, RN, BA, PB, MA, PI, AL, SE  (seca e variação de oferta)
  Sul       — RS, SC, PR                          (enchentes e excesso hídrico)
"""

import sys
import io
import requests
import pandas as pd
from pathlib import Path
import time
import logging

# UTF-8 no terminal Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Capitais representativas de cada estado com bioma de referência
LOCALIDADES = [
    # ── Nordeste ─────────────────────────────────────────────────────────────
    {"estado": "CE", "regiao": "Nordeste", "bioma": "Caatinga",      "cidade": "Fortaleza",     "lat": -3.717,  "lon": -38.543},
    {"estado": "PE", "regiao": "Nordeste", "bioma": "Caatinga",      "cidade": "Recife",        "lat": -8.054,  "lon": -34.881},
    {"estado": "RN", "regiao": "Nordeste", "bioma": "Caatinga",      "cidade": "Natal",         "lat": -5.795,  "lon": -35.209},
    {"estado": "BA", "regiao": "Nordeste", "bioma": "Caatinga",      "cidade": "Salvador",      "lat": -12.971, "lon": -38.501},
    {"estado": "PB", "regiao": "Nordeste", "bioma": "Caatinga",      "cidade": "João Pessoa",   "lat": -7.119,  "lon": -34.845},
    {"estado": "MA", "regiao": "Nordeste", "bioma": "Cerrado",       "cidade": "São Luís",      "lat": -2.530,  "lon": -44.304},
    {"estado": "PI", "regiao": "Nordeste", "bioma": "Caatinga",      "cidade": "Teresina",      "lat": -5.089,  "lon": -42.802},
    {"estado": "AL", "regiao": "Nordeste", "bioma": "Mata Atlântica","cidade": "Maceió",        "lat": -9.665,  "lon": -35.735},
    {"estado": "SE", "regiao": "Nordeste", "bioma": "Mata Atlântica","cidade": "Aracaju",       "lat": -10.947, "lon": -37.073},
    # ── Sul ──────────────────────────────────────────────────────────────────
    {"estado": "RS", "regiao": "Sul",      "bioma": "Pampa",         "cidade": "Porto Alegre",  "lat": -30.033, "lon": -51.230},
    {"estado": "SC", "regiao": "Sul",      "bioma": "Mata Atlântica","cidade": "Florianópolis", "lat": -27.595, "lon": -48.548},
    {"estado": "PR", "regiao": "Sul",      "bioma": "Mata Atlântica","cidade": "Curitiba",      "lat": -25.428, "lon": -49.273},
]

PAUSA_SEGUNDOS = 1.0


def coletar_precipitacao_estado(
    localidade: dict, ano_inicio: int = 2015, ano_fim: int = 2024
) -> pd.DataFrame:
    """
    Coleta dados diários da Open-Meteo e agrega para mensal.
    Variáveis coletadas: precipitação total, temperatura máx/mín.
    """
    params = {
        "latitude":   localidade["lat"],
        "longitude":  localidade["lon"],
        "start_date": f"{ano_inicio}-01-01",
        "end_date":   f"{ano_fim}-12-31",
        "daily":      "precipitation_sum,temperature_2m_max,temperature_2m_min",
        "timezone":   "America/Sao_Paulo",
    }

    for tentativa in range(1, 4):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=60)
            if resp.status_code == 429:
                espera = tentativa * 10
                logger.warning(
                    f"Rate limit (429) para {localidade['cidade']} "
                    f"(tentativa {tentativa}/3). Aguardando {espera}s..."
                )
                time.sleep(espera)
                continue
            resp.raise_for_status()
            dados = resp.json()
            break
        except requests.exceptions.Timeout:
            if tentativa < 3:
                logger.warning(f"Timeout {localidade['cidade']} (tentativa {tentativa}). Retentando...")
                time.sleep(5)
            else:
                logger.error(f"Timeout definitivo para {localidade['cidade']}.")
                return pd.DataFrame()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Erro HTTP para {localidade['cidade']}: {e}")
            return pd.DataFrame()
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de rede para {localidade['cidade']}: {e}")
            return pd.DataFrame()
    else:
        logger.error(f"Falhou apos 3 tentativas para {localidade['cidade']}.")
        return pd.DataFrame()

    diario = dados.get("daily", {})
    datas  = diario.get("time", [])

    if not datas:
        logger.warning(f"Resposta vazia para {localidade['cidade']}.")
        return pd.DataFrame()

    df = pd.DataFrame({
        "data":           pd.to_datetime(datas),
        "precipitacao_mm": pd.to_numeric(diario.get("precipitation_sum", []), errors="coerce"),
        "temp_max":        pd.to_numeric(diario.get("temperature_2m_max", []),  errors="coerce"),
        "temp_min":        pd.to_numeric(diario.get("temperature_2m_min", []),  errors="coerce"),
    })

    # Agrega dados diários para mensais
    df["periodo"] = df["data"].dt.strftime("%Y%m")
    df_mensal = df.groupby("periodo").agg(
        precipitacao_mm_total        =("precipitacao_mm", "sum"),
        precipitacao_dias_sem_chuva  =("precipitacao_mm", lambda x: (x == 0).sum()),
        temp_max_media               =("temp_max", "mean"),
        temp_min_media               =("temp_min", "mean"),
        registros_diarios            =("precipitacao_mm", "count"),
    ).reset_index()

    df_mensal["estado"] = localidade["estado"]
    df_mensal["regiao"] = localidade["regiao"]
    df_mensal["bioma"]  = localidade["bioma"]
    df_mensal["cidade"] = localidade["cidade"]
    df_mensal["ano"]    = df_mensal["periodo"].str[:4].astype(int)
    df_mensal["mes"]    = df_mensal["periodo"].str[4:].astype(int)

    return df_mensal


def imprimir_resumo(df: pd.DataFrame) -> None:
    sep = "=" * 55
    print(f"\n{sep}")
    print("  Precipitação — Open-Meteo (mensal)")
    print(sep)
    print(f"  Registros  : {len(df):,}")
    print(f"  Periodo    : {df['periodo'].min()} a {df['periodo'].max()}")
    print(f"  Estados    : {', '.join(sorted(df['estado'].unique()))}")
    nulos = df["precipitacao_mm_total"].isna().sum()
    print(f"  Nulos prec : {nulos:,} ({nulos/len(df)*100:.1f}%)")
    print(f"\n  Média mensal por região (mm):")
    for reg, grp in df.groupby("regiao"):
        media = grp["precipitacao_mm_total"].mean()
        print(f"    {reg:<12} {media:>8.1f} mm/mês")
    print(sep)


def main():
    logger.info("=" * 55)
    logger.info("  AgroClima Brasil — Coleta Clima (Open-Meteo)")
    logger.info("=" * 55)
    logger.info("  Fonte: archive-api.open-meteo.com (sem token)")
    logger.info("=" * 55)

    todos = []

    for i, loc in enumerate(LOCALIDADES, 1):
        logger.info(f"[{i}/{len(LOCALIDADES)}] {loc['cidade']} ({loc['estado']})...")
        df = coletar_precipitacao_estado(loc)

        if not df.empty:
            todos.append(df)
            logger.info(
                f"  -> {len(df)} meses | media: {df['precipitacao_mm_total'].mean():.1f} mm/mes"
            )
        else:
            logger.warning(f"  -> sem dados para {loc['cidade']}")

        if i < len(LOCALIDADES):
            time.sleep(PAUSA_SEGUNDOS)

    if not todos:
        logger.error("Nenhum dado coletado. Verifique conexão.")
        raise SystemExit(1)

    colunas_ord = [
        "periodo", "ano", "mes", "estado", "regiao", "bioma", "cidade",
        "precipitacao_mm_total", "precipitacao_dias_sem_chuva",
        "temp_max_media", "temp_min_media", "registros_diarios",
    ]
    df_final = (
        pd.concat(todos, ignore_index=True)
        .sort_values(["estado", "periodo"])
        .reset_index(drop=True)
    )[colunas_ord]

    saida = OUTPUT_DIR / "openmeteo_precipitacao.csv"
    df_final.to_csv(saida, index=False, encoding="utf-8")
    logger.info(f"Arquivo salvo: {saida} ({saida.stat().st_size / 1024:.1f} KB)")

    imprimir_resumo(df_final)
    logger.info("Coleta de precipitação finalizada.")


if __name__ == "__main__":
    main()
