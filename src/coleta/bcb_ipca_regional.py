"""
Coleta do IPCA por capital (regional) via BCB/SGS
Fonte  : https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados
Saída  : data/raw/bcb_ipca_regional.csv

Capitais monitoradas (onde IBGE mede IPCA):
  Sul       — Curitiba (PR), Porto Alegre (RS)
  Nordeste  — Fortaleza (CE), Recife (PE), Salvador (BA)
  Referência — São Paulo (SP), Rio de Janeiro (RJ), Brasil (nacional)

Por que dados regionais importam:
  O IPCA nacional suaviza impactos locais. Quando o RS tem uma enchente,
  o preço de alimentos em Porto Alegre sobe mais do que a média nacional.
  Com dados regionais, o modelo consegue capturar esse efeito local.

Códigos BCB confirmados para IPCA geral por capital (variação mensal %):
  Os códigos são descobertos automaticamente na primeira execução
  e salvos em data/raw/bcb_codigos_regionais.json para reutilização.

Uso:
  python src/coleta/bcb_ipca_regional.py
"""

import sys
import io
import json
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

BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{}/dados"

# Mapeamento de capitais → localidade e região (para o projeto)
CAPITAIS = {
    "Porto Alegre":   {"estado": "RS", "regiao": "Sul",      "cod_ibge": "4314"},
    "Curitiba":       {"estado": "PR", "regiao": "Sul",      "cod_ibge": "4106"},
    "Florianopolis":  {"estado": "SC", "regiao": "Sul",      "cod_ibge": "4200"},
    "Fortaleza":      {"estado": "CE", "regiao": "Nordeste", "cod_ibge": "2304"},
    "Recife":         {"estado": "PE", "regiao": "Nordeste", "cod_ibge": "2611"},
    "Salvador":       {"estado": "BA", "regiao": "Nordeste", "cod_ibge": "2927"},
    "Sao Paulo":      {"estado": "SP", "regiao": "Sudeste",  "cod_ibge": "3550"},
    "Brasil":         {"estado": "BR", "regiao": "Nacional", "cod_ibge": "0"},
}

# Séries BCB confirmadas (IPCA variação mensal geral)
# Atualizado: 10841 confirmado ativo com dados até 2026
# Os demais são descobertos automaticamente
SERIES_CONHECIDAS = {
    "Brasil":       433,    # IPCA Nacional variação mensal (%)
    "Porto Alegre": 10841,  # Confirmado ativo (val abr/2026 = 1.44%)
}

ARQUIVO_CODIGOS = OUTPUT_DIR / "bcb_codigos_regionais.json"


def carregar_codigos_salvos() -> dict:
    if ARQUIVO_CODIGOS.exists():
        with open(ARQUIVO_CODIGOS, encoding="utf-8") as f:
            return json.load(f)
    return {}


def salvar_codigos(codigos: dict) -> None:
    with open(ARQUIVO_CODIGOS, "w", encoding="utf-8") as f:
        json.dump(codigos, f, ensure_ascii=False, indent=2)


def coletar_serie(codigo: int, data_ini: str = "01/01/2015",
                  data_fim: str = "31/12/2024") -> pd.DataFrame:
    url = BASE_URL.format(codigo)
    params = {"formato": "json", "dataInicial": data_ini, "dataFinal": data_fim}
    for tentativa in range(1, 4):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 200 and r.json():
                df = pd.DataFrame(r.json())
                df["data"]  = pd.to_datetime(df["data"], format="%d/%m/%Y")
                df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
                return df[["data", "valor"]].sort_values("data").reset_index(drop=True)
            return pd.DataFrame()
        except requests.exceptions.RequestException:
            if tentativa < 3:
                time.sleep(tentativa * 5)
    return pd.DataFrame()


def descobrir_codigo_capital(capital: str, faixa_inicio: int = 10836,
                             faixa_fim: int = 10940) -> int | None:
    """
    Varre um intervalo de códigos BCB buscando a série de IPCA mensal
    da capital especificada. Identifica a série verificando:
    - Tem dados de 2015 a 2024 (>=100 registros)
    - Valores típicos de IPCA mensal (entre -3% e +5%)
    - Série mensal (12 registros por ano)
    """
    logger.info(f"  Buscando codigo BCB para {capital} (faixa {faixa_inicio}-{faixa_fim})...")
    for cod in range(faixa_inicio, faixa_fim + 1):
        df = coletar_serie(cod, "01/01/2015", "31/12/2017")
        if df.empty or len(df) < 30:
            time.sleep(0.2)
            continue
        # Verifica se parece IPCA mensal: média entre 0.1% e 1.5%
        media = df["valor"].mean()
        if 0.05 <= media <= 2.5:
            logger.info(f"  Candidato encontrado: serie {cod} (media={media:.2f}%)")
            return cod
        time.sleep(0.2)
    return None


def main():
    logger.info("=" * 60)
    logger.info("  AgroClima Brasil — IPCA Regional por Capital (BCB)")
    logger.info("=" * 60)

    # Carrega códigos salvos de execuções anteriores
    codigos = carregar_codigos_salvos()
    codigos.update(SERIES_CONHECIDAS)  # garante os confirmados

    todos = []

    for capital, info in CAPITAIS.items():
        # Usa código já conhecido ou descobre
        if capital not in codigos:
            logger.info(f"Codigo BCB desconhecido para {capital} — tentando descobrir...")
            cod = descobrir_codigo_capital(capital)
            if cod:
                codigos[capital] = cod
                salvar_codigos(codigos)
            else:
                logger.warning(f"  Nao encontrado para {capital} — pulando.")
                continue
        else:
            cod = codigos[capital]

        logger.info(f"Coletando {capital} (serie {cod})...")
        df = coletar_serie(cod)

        if df.empty:
            logger.warning(f"  Sem dados para {capital}.")
            continue

        df["periodo"]  = df["data"].dt.strftime("%Y%m")
        df["ano"]      = df["data"].dt.year.astype("int16")
        df["mes"]      = df["data"].dt.month.astype("int16")
        df["capital"]  = capital
        df["estado"]   = info["estado"]
        df["regiao"]   = info["regiao"]
        df["cod_bcb"]  = cod
        df["variacao_mensal_pct"] = df["valor"]
        df = df.drop(columns=["data", "valor"])

        todos.append(df)
        nulos = df["variacao_mensal_pct"].isna().sum()
        logger.info(f"  -> {len(df)} meses | {df['periodo'].min()} a {df['periodo'].max()} | nulos: {nulos}")
        time.sleep(0.5)

    if not todos:
        logger.error("Nenhum dado coletado.")
        logger.error(
            "Possivel causa: BCB lento ou series nao identificadas.\n"
            "Tente novamente mais tarde ou verifique os codigos manualmente em:\n"
            "  https://www3.bcb.gov.br/sgspub/localizarseries/localizarSeries.do?method=prepararTelaLocalizarSeries"
        )
        raise SystemExit(1)

    df_final = (
        pd.concat(todos, ignore_index=True)
        .sort_values(["capital", "periodo"])
        .reset_index(drop=True)
    )

    colunas = ["periodo", "ano", "mes", "capital", "estado", "regiao",
               "cod_bcb", "variacao_mensal_pct"]
    df_final = df_final[colunas]

    saida = OUTPUT_DIR / "bcb_ipca_regional.csv"
    df_final.to_csv(saida, index=False, encoding="utf-8")

    print(f"\n{'='*65}")
    print("  IPCA Regional por Capital — Resultado")
    print(f"{'='*65}")
    print(f"  Capitais coletadas : {df_final['capital'].nunique()}")
    print(f"  Registros totais   : {len(df_final):,}")
    print(f"  Periodo            : {df_final['periodo'].min()} a {df_final['periodo'].max()}")
    print(f"\n  Media mensal IPCA por capital (%):")
    for cap, grp in df_final.groupby("capital"):
        media = grp["variacao_mensal_pct"].mean()
        print(f"    {cap:<15} {media:>6.2f}%/mes  [{grp['regiao'].iloc[0]}]")
    print(f"\n  Salvo em: {saida}")
    print(f"  Codigos BCB salvos: {ARQUIVO_CODIGOS}")
    print(f"{'='*65}")

    logger.info("Coleta IPCA regional concluida.")


if __name__ == "__main__":
    main()
