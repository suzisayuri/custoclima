"""
Análise de correlação entre precipitação e variação de preço de alimentos
Entrada : data/processed/fato_correlacao_base.csv
Saídas  : data/processed/correlacao_resultados.csv  ← resultados numéricos
          plots/heatmap_nordeste.png                 ← heatmap produto × lag
          plots/heatmap_sul.png
          plots/serie_<id>_<regiao>.png              ← séries dos top-5 produtos

Conceito de lag (defasagem):
  lag0 = correlação com precipitação no mesmo mês
  lag1 = preço de hoje × precipitação de 1 mês atrás
  lag3 = preço de hoje × precipitação de 3 meses atrás  (plantio → colheita)
  lag6 = preço de hoje × precipitação de 6 meses atrás  (impacto tardio, estoque)

Uso:
  python src/analise/correlacao.py
"""

import sys
import io
import warnings
import logging

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

import matplotlib
matplotlib.use("Agg")  # sem interface gráfica (compatível com servidores)
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore", category=RuntimeWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PROC_DIR = Path("data/processed")
PLOT_DIR = Path("plots")
PLOT_DIR.mkdir(parents=True, exist_ok=True)

# Mínimo de pares para aceitar uma correlação como válida
MIN_AMOSTRAS = 12


# ── Cálculo de correlações ────────────────────────────────────────────────────

def correlacao_com_lag(
    df_produto: pd.DataFrame,
    col_preco: str,
    col_precip: str,
) -> list[dict]:
    """
    Calcula correlação de Pearson entre variação de preço e precipitação
    para lag 0, 1, 2, 3 e 6 meses. Retorna lista de dicionários.
    """
    resultados = []
    for lag in [0, 1, 2, 3, 6]:
        col = col_precip if lag == 0 else f"{col_precip}_lag{lag}"
        if col not in df_produto.columns:
            continue

        pares = df_produto[[col_preco, col]].dropna()
        if len(pares) < MIN_AMOSTRAS:
            continue

        r, p = stats.pearsonr(pares[col_preco], pares[col])
        resultados.append({
            "lag":           lag,
            "r_pearson":     round(r, 4),
            "p_valor":       round(p, 4),
            "n_amostras":    len(pares),
            "significativo": p < 0.05,
        })
    return resultados


def calcular_todas_correlacoes(df: pd.DataFrame) -> pd.DataFrame:
    """Itera sobre produtos e regiões, gera tabela completa de correlações."""
    regioes_colunas = {
        "Nordeste": "precip_nordeste_mm",
        "Sul":      "precip_sul_mm",
    }
    registros = []

    for id_prod in df["id_categoria"].unique():
        df_prod = df[df["id_categoria"] == id_prod]
        nome    = df_prod["categoria"].iloc[0]

        for regiao, col_precip in regioes_colunas.items():
            if col_precip not in df.columns:
                continue

            for r in correlacao_com_lag(df_prod, "variacao_mensal_pct", col_precip):
                registros.append({
                    "id_produto": id_prod,
                    "produto":    nome,
                    "regiao":     regiao,
                    **r,
                })

    return pd.DataFrame(registros)


def top_produtos_sensiveis(df_corr: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Filtra os N produtos com maior |r| e p < 0.05."""
    return (
        df_corr[df_corr["significativo"]]
        .assign(r_abs=lambda x: x["r_pearson"].abs())
        .sort_values("r_abs", ascending=False)
        .drop_duplicates(subset=["produto", "regiao"])
        .head(n)
        .drop(columns="r_abs")
        .reset_index(drop=True)
    )


# ── Visualizações ─────────────────────────────────────────────────────────────

def plotar_heatmap(df_corr: pd.DataFrame, regiao: str) -> None:
    """
    Heatmap produtos (linhas) × lag (colunas) com r de Pearson.
    Vermelho = correlação positiva (chuva sobe preço).
    Azul = correlação negativa (chuva baixa preço).
    """
    sub = df_corr[df_corr["regiao"] == regiao].copy()
    if sub.empty:
        logger.warning(f"Sem dados para heatmap {regiao}.")
        return

    # Seleciona os 20 produtos com maior variação de |r| para caber no gráfico
    top_prods = (
        sub.assign(r_abs=lambda x: x["r_pearson"].abs())
        .groupby("produto")["r_abs"].max()
        .nlargest(20)
        .index
    )
    pivot = sub[sub["produto"].isin(top_prods)].pivot_table(
        index="produto", columns="lag", values="r_pearson", aggfunc="mean"
    )
    pivot.columns = [f"lag{c}" for c in pivot.columns]

    fig, ax = plt.subplots(figsize=(10, max(5, len(pivot) * 0.45)))
    sns.heatmap(
        pivot,
        annot=True, fmt=".2f",
        cmap="RdBu_r", center=0, vmin=-1, vmax=1,
        linewidths=0.5,
        cbar_kws={"label": "r de Pearson", "shrink": 0.8},
        ax=ax,
    )
    ax.set_title(
        f"Correlação Preço × Precipitação — {regiao}  (2015–2024)\n"
        "Vermelho = chuva eleva preço  |  Azul = chuva reduz preço",
        fontsize=11, pad=12,
    )
    ax.set_xlabel("Defasagem (meses)", fontsize=10)
    ax.set_ylabel("Produto IBGE", fontsize=10)
    plt.tight_layout()

    caminho = PLOT_DIR / f"heatmap_{regiao.lower()}.png"
    fig.savefig(caminho, dpi=130, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Gráfico salvo: {caminho}")


def plotar_serie_temporal(
    df: pd.DataFrame, id_produto: str, regiao: str
) -> None:
    """
    Eixo duplo: variação de preço (vermelho) e precipitação (azul).
    Permite visualizar a defasagem visualmente antes de confiar nos números.
    """
    col_precip = f"precip_{regiao.lower()}_mm"
    if col_precip not in df.columns:
        return

    df_prod = df[df["id_categoria"] == id_produto].sort_values("periodo").copy()
    if len(df_prod) < MIN_AMOSTRAS:
        return

    nome  = df_prod["categoria"].iloc[0][:45]
    datas = pd.to_datetime(df_prod["periodo"].astype(str), format="%Y%m")

    fig, ax1 = plt.subplots(figsize=(14, 5))

    cor_preco  = "#c0392b"
    cor_precip = "#2980b9"

    ax1.plot(datas, df_prod["variacao_mensal_pct"],
             color=cor_preco, linewidth=1.5, label="Variação preço (%)")
    ax1.axhline(0, color=cor_preco, linestyle="--", linewidth=0.5, alpha=0.4)
    ax1.set_ylabel("Variação mensal do preço (%)", color=cor_preco, fontsize=10)
    ax1.tick_params(axis="y", labelcolor=cor_preco)

    ax2 = ax1.twinx()
    ax2.fill_between(datas, df_prod[col_precip], alpha=0.2, color=cor_precip)
    ax2.plot(datas, df_prod[col_precip],
             color=cor_precip, linewidth=1.2, label=f"Precipitação {regiao} (mm/mês)")
    ax2.set_ylabel(f"Precipitação {regiao} (mm/mês)", color=cor_precip, fontsize=10)
    ax2.tick_params(axis="y", labelcolor=cor_precip)

    ax1.set_title(f"{nome}  ×  Precipitação {regiao} — 2015–2024", fontsize=12)
    ax1.set_xlabel("Mês/Ano", fontsize=10)

    linhas  = ax1.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    rotulos = ax1.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
    ax1.legend(linhas, rotulos, loc="upper left", fontsize=9, framealpha=0.8)

    plt.tight_layout()
    caminho = PLOT_DIR / f"serie_{id_produto}_{regiao.lower()}.png"
    fig.savefig(caminho, dpi=130, bbox_inches="tight")
    plt.close(fig)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 55)
    logger.info("  AgroClima Brasil — Análise de Correlação")
    logger.info("=" * 55)

    arq = PROC_DIR / "fato_correlacao_base.csv"
    if not arq.exists():
        logger.error(
            f"Arquivo não encontrado: {arq}\n"
            "Execute src/etl/transformar.py antes desta análise."
        )
        raise SystemExit(1)

    df = pd.read_csv(arq, dtype={"periodo": str, "id_categoria": str})
    logger.info(f"Carregados: {len(df):,} linhas | {df['id_categoria'].nunique()} produtos")

    # ── 1. Calcula correlações ───────────────────────────────────
    logger.info("Calculando correlações (todos produtos × regiões × lags)...")
    df_corr = calcular_todas_correlacoes(df)

    saida = PROC_DIR / "correlacao_resultados.csv"
    df_corr.to_csv(saida, index=False, encoding="utf-8")
    logger.info(f"Resultados salvos: {saida} ({len(df_corr):,} combinações)")

    # ── 2. Produtos mais sensíveis ───────────────────────────────
    sensiveis = top_produtos_sensiveis(df_corr)
    print(f"\n{'='*72}")
    print("  Top produtos mais sensíveis a variações climáticas (p < 0.05)")
    print(f"{'='*72}")
    if not sensiveis.empty:
        for _, row in sensiveis.iterrows():
            direcao = "+chuva -> +preco" if row["r_pearson"] > 0 else "+chuva -> -preco"
            print(
                f"  {row['produto'][:35]:<35} | {row['regiao']:<9} | "
                f"lag{row['lag']} | r={row['r_pearson']:>+.3f} | "
                f"p={row['p_valor']:.3f} | {direcao}"
            )
    else:
        print("  Nenhuma correlação significativa encontrada com os dados atuais.")
        print("  Execute a coleta e o ETL para obter dados reais.")
    print(f"{'='*72}")

    # ── 3. Heatmaps ─────────────────────────────────────────────
    logger.info("Gerando heatmaps...")
    plotar_heatmap(df_corr, "Nordeste")
    plotar_heatmap(df_corr, "Sul")

    # ── 4. Séries temporais dos 5 produtos mais sensíveis ────────
    logger.info("Gerando séries temporais dos produtos mais sensíveis...")
    top5_ids = (
        df_corr[df_corr["significativo"]]
        .assign(r_abs=lambda x: x["r_pearson"].abs())
        .sort_values("r_abs", ascending=False)
        .drop_duplicates(subset=["id_produto"])
        .head(5)["id_produto"]
        .tolist()
    )

    for id_prod in top5_ids:
        for regiao in ["Nordeste", "Sul"]:
            plotar_serie_temporal(df, id_prod, regiao)

    n_plots = len(list(PLOT_DIR.glob("*.png")))
    logger.info(f"Gráficos salvos em plots/ ({n_plots} arquivo(s))")
    logger.info("Análise concluída.")


if __name__ == "__main__":
    main()
