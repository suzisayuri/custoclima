"""
Coleta de IPCA por grupo de alimentos via API do Banco Central do Brasil (BCB/SGS)
Fonte  : https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados
Sem autenticação necessária — API pública do BCB.
Saída  : data/raw/bcb_ipca_alimentos.csv

QUANDO USAR:
  Use este script quando o IBGE SIDRA (ibge_ipca.py) retornar erros 500.
  O BCB fornece os mesmos grupos alimentares do IPCA, com histórico desde os anos 1990.
  A saída é compatível com o ETL (mesmas colunas do ibge_ipca.py).

Como funciona:
  As séries BCB de produto alimentar são número-índice (base = algum período histórico).
  A variação mensal é calculada como: (indice_t / indice_t-1 - 1) × 100
  Por isso coletamos um mês antes do período de análise (dez/2014) para calcular jan/2015.

Uso:
  python src/coleta/bcb_ipca.py
"""

import sys
import io
import requests
import pandas as pd
from pathlib import Path
import time
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

BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
PAUSA = 0.8

# Séries do BCB para grupos alimentares do IPCA
# tipo "indice"  → série é número-índice; variação mensal calculada internamente
# tipo "mensal"  → série já é variação mensal (%)
SERIES = [
    {"codigo": 433,   "categoria": "IPCA - Geral",                       "id_cat": "ipca_geral",   "tipo": "mensal"},
    {"codigo": 7479,  "categoria": "IPCA - Carnes e peixes",             "id_cat": "carnes",       "tipo": "indice"},
    {"codigo": 7480,  "categoria": "IPCA - Aves e ovos",                 "id_cat": "aves_ovos",    "tipo": "indice"},
    {"codigo": 7481,  "categoria": "IPCA - Leite e derivados",           "id_cat": "leite",        "tipo": "indice"},
    {"codigo": 7482,  "categoria": "IPCA - Panificados",                 "id_cat": "panificados",  "tipo": "indice"},
    {"codigo": 7483,  "categoria": "IPCA - Cereais, leguminosas e oleag","id_cat": "cereais",      "tipo": "indice"},
    {"codigo": 7484,  "categoria": "IPCA - Tuberculos, raizes e legumes","id_cat": "tuberculos",   "tipo": "indice"},
    {"codigo": 7485,  "categoria": "IPCA - Horticultura",                "id_cat": "horticultura", "tipo": "indice"},
    {"codigo": 7486,  "categoria": "IPCA - Frutas",                      "id_cat": "frutas",       "tipo": "indice"},
    {"codigo": 7487,  "categoria": "IPCA - Acucares e derivados",        "id_cat": "acucares",     "tipo": "indice"},
    {"codigo": 7488,  "categoria": "IPCA - Oleos e gorduras",            "id_cat": "oleos",        "tipo": "indice"},
]


def coletar_serie_bcb(
    serie: dict,
    data_ini: str,
    data_fim: str,
    tentativas: int = 3,
) -> pd.DataFrame:
    """
    Baixa série do BCB entre data_ini e data_fim (formato DD/MM/AAAA).
    Retorna DataFrame com colunas: data, valor_bruto.
    """
    url = BASE_URL.format(codigo=serie["codigo"])
    params = {
        "formato":     "json",
        "dataInicial": data_ini,
        "dataFinal":   data_fim,
    }

    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code in (502, 503) and tentativa < tentativas:
                espera = tentativa * 5
                logger.warning(
                    f"  HTTP {resp.status_code} para {serie['codigo']} "
                    f"(tentativa {tentativa}). Aguardando {espera}s..."
                )
                time.sleep(espera)
                continue
            resp.raise_for_status()
            dados = resp.json()
            break
        except requests.exceptions.RequestException as e:
            if tentativa < tentativas:
                logger.warning(f"  Erro {serie['codigo']} tentativa {tentativa}: {e}")
                time.sleep(tentativa * 3)
            else:
                logger.error(f"Falhou apos {tentativas} tentativas: {serie['codigo']} — {e}")
                return pd.DataFrame()
    else:
        return pd.DataFrame()

    if not dados:
        logger.warning(f"  Sem dados para serie {serie['codigo']}.")
        return pd.DataFrame()

    df = pd.DataFrame(dados)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor_bruto"] = pd.to_numeric(df["valor"], errors="coerce")
    return df[["data", "valor_bruto"]].sort_values("data").reset_index(drop=True)


def calcular_variacao_mensal(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converte número-índice em variação mensal (%):
    var_t = (indice_t / indice_t-1 - 1) * 100
    Remove o primeiro mês (usado apenas como base de cálculo).
    """
    df = df.copy()
    df["variacao_mensal_pct"] = df["valor_bruto"].pct_change() * 100
    return df.iloc[1:].reset_index(drop=True)  # remove mês base (dez/2014)


def processar_serie(
    serie: dict,
    ano_inicio: int = 2015,
    ano_fim: int = 2026,
) -> pd.DataFrame:
    """
    Coleta e processa uma série. Retorna DataFrame com colunas compatíveis com o ETL.
    """
    # Um mês antes para calcular o primeiro delta
    data_ini = f"01/12/{ano_inicio - 1}"
    data_fim = f"31/12/{ano_fim}"

    df_raw = coletar_serie_bcb(serie, data_ini, data_fim)
    if df_raw.empty:
        return pd.DataFrame()

    if serie["tipo"] == "indice":
        df = calcular_variacao_mensal(df_raw)
    else:
        # Série já está em variação mensal; remove apenas o mês base se necessário
        df = df_raw[df_raw["data"].dt.year >= ano_inicio].copy()
        df["variacao_mensal_pct"] = df["valor_bruto"]

    # Filtra período de interesse
    df = df[
        (df["data"].dt.year >= ano_inicio) &
        (df["data"].dt.year <= ano_fim)
    ].copy()

    df["periodo"]        = df["data"].dt.strftime("%Y%m")
    df["ano"]            = df["data"].dt.year.astype("int16")
    df["mes"]            = df["data"].dt.month.astype("int16")
    df["id_variavel"]    = "2265"  # compatível com formato IBGE
    df["variavel"]       = "IPCA - Variacao mensal"
    df["unidade"]        = "%"
    df["id_categoria"]   = serie["id_cat"]
    df["categoria"]      = serie["categoria"]
    df["valor"]          = df["variacao_mensal_pct"].round(4)

    colunas = ["periodo", "ano", "mes", "id_variavel", "variavel",
               "unidade", "id_categoria", "categoria", "valor"]
    return df[colunas].copy()


def main():
    logger.info("=" * 55)
    logger.info("  AgroClima Brasil — Coleta BCB IPCA por Alimento")
    logger.info("=" * 55)
    logger.info("  Fonte: api.bcb.gov.br (sem token, API publica)")
    logger.info("=" * 55)

    todos = []

    for i, serie in enumerate(SERIES, 1):
        logger.info(f"[{i}/{len(SERIES)}] {serie['codigo']} — {serie['categoria']}")
        df = processar_serie(serie)

        if not df.empty:
            todos.append(df)
            nulos = df["valor"].isna().sum()
            logger.info(
                f"  -> {len(df)} registros | {df['periodo'].min()} a {df['periodo'].max()} "
                f"| nulos: {nulos}"
            )
        else:
            logger.warning(f"  -> sem dados para {serie['categoria']}")

        if i < len(SERIES):
            time.sleep(PAUSA)

    if not todos:
        logger.error("Nenhuma serie coletada.")
        raise SystemExit(1)

    df_final = (
        pd.concat(todos, ignore_index=True)
        .sort_values(["id_categoria", "periodo"])
        .reset_index(drop=True)
    )

    saida = OUTPUT_DIR / "bcb_ipca_alimentos.csv"
    df_final.to_csv(saida, index=False, encoding="utf-8")

    print(f"\n{'='*60}")
    print("  BCB IPCA por Grupo Alimentar — Resultado")
    print(f"{'='*60}")
    print(f"  Registros  : {len(df_final):,}")
    print(f"  Periodo    : {df_final['periodo'].min()} a {df_final['periodo'].max()}")
    print(f"  Categorias : {df_final['id_categoria'].nunique()} grupos")
    nulos = df_final["valor"].isna().sum()
    print(f"  Nulos      : {nulos} ({nulos/len(df_final)*100:.1f}%)")
    print(f"  Salvo em   : {saida}")
    print(f"\n  Grupos coletados:")
    for cat in sorted(df_final["id_categoria"].unique()):
        nome = df_final[df_final["id_categoria"] == cat]["categoria"].iloc[0]
        print(f"    {cat:<15}  {nome}")
    print(f"{'='*60}")

    logger.info("Coleta BCB concluida.")


if __name__ == "__main__":
    main()
