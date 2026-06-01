"""
ETL — Limpeza, transformação e geração das tabelas do Data Warehouse
Entradas (preço): data/raw/bcb_ipca_alimentos.csv   ← fonte primária (BCB)
                  data/raw/ibge_ipca_alimentos.csv   ← fallback (IBGE SIDRA)
Entrada (clima) : data/raw/openmeteo_precipitacao.csv
Saídas  : data/processed/dim_tempo.csv
          data/processed/dim_produto.csv
          data/processed/dim_regiao.csv
          data/processed/fato_preco.csv
          data/processed/fato_clima.csv
          data/processed/fato_correlacao_base.csv

Uso:
  python src/etl/transformar.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

RAW_DIR  = Path("data/raw")
PROC_DIR = Path("data/processed")
PROC_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def salvar(df: pd.DataFrame, nome: str) -> None:
    caminho = PROC_DIR / nome
    df.to_csv(caminho, index=False, encoding="utf-8")
    logger.info(
        f"  Salvo: {nome:<35} {len(df):>8,} linhas  "
        f"({caminho.stat().st_size / 1024:.1f} KB)"
    )


# ── Dimensão Tempo ────────────────────────────────────────────────────────────

def criar_dim_tempo(ano_inicio: int = 2015, ano_fim: int = 2024) -> pd.DataFrame:
    periodos = pd.date_range(
        start=f"{ano_inicio}-01-01",
        end=f"{ano_fim}-12-31",
        freq="MS",
    )
    df = pd.DataFrame({
        "periodo":   periodos.strftime("%Y%m"),
        "data_ref":  periodos.strftime("%Y-%m-%d"),
        "ano":       periodos.year.astype("int16"),
        "mes":       periodos.month.astype("int16"),
        "trimestre": periodos.quarter.astype("int16"),
        "semestre":  ((periodos.month > 6).astype(int) + 1).astype("int16"),
        "nome_mes":  periodos.strftime("%B"),
    })
    return df


# ── Dimensão Produto ──────────────────────────────────────────────────────────

# Mapeamento id_categoria → (grupo, subgrupo)
# Inclui códigos IBGE (numéricos) e códigos BCB (strings)
_GRUPOS = {
    # ── Fonte BCB ──────────────────────────────────────────────
    "ipca_geral":   ("Indice Geral", "Geral"),
    "carnes":       ("Alimentos", "Carnes"),
    "aves_ovos":    ("Alimentos", "Aves e Ovos"),
    "leite":        ("Alimentos", "Laticinios"),
    "panificados":  ("Alimentos", "Panificados"),
    "cereais":      ("Alimentos", "Cereais"),
    "tuberculos":   ("Alimentos", "Tuberculos"),
    "horticultura": ("Alimentos", "Hortifruti"),
    "frutas":       ("Alimentos", "Frutas"),
    "acucares":     ("Alimentos", "Acucares"),
    "oleos":        ("Alimentos", "Oleos e Gorduras"),
    # ── Fonte IBGE SIDRA (fallback) ────────────────────────────
    "1104": ("Alimentos", "Agregado"),
    "1105": ("Alimentos", "Cereais"),
    "1107": ("Alimentos", "Carnes"),
    "1108": ("Alimentos", "Pescados"),
    "1109": ("Alimentos", "Aves e Ovos"),
    "1110": ("Alimentos", "Laticinios"),
    "1111": ("Alimentos", "Acucares"),
    "1112": ("Alimentos", "Oleos e Gorduras"),
    "1113": ("Alimentos", "Hortifruti"),
    "1114": ("Alimentos", "Tuberculos"),
    "1115": ("Alimentos", "Frutas"),
    "1116": ("Alimentos", "Panificados"),
    "1117": ("Bebidas",   "Bebidas"),
    "1118": ("Alimentos", "Processados"),
    "1119": ("Alimentos", "Condimentos"),
    "1120": ("Servicos",  "Alimentacao Fora"),
}


def criar_dim_produto(df_preco_raw: pd.DataFrame) -> pd.DataFrame:
    produtos = (
        df_preco_raw[["id_categoria", "categoria"]]
        .drop_duplicates()
        .rename(columns={"id_categoria": "id_produto", "categoria": "nome_produto"})
        .copy()
    )
    produtos["grupo"]    = produtos["id_produto"].map(lambda x: _GRUPOS.get(str(x), ("Outros", "Outros"))[0])
    produtos["subgrupo"] = produtos["id_produto"].map(lambda x: _GRUPOS.get(str(x), ("Outros", "Outros"))[1])
    return produtos.sort_values("id_produto").reset_index(drop=True)


# ── Dimensão Região ───────────────────────────────────────────────────────────

def criar_dim_regiao(df_clima_raw: pd.DataFrame) -> pd.DataFrame:
    regiao = (
        df_clima_raw[["estado", "regiao", "bioma", "cidade"]]
        .drop_duplicates()
        .sort_values("estado")
        .reset_index(drop=True)
    )
    regiao.insert(0, "id_regiao", range(1, len(regiao) + 1))
    return regiao


# ── Fato Preço ────────────────────────────────────────────────────────────────

def criar_fato_preco(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Pivota variáveis IBGE: variação mensal (2265) e número-índice (2266).
    Cada linha = 1 período × 1 produto com ambas as métricas.
    """
    df_raw = df_raw.copy()
    df_raw["id_variavel"] = df_raw["id_variavel"].astype(str)

    var_mensal = (
        df_raw[df_raw["id_variavel"] == "2265"]
        [["periodo", "id_categoria", "categoria", "valor"]]
        .rename(columns={"valor": "variacao_mensal_pct"})
    )
    var_indice = (
        df_raw[df_raw["id_variavel"] == "2266"]
        [["periodo", "id_categoria", "valor"]]
        .rename(columns={"valor": "numero_indice"})
    )

    df = var_mensal.merge(var_indice, on=["periodo", "id_categoria"], how="left")

    df["periodo"]             = df["periodo"].astype(str).str.zfill(6)
    df["variacao_mensal_pct"] = pd.to_numeric(df["variacao_mensal_pct"], errors="coerce")
    df["numero_indice"]       = pd.to_numeric(df["numero_indice"],       errors="coerce")
    df["ano"]                 = df["periodo"].str[:4].astype("int16")
    df["mes"]                 = df["periodo"].str[4:].astype("int16")

    return df.sort_values(["id_categoria", "periodo"]).reset_index(drop=True)


# ── Fato Clima ────────────────────────────────────────────────────────────────

def criar_fato_clima(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Enriquece os dados brutos de precipitação com:
    - Média histórica por estado/mês (baseline)
    - Anomalia percentual em relação à média
    - Classificação do evento climático
    """
    df = df_raw.copy()
    df["periodo"] = df["periodo"].astype(str).str.zfill(6)

    # Média histórica por estado+mês para calcular anomalia
    df["media_hist_mm"] = df.groupby(["estado", "mes"])["precipitacao_mm_total"].transform("mean")

    # Anomalia (%): quanto acima/abaixo da média histórica
    df["anomalia_pct"] = (
        (df["precipitacao_mm_total"] - df["media_hist_mm"])
        / df["media_hist_mm"].replace(0, np.nan)
        * 100
    ).round(2)

    # Classifica evento com base na anomalia
    def classificar(a):
        if pd.isna(a):
            return "desconhecido"
        if a < -60:
            return "seca_severa"
        if a < -30:
            return "seca_moderada"
        if a > 100:
            return "enchente_severa"
        if a > 50:
            return "chuva_intensa"
        return "normal"

    df["evento_climatico"] = df["anomalia_pct"].apply(classificar)

    return df.sort_values(["estado", "periodo"]).reset_index(drop=True)


# ── Fato Correlação Base ──────────────────────────────────────────────────────

def criar_fato_correlacao_base(
    fato_preco: pd.DataFrame,
    fato_clima: pd.DataFrame,
) -> pd.DataFrame:
    """
    Cria tabela desnormalizada para análise de correlação.
    Contém: variação de preço por produto + precipitação média de cada região
    com defasagem (lag) de 0, 1, 2, 3 e 6 meses.

    Por que defasagem? O impacto climático no preço não é imediato:
    a seca em março pode encarece o feijão em abril ou maio.
    Testar vários lags permite identificar o tempo de resposta de cada produto.
    """
    def agregar_precip_regiao(regiao: str, col: str) -> pd.DataFrame:
        sub = (
            fato_clima[fato_clima["regiao"] == regiao]
            .groupby("periodo")["precipitacao_mm_total"]
            .mean()
            .reset_index()
            .rename(columns={"precipitacao_mm_total": col})
            .sort_values("periodo")
            .reset_index(drop=True)
        )
        for lag in [1, 2, 3, 6]:
            sub[f"{col}_lag{lag}"] = sub[col].shift(lag)
        return sub

    clima_nordeste = agregar_precip_regiao("Nordeste", "precip_nordeste_mm")
    clima_sul      = agregar_precip_regiao("Sul",      "precip_sul_mm")
    clima = clima_nordeste.merge(clima_sul, on="periodo", how="outer")

    # Usa apenas variação mensal (não o índice)
    preco = (
        fato_preco[["periodo", "id_categoria", "categoria", "variacao_mensal_pct"]]
        .dropna(subset=["variacao_mensal_pct"])
        .copy()
    )

    df = preco.merge(clima, on="periodo", how="inner")
    df["ano"] = df["periodo"].str[:4].astype("int16")
    df["mes"] = df["periodo"].str[4:].astype("int16")

    return df.sort_values(["id_categoria", "periodo"]).reset_index(drop=True)


# ── Relatório de qualidade ────────────────────────────────────────────────────

def relatorio_qualidade(dfs: dict) -> None:
    print(f"\n{'='*60}")
    print("  Relatório de qualidade dos dados processados")
    print(f"{'='*60}")
    for nome, df in dfs.items():
        nulos = df.isnull().sum().sum()
        total = df.size
        print(
            f"  {nome:<35} {len(df):>7,} linhas  "
            f"nulos: {nulos:>5} ({nulos/total*100:.1f}%)"
        )
    print(f"{'='*60}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 55)
    logger.info("  AgroClima Brasil — ETL")
    logger.info("=" * 55)

    # ── 1. Detecta fonte de dados de preço ────────────────────
    # Tenta BCB primeiro (mais estável); fallback para IBGE SIDRA
    arq_bcb  = RAW_DIR / "bcb_ipca_alimentos.csv"
    arq_ibge = RAW_DIR / "ibge_ipca_alimentos.csv"
    arq_clima = RAW_DIR / "openmeteo_precipitacao.csv"

    if arq_bcb.exists():
        arq_preco  = arq_bcb
        fonte_preco = "BCB"
    elif arq_ibge.exists():
        arq_preco  = arq_ibge
        fonte_preco = "IBGE SIDRA"
    else:
        logger.error(
            "Nenhum arquivo de preco encontrado. Execute um dos scripts de coleta:\n"
            "  python src/coleta/bcb_ipca.py          (recomendado)\n"
            "  python src/coleta/ibge_ipca.py          (alternativo)"
        )
        raise SystemExit(1)

    if not arq_clima.exists():
        logger.error(
            f"Arquivo climatico nao encontrado: {arq_clima}\n"
            "  Execute: python src/coleta/openmeteo_precipitacao.py"
        )
        raise SystemExit(1)

    # ── 2. Leitura dos dados brutos ────────────────────────────
    logger.info("Carregando dados brutos...")
    df_preco_raw = pd.read_csv(arq_preco, dtype={"periodo": str})
    df_clima_raw = pd.read_csv(arq_clima, dtype={"periodo": str})
    logger.info(f"  Preco ({fonte_preco}): {len(df_preco_raw):,} linhas ({arq_preco.name})")
    logger.info(f"  Clima (Open-Meteo) : {len(df_clima_raw):,} linhas")

    # ── 3. Dimensões ───────────────────────────────────────────
    logger.info("\nCriando dimensões...")
    dim_tempo   = criar_dim_tempo()
    dim_produto = criar_dim_produto(df_preco_raw)
    dim_regiao  = criar_dim_regiao(df_clima_raw)
    logger.info(f"  dim_tempo   : {len(dim_tempo)} períodos")
    logger.info(f"  dim_produto : {len(dim_produto)} produtos")
    logger.info(f"  dim_regiao  : {len(dim_regiao)} localidades")

    # ── 4. Tabelas fato ────────────────────────────────────────
    logger.info("\nCriando tabelas fato...")
    fato_preco = criar_fato_preco(df_preco_raw)
    fato_clima = criar_fato_clima(df_clima_raw)
    fato_corr  = criar_fato_correlacao_base(fato_preco, fato_clima)
    logger.info(f"  fato_preco  : {len(fato_preco):,} linhas | {fato_preco['id_categoria'].nunique()} produtos")
    logger.info(f"  fato_clima  : {len(fato_clima):,} linhas | {fato_clima['estado'].nunique()} estados")
    logger.info(f"  fato_corr   : {len(fato_corr):,} linhas | {fato_corr['id_categoria'].nunique()} produtos")

    # ── 5. Persistência ────────────────────────────────────────
    logger.info("\nSalvando arquivos processados...")
    salvar(dim_tempo,   "dim_tempo.csv")
    salvar(dim_produto, "dim_produto.csv")
    salvar(dim_regiao,  "dim_regiao.csv")
    salvar(fato_preco,  "fato_preco.csv")
    salvar(fato_clima,  "fato_clima.csv")
    salvar(fato_corr,   "fato_correlacao_base.csv")

    # ── 6. Qualidade ───────────────────────────────────────────
    relatorio_qualidade({
        "dim_tempo":           dim_tempo,
        "dim_produto":         dim_produto,
        "fato_preco":          fato_preco,
        "fato_clima":          fato_clima,
        "fato_correlacao_base":fato_corr,
    })

    logger.info("ETL concluído.")


if __name__ == "__main__":
    main()
