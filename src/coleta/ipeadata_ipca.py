"""
Coleta IPCA geral via IPEADATA — fallback para quando o IBGE SIDRA estiver instável.
Fonte  : http://ipeadata.gov.br/api/odata4/
Saída  : data/raw/ipeadata_ipca_geral.csv

QUANDO USAR:
  Use este script se src/coleta/ibge_ipca.py retornar erros 500 persistentes.
  O IPEADATA fornece o IPCA Geral mensal (índice agregado, sem breakdown por produto).
  Para análise de correlação agregada (clima × inflação alimentar geral) isso é suficiente.
  Para análise por produto (arroz, feijão, carnes), o IBGE SIDRA é insubstituível.

Uso:
  python src/coleta/ipeadata_ipca.py
"""

import sys
import io
import requests
import pandas as pd
from pathlib import Path
import logging
import time

# Garante saída UTF-8 no Windows (evita UnicodeEncodeError no terminal)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "http://ipeadata.gov.br/api/odata4/ValoresSerie"

# Séries disponíveis e confirmadas no IPEADATA
# Adicione mais conforme encontrar códigos válidos em: ipeadata.gov.br/Default.aspx
SERIES = [
    {
        "codigo":    "PRECOS12_IPCAG12",
        "nome":      "IPCA - Variação mensal - Geral",
        "unidade":   "%",
        "categoria": "Índice Geral",
        "id_cat":    "ipca_geral",
    },
]


def coletar_serie(serie: dict, ano_inicio: int = 2015, ano_fim: int = 2024) -> pd.DataFrame:
    """
    Coleta uma série temporal do IPEADATA entre ano_inicio e ano_fim.
    A API IPEADATA usa formato de data ISO (YYYY-MM-DDT00:00:00).
    """
    data_ini = f"{ano_inicio}-01-01T00:00:00"
    data_fim = f"{ano_fim}-12-31T00:00:00"

    url = (
        f"{BASE_URL}(SERCODIGO='{serie['codigo']}')"
        f"?$filter=VALDATA ge {data_ini} and VALDATA le {data_fim}"
        f"&$orderby=VALDATA asc"
    )

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        valores = resp.json().get("value", [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao coletar {serie['codigo']}: {e}")
        return pd.DataFrame()

    if not valores:
        logger.warning(f"Nenhum valor retornado para {serie['codigo']}.")
        return pd.DataFrame()

    df = pd.DataFrame(valores)
    df["data"]  = pd.to_datetime(df["VALDATA"], utc=True).dt.tz_localize(None)
    df["valor"] = pd.to_numeric(df["VALVALOR"], errors="coerce")

    df["periodo"]    = df["data"].dt.strftime("%Y%m")
    df["ano"]        = df["data"].dt.year.astype("int16")
    df["mes"]        = df["data"].dt.month.astype("int16")
    df["codigo"]     = serie["codigo"]
    df["nome"]       = serie["nome"]
    df["unidade"]    = serie["unidade"]
    df["categoria"]  = serie["categoria"]
    df["id_categoria"] = serie["id_cat"]

    return df[["periodo", "ano", "mes", "id_categoria", "categoria",
               "codigo", "nome", "unidade", "valor"]].copy()


def main():
    logger.info("=" * 55)
    logger.info("  AgroClima Brasil — Coleta IPEADATA (fallback IBGE)")
    logger.info("=" * 55)

    todos = []
    for i, serie in enumerate(SERIES, 1):
        logger.info(f"[{i}/{len(SERIES)}] {serie['codigo']} — {serie['nome']}")
        df = coletar_serie(serie)
        if not df.empty:
            todos.append(df)
            logger.info(f"  -> {len(df)} registros | {df['periodo'].min()} a {df['periodo'].max()}")
        if i < len(SERIES):
            time.sleep(0.5)

    if not todos:
        logger.error("Nenhum dado coletado.")
        raise SystemExit(1)

    df_final = pd.concat(todos, ignore_index=True)

    saida = OUTPUT_DIR / "ipeadata_ipca_geral.csv"
    df_final.to_csv(saida, index=False, encoding="utf-8")

    print(f"\n{'='*55}")
    print("  IPEADATA IPCA — Resultado")
    print(f"{'='*55}")
    print(f"  Registros  : {len(df_final):,}")
    print(f"  Período    : {df_final['periodo'].min()} a {df_final['periodo'].max()}")
    print(f"  Séries     : {df_final['codigo'].nunique()}")
    nulos = df_final["valor"].isna().sum()
    print(f"  Nulos      : {nulos} ({nulos/len(df_final)*100:.1f}%)")
    print(f"  Salvo em   : {saida}")
    print(f"\n  Nota: use ibge_ipca.py para dados por produto (carnes, cereais, etc.)")
    print(f"{'='*55}")

    logger.info("Coleta IPEADATA finalizada.")


if __name__ == "__main__":
    main()
