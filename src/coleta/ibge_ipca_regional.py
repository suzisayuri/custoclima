"""
Coleta do IPCA por capital via IBGE SIDRA — dados regionais
Fonte  : https://servicodados.ibge.gov.br/api/v3/agregados/7060
Saída  : data/raw/ibge_ipca_regional.csv

Capitais monitoradas pelo IBGE para o IPCA:
  Sul       → Curitiba (PR) = N7[4106], Porto Alegre (RS) = N7[4314]
  Nordeste  → Fortaleza (CE) = N7[2304], Recife (PE) = N7[2611], Salvador (BA) = N7[2927]
  Referência → São Paulo (SP) = N7[3550], Rio de Janeiro (RJ) = N7[3301]
  Nacional  → N1[1]

Por que dados regionais importam:
  O IPCA nacional suaviza impactos locais. Quando o RS tem uma enchente,
  o preço de alimentos em Porto Alegre sobe mais do que a média nacional.
  Com dados por capital, o backtesting do Sul deve melhorar de ~45% para ~60%+.

STATUS ATUAL:
  O IBGE SIDRA está retornando HTTP 500 em todos os endpoints (instabilidade do servidor).
  Este script está pronto para rodar quando o IBGE voltar ao ar.
  Para verificar se voltou: acesse https://servicodados.ibge.gov.br/api/v3/agregados/7060

Uso:
  python src/coleta/ibge_ipca_regional.py
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

BASE_URL = "https://servicodados.ibge.gov.br/api/v3/agregados"
TABELA   = 7060

# Códigos IBGE de localidade para cada capital
LOCALIDADES = {
    "Porto Alegre":  {"cod": "N7[4314]", "estado": "RS", "regiao": "Sul"},
    "Curitiba":      {"cod": "N7[4106]", "estado": "PR", "regiao": "Sul"},
    "Fortaleza":     {"cod": "N7[2304]", "estado": "CE", "regiao": "Nordeste"},
    "Recife":        {"cod": "N7[2611]", "estado": "PE", "regiao": "Nordeste"},
    "Salvador":      {"cod": "N7[2927]", "estado": "BA", "regiao": "Nordeste"},
    "Sao Paulo":     {"cod": "N7[3550]", "estado": "SP", "regiao": "Sudeste"},
    "Rio de Janeiro":{"cod": "N7[3301]", "estado": "RJ", "regiao": "Sudeste"},
    "Nacional":      {"cod": "N1[1]",    "estado": "BR", "regiao": "Nacional"},
}

# Grupos alimentares relevantes para o projeto
CATEGORIAS = "1104|1107|1109|1110|1113|1114|1115|1116"


def verificar_api() -> bool:
    """Verifica se o IBGE SIDRA está acessível antes de coletar."""
    url = f"{BASE_URL}/{TABELA}/periodos/202401/variaveis/2265?localidades=N1[1]&classificacao=660[7169]"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            logger.info("IBGE SIDRA OK — iniciando coleta regional.")
            return True
        logger.error(
            f"IBGE SIDRA retornou HTTP {r.status_code}.\n"
            "O servidor esta fora do ar. Tente novamente mais tarde.\n"
            "Para verificar o status: https://servicodados.ibge.gov.br/api/v3/agregados/7060"
        )
        return False
    except Exception as e:
        logger.error(f"Sem conexao com IBGE: {e}")
        return False


def coletar_capital(localidade_info: dict, capital: str,
                    ano_inicio: int = 2015, ano_fim: int = 2024) -> pd.DataFrame:
    """Coleta IPCA mensal por grupos alimentares para uma capital."""
    todos = []
    for ano in range(ano_inicio, ano_fim + 1):
        periodos = "|".join(f"{ano}{str(m).zfill(2)}" for m in range(1, 13))
        url = (
            f"{BASE_URL}/{TABELA}/periodos/{periodos}/variaveis/2265"
            f"?localidades={localidade_info['cod']}&classificacao=660[{CATEGORIAS}]"
        )
        try:
            r = requests.get(url, timeout=90)
            r.raise_for_status()
            dados = r.json()
        except Exception as e:
            logger.warning(f"  Erro {capital} {ano}: {e}")
            continue

        for variavel in dados:
            for resultado in variavel.get("resultados", []):
                for classif in resultado.get("classificacoes", []):
                    if classif.get("id") == "660":
                        cat = classif.get("categoria", {})
                        if cat:
                            id_cat, nome_cat = next(iter(cat.items()))
                for serie_info in resultado.get("series", []):
                    for periodo, valor_str in serie_info.get("serie", {}).items():
                        valor = None
                        if valor_str not in ("...", "-", "***", "X"):
                            try:
                                valor = float(str(valor_str).replace(",", "."))
                            except (ValueError, TypeError):
                                pass
                        todos.append({
                            "periodo":    periodo,
                            "ano":        int(periodo[:4]),
                            "mes":        int(periodo[4:]),
                            "capital":    capital,
                            "estado":     localidade_info["estado"],
                            "regiao":     localidade_info["regiao"],
                            "id_categoria": id_cat,
                            "categoria":  nome_cat,
                            "variacao_mensal_pct": valor,
                        })
        time.sleep(1.0)

    return pd.DataFrame(todos) if todos else pd.DataFrame()


def main():
    logger.info("=" * 60)
    logger.info("  AgroClima Brasil — IPCA Regional por Capital (IBGE)")
    logger.info("=" * 60)

    if not verificar_api():
        logger.error(
            "\nIBGE SIDRA indisponivel no momento.\n"
            "Este script esta pronto — rode novamente quando o IBGE voltar.\n"
            "Enquanto isso, o projeto usa o IPCA nacional do BCB (bcb_ipca.py)."
        )
        raise SystemExit(1)

    todos = []
    for capital, info in LOCALIDADES.items():
        logger.info(f"Coletando {capital} ({info['estado']})...")
        df = coletar_capital(info, capital)
        if not df.empty:
            todos.append(df)
            logger.info(f"  -> {len(df):,} registros")
        time.sleep(0.5)

    if not todos:
        logger.error("Nenhum dado coletado.")
        raise SystemExit(1)

    df_final = (
        pd.concat(todos, ignore_index=True)
        .sort_values(["capital", "id_categoria", "periodo"])
        .reset_index(drop=True)
    )

    saida = OUTPUT_DIR / "ibge_ipca_regional.csv"
    df_final.to_csv(saida, index=False, encoding="utf-8")

    print(f"\n{'='*60}")
    print("  IPCA Regional — Resultado")
    print(f"{'='*60}")
    print(f"  Capitais: {df_final['capital'].nunique()}")
    print(f"  Registros: {len(df_final):,}")
    print(f"  Periodo: {df_final['periodo'].min()} a {df_final['periodo'].max()}")
    for cap, grp in df_final.groupby("capital"):
        media = grp["variacao_mensal_pct"].mean()
        print(f"  {cap:<16} {media:>5.2f}%/mes [{grp['regiao'].iloc[0]}]")
    print(f"  Salvo: {saida}")
    print(f"{'='*60}")
    logger.info("Coleta regional concluida.")


if __name__ == "__main__":
    main()
