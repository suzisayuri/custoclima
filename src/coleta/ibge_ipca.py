"""
Coleta de dados IPCA via API SIDRA do IBGE — Projeto AgroClima Brasil
Fonte  : https://servicodados.ibge.gov.br/api/v3/
Tabela : 7060 — IPCA variação mensal por grupo/subgrupo/item (base 2019=100)
Saída  : data/raw/ibge_ipca_completo.csv
         data/raw/ibge_ipca_alimentos.csv

Variáveis coletadas:
  2265 = variação % mensal
  2266 = número-índice (2019=100)

Uso:
  python src/coleta/ibge_ipca.py
"""

import requests
import pandas as pd
from pathlib import Path
import time
import logging
from typing import Optional

# ============================================================
# CONFIGURAÇÃO
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://servicodados.ibge.gov.br/api/v3/agregados"
TABELA_IPCA = 7060
VARIAVEIS = "2265|2266"

# Pausa entre requisições para não sobrecarregar a API do IBGE
PAUSA_SEGUNDOS = 1.5

# Termos usados para identificar categorias alimentares no filtro final
TERMOS_ALIMENTARES = [
    "alimenta", "bebida", "carne", "aves", "peixe", "frango",
    "leite", "queijo", "manteiga", "arroz", "feijão", "farinha",
    "pão", "açúcar", "óleo", "gordura", "verdura", "legume",
    "fruta", "horticultura", "tomate", "batata", "cebola",
    "cereal", "trigo", "milho", "café", "refrigerante",
]


# ============================================================
# METADADOS
# ============================================================

def verificar_disponibilidade() -> bool:
    """
    Verifica se a API SIDRA está respondendo usando uma consulta mínima de dados
    (1 mês, 1 variável, 1 categoria). Mais confiável do que chamar metadados.
    """
    url = (
        f"{BASE_URL}/{TABELA_IPCA}/periodos/202401/variaveis/2265"
        f"?localidades=N1[1]&classificacao=660[7169]"
    )
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            logger.info("API IBGE SIDRA OK — respondendo normalmente.")
            return True
        if resp.status_code == 500:
            logger.warning(
                f"API IBGE SIDRA retornou HTTP 500 (instabilidade temporária). "
                "Tentando coletar mesmo assim — os dados podem funcionar por ano completo."
            )
            return True  # Prossegue; o erro pode ser só na consulta de verificação
        resp.raise_for_status()
        return True
    except requests.exceptions.ConnectionError:
        logger.error("Sem conexão com a internet ou API fora do ar.")
        return False
    except Exception as e:
        logger.warning(f"Verificação falhou ({e}) — tentando coletar mesmo assim.")
        return True


# ============================================================
# COLETA
# ============================================================

def coletar_ipca_ano(ano: int, tentativas: int = 3) -> Optional[list]:
    """
    Faz requisição à API SIDRA para todos os 12 meses de um ano.
    Tenta até `tentativas` vezes em caso de erro 500 (instabilidade do IBGE).

    Parâmetros da URL:
      classificacao=660[all]  → todos os grupos/subgrupos/itens do IPCA
      localidades=N1[1]       → Brasil (nível nacional agregado)
    """
    periodos = "|".join(f"{ano}{str(m).zfill(2)}" for m in range(1, 13))

    url = (
        f"{BASE_URL}/{TABELA_IPCA}/periodos/{periodos}"
        f"/variaveis/{VARIAVEIS}"
        f"?localidades=N1[1]&classificacao=660[all]"
    )

    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.get(url, timeout=90)

            if resp.status_code == 500 and tentativa < tentativas:
                espera = tentativa * 5
                logger.warning(
                    f"  HTTP 500 para {ano} (tentativa {tentativa}/{tentativas}). "
                    f"Aguardando {espera}s..."
                )
                time.sleep(espera)
                continue

            resp.raise_for_status()
            return resp.json()

        except requests.exceptions.Timeout:
            if tentativa < tentativas:
                logger.warning(f"  Timeout {ano} (tentativa {tentativa}). Retentando...")
                time.sleep(tentativa * 3)
            else:
                logger.error(f"Timeout definitivo ao coletar {ano}.")
                return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"Erro HTTP ao coletar {ano}: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de rede ao coletar {ano}: {e}")
            return None

    logger.error(f"Falhou após {tentativas} tentativas para {ano}.")
    return None


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def normalizar_json_sidra(dados_json: list, ano: int) -> pd.DataFrame:
    """
    Transforma a resposta aninhada da API SIDRA v3 num DataFrame plano.

    Estrutura esperada da resposta:
    [
      {
        "id": "2265",
        "variavel": "IPCA - Variação mensal",
        "unidade": "%",
        "resultados": [
          {
            "classificacoes": [
              {"id": "660", "categoria": {"7169": "Índice geral"}}
            ],
            "series": [
              {"localidade": {"nome": "Brasil"}, "serie": {"201501": "0.71", ...}}
            ]
          },
          ...  (um resultado por categoria)
        ]
      },
      ...  (uma entrada por variável solicitada)
    ]
    """
    registros = []

    for variavel_obj in dados_json:
        id_variavel = variavel_obj.get("id", "")
        nome_variavel = variavel_obj.get("variavel", "")
        unidade = variavel_obj.get("unidade", "")

        for resultado in variavel_obj.get("resultados", []):
            # Extrai código e nome da categoria dentro da classificação 660
            id_categoria = "0"
            nome_categoria = "N/A"

            for classif in resultado.get("classificacoes", []):
                if classif.get("id") == "660":
                    cat_dict = classif.get("categoria", {})
                    if cat_dict:
                        id_categoria, nome_categoria = next(iter(cat_dict.items()))
                    break

            # Cada item em "series" corresponde a uma localidade
            for serie_info in resultado.get("series", []):
                serie = serie_info.get("serie", {})

                for periodo, valor_str in serie.items():
                    # IBGE usa "..." para dado não disponível e "-" para não aplicável
                    valor = None
                    if valor_str not in ("...", "-", "***", "X"):
                        try:
                            valor = float(str(valor_str).replace(",", "."))
                        except (ValueError, TypeError):
                            valor = None

                    registros.append({
                        "periodo": periodo,          # formato YYYYMM
                        "ano": int(periodo[:4]),
                        "mes": int(periodo[4:]),
                        "id_variavel": id_variavel,
                        "variavel": nome_variavel,
                        "unidade": unidade,
                        "id_categoria": id_categoria,
                        "categoria": nome_categoria,
                        "valor": valor,
                    })

    return pd.DataFrame(registros)


# ============================================================
# ORQUESTRAÇÃO
# ============================================================

def coletar_todos_anos(ano_inicio: int = 2015, ano_fim: int = 2024) -> pd.DataFrame:
    """
    Coleta IPCA para todos os anos do intervalo especificado.
    Uma requisição por ano para evitar timeout e URLs muito longas.
    """
    todos_dados = []
    anos = list(range(ano_inicio, ano_fim + 1))

    for i, ano in enumerate(anos, 1):
        logger.info(f"[{i}/{len(anos)}] Coletando {ano}...")

        dados_json = coletar_ipca_ano(ano)

        if dados_json is None:
            logger.warning(f"  → Ano {ano} ignorado por erro na coleta.")
            continue

        df_ano = normalizar_json_sidra(dados_json, ano)

        if df_ano.empty:
            logger.warning(f"  → Nenhum registro retornado para {ano}.")
        else:
            todos_dados.append(df_ano)
            logger.info(f"  → {len(df_ano):,} registros | {df_ano['id_categoria'].nunique()} categorias")

        # Pausa entre anos para não sobrecarregar a API
        if i < len(anos):
            time.sleep(PAUSA_SEGUNDOS)

    if not todos_dados:
        logger.error("Nenhum dado coletado. Verifique conexão e tente novamente.")
        return pd.DataFrame()

    return pd.concat(todos_dados, ignore_index=True)


def filtrar_alimentos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra linhas cujas categorias estão relacionadas a alimentos e bebidas.
    Usa os termos definidos em TERMOS_ALIMENTARES (busca parcial, sem distinção maiúscula).
    """
    mascara = df["categoria"].str.lower().str.contains(
        "|".join(TERMOS_ALIMENTARES), na=False, regex=True
    )
    df_alimentos = df[mascara].copy()
    logger.info(
        f"Filtro alimentar: {len(df_alimentos):,} de {len(df):,} registros "
        f"({len(df_alimentos)/len(df)*100:.1f}%)"
    )
    return df_alimentos


def salvar_csv(df: pd.DataFrame, nome_arquivo: str) -> Path:
    """Salva DataFrame em CSV UTF-8 na pasta de saída."""
    caminho = OUTPUT_DIR / nome_arquivo
    df.to_csv(caminho, index=False, encoding="utf-8")
    logger.info(f"Salvo: {caminho} ({caminho.stat().st_size / 1024:.1f} KB)")
    return caminho


def imprimir_resumo(df: pd.DataFrame, titulo: str) -> None:
    """Exibe estatísticas básicas do DataFrame coletado."""
    separador = "=" * 55
    print(f"\n{separador}")
    print(f"  {titulo}")
    print(separador)

    if df.empty:
        print("  VAZIO — nenhum dado disponível.")
        print(separador)
        return

    print(f"  Registros totais : {len(df):,}")
    print(f"  Período          : {df['periodo'].min()} → {df['periodo'].max()}")
    print(f"  Anos distintos   : {df['ano'].nunique()}")
    print(f"  Categorias únicas: {df['id_categoria'].nunique()}")
    print(f"  Variáveis        : {', '.join(df['variavel'].unique())}")
    nulos = df['valor'].isna().sum()
    print(f"  Valores ausentes : {nulos:,} ({nulos/len(df)*100:.1f}%)")

    print(f"\n  Top 5 categorias por registros:")
    top5 = df.groupby("categoria").size().sort_values(ascending=False).head(5)
    for cat, n in top5.items():
        print(f"    {cat[:42]:<42} {n:>5}")

    print(separador)


# ============================================================
# PONTO DE ENTRADA
# ============================================================

if __name__ == "__main__":
    logger.info("=" * 55)
    logger.info("  AgroClima Brasil — Coleta IBGE IPCA")
    logger.info("=" * 55)

    # 1. Verifica se a API está acessível
    if not verificar_disponibilidade():
        logger.error("API inacessível. Encerrando.")
        raise SystemExit(1)

    # 2. Coleta dados ano a ano (2015–2024)
    df_completo = coletar_todos_anos(ano_inicio=2015, ano_fim=2024)

    if df_completo.empty:
        raise SystemExit(1)

    # 3. Filtra categorias alimentares para análise focada
    df_alimentos = filtrar_alimentos(df_completo)

    # 4. Salva ambos os datasets
    salvar_csv(df_completo, "ibge_ipca_completo.csv")
    salvar_csv(df_alimentos, "ibge_ipca_alimentos.csv")

    # 5. Imprime resumo
    imprimir_resumo(df_completo, "IPCA — Todos os grupos")
    imprimir_resumo(df_alimentos, "IPCA — Alimentos e Bebidas")

    logger.info("Coleta finalizada.")
