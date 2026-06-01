"""
Correlação entre NDVI (saúde da vegetação via satélite NASA) e preço de alimentos
Entrada : data/raw/nasa_ndvi_regioes.csv
          data/processed/fato_preco.csv
Saída   : data/processed/correlacao_ndvi.csv
          plots/ndvi_vs_preco_*.png
          plots/ndvi_comparacao_sinais.png

Hipótese central:
  NDVI cai ANTES do preço subir. O satélite "vê" a lavoura morrendo
  semanas antes de a escassez chegar ao supermercado.
  Se a correlação NDVI→preço for mais forte que precipitação→preço,
  o NDVI é um sinal melhor para o modelo de alertas.

Uso:
  python src/analise/correlacao_ndvi.py
"""

import sys
import io
import warnings
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PROC_DIR = Path("data/processed")
RAW_DIR  = Path("data/raw")
PLOT_DIR = Path("plots")
PLOT_DIR.mkdir(parents=True, exist_ok=True)

MIN_AMOSTRAS = 12


# ── Correlação NDVI → Preço ───────────────────────────────────────────────────

def periodo_mais_lag(periodo: str, lag: int) -> str:
    ano = int(periodo[:4])
    mes = int(periodo[4:]) + lag
    ano += (mes - 1) // 12
    mes  = ((mes - 1) % 12) + 1
    return f"{ano}{str(mes).zfill(2)}"


def calcular_correlacoes_ndvi(
    df_ndvi: pd.DataFrame,
    df_preco: pd.DataFrame,
) -> pd.DataFrame:
    """
    Para cada produto e cada lag (0-6 meses), calcula a correlação
    entre NDVI médio regional e variação de preço.

    Sinal esperado: NDVI negativo com preço (NDVI cai → preço sobe → r < 0)
    Nordeste deve ter correlação mais forte que Sul.
    """
    # Índice NDVI médio por região e período
    ndvi_reg = df_ndvi.set_index(["periodo", "regiao"])["ndvi_medio_regiao"].to_dict()

    # Índice de preço por produto e período
    preco_idx = df_preco.set_index(["periodo", "id_produto"])["variacao_mensal_pct"].to_dict()
    produtos  = df_preco["id_produto"].unique()

    resultados = []

    for regiao in ["Nordeste", "Sul"]:
        # Série temporal de NDVI para esta região
        periodos_ndvi = sorted({p for p, r in ndvi_reg.keys() if r == regiao})

        for id_prod in produtos:
            nome = df_preco[df_preco["id_produto"] == id_prod]["categoria"].iloc[0]

            for lag in range(0, 7):
                pares_ndvi  = []
                pares_preco = []

                for periodo_t in periodos_ndvi:
                    ndvi_val  = ndvi_reg.get((periodo_t, regiao))
                    periodo_alvo = periodo_mais_lag(periodo_t, lag)
                    preco_val = preco_idx.get((periodo_alvo, id_prod))

                    if ndvi_val is not None and preco_val is not None:
                        if not np.isnan(ndvi_val) and not np.isnan(preco_val):
                            pares_ndvi.append(ndvi_val)
                            pares_preco.append(preco_val)

                if len(pares_ndvi) < MIN_AMOSTRAS:
                    continue

                r, p = stats.pearsonr(pares_preco, pares_ndvi)
                resultados.append({
                    "id_produto":    id_prod,
                    "produto":       nome,
                    "regiao":        regiao,
                    "lag_meses":     lag,
                    "r_ndvi_preco":  round(r, 4),
                    "p_valor":       round(p, 4),
                    "n_amostras":    len(pares_ndvi),
                    "significativo": p < 0.05,
                })

    return pd.DataFrame(resultados)


def comparar_sinais(
    df_ndvi_corr: pd.DataFrame,
    df_precip_corr: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compara a força do sinal NDVI vs precipitação para cada produto.
    Responde: qual é o melhor preditor de preço — NDVI ou chuva?
    """
    # Melhor lag por produto/região para NDVI
    best_ndvi = (
        df_ndvi_corr[df_ndvi_corr["significativo"]]
        .assign(r_abs=lambda x: x["r_ndvi_preco"].abs())
        .sort_values("r_abs", ascending=False)
        .drop_duplicates(subset=["id_produto", "regiao"])
        [["id_produto", "produto", "regiao", "lag_meses", "r_ndvi_preco", "r_abs"]]
        .rename(columns={"lag_meses": "lag_ndvi", "r_ndvi_preco": "r_ndvi",
                         "r_abs": "r_abs_ndvi"})
    )

    # Melhor lag por produto/região para precipitação
    col_r = "r_pearson" if "r_pearson" in df_precip_corr.columns else "r_ndvi_preco"
    col_lag = "defasagem_meses" if "defasagem_meses" in df_precip_corr.columns else "lag_meses"

    best_precip = (
        df_precip_corr[df_precip_corr["significativo"].astype(bool)]
        .assign(r_abs=lambda x: x[col_r].abs())
        .sort_values("r_abs", ascending=False)
        .drop_duplicates(subset=["id_produto", "regiao"])
        [[col_lag, "id_produto", "regiao", col_r, "r_abs"]]
        .rename(columns={col_lag: "lag_precip", col_r: "r_precip",
                         "r_abs": "r_abs_precip"})
    )

    comp = best_ndvi.merge(best_precip, on=["id_produto", "regiao"], how="outer")
    comp["melhor_sinal"] = comp.apply(
        lambda row: "NDVI" if row.get("r_abs_ndvi", 0) > row.get("r_abs_precip", 0)
        else "Precipitacao",
        axis=1,
    )
    comp["ganho_ndvi"] = (comp["r_abs_ndvi"] - comp["r_abs_precip"]).round(4)
    return comp.sort_values("r_abs_ndvi", ascending=False)


# ── Visualizações ─────────────────────────────────────────────────────────────

def plotar_ndvi_serie(
    df_ndvi: pd.DataFrame,
    df_preco: pd.DataFrame,
    id_produto: str,
    regiao: str,
) -> None:
    """Série dupla: NDVI (verde) e variação de preço (vermelho) com eixos separados."""
    col_ndvi = "ndvi_medio_regiao"
    sub_ndvi = df_ndvi[df_ndvi["regiao"] == regiao].sort_values("periodo").copy()
    sub_prec = df_preco[
        (df_preco["id_produto"] == id_produto)
    ].sort_values("periodo").copy()

    merged = sub_ndvi.merge(
        sub_prec[["periodo", "variacao_mensal_pct"]],
        on="periodo", how="inner"
    ).dropna()

    if len(merged) < 12:
        return

    nome   = df_preco[df_preco["id_produto"] == id_produto]["categoria"].iloc[0]
    datas  = pd.to_datetime(merged["periodo"].astype(str), format="%Y%m")

    fig, ax1 = plt.subplots(figsize=(14, 5))

    # NDVI — verde
    ax1.fill_between(datas, merged[col_ndvi], 0.2, alpha=0.2, color="#27ae60")
    ax1.plot(datas, merged[col_ndvi], color="#27ae60", linewidth=1.8,
             label="NDVI (saude da vegetacao)")
    ax1.axhline(0.3, color="#27ae60", linewidth=0.6, linestyle="--", alpha=0.5)
    ax1.set_ylabel("NDVI (0=seco, 1=verde)", color="#27ae60", fontsize=10)
    ax1.tick_params(axis="y", labelcolor="#27ae60")
    ax1.set_ylim(0, 0.8)

    # Preço — vermelho
    ax2 = ax1.twinx()
    ax2.bar(datas, merged["variacao_mensal_pct"],
            width=20, alpha=0.5, color="#e74c3c", label="Variacao preco (%)")
    ax2.axhline(0, color="#e74c3c", linewidth=0.6, linestyle="--", alpha=0.4)
    ax2.set_ylabel("Variacao mensal do preco (%)", color="#e74c3c", fontsize=10)
    ax2.tick_params(axis="y", labelcolor="#e74c3c")

    ax1.set_title(
        f"NDVI (NASA/MODIS) x Preco: {nome[:45]} | {regiao}\n"
        "Quando NDVI cai (verde some), o preco tende a subir nos meses seguintes",
        fontsize=11,
    )
    ax1.set_xlabel("Periodo")

    linhas = ax1.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    labels = ax1.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
    ax1.legend(linhas, labels, loc="upper left", fontsize=9)

    plt.tight_layout()
    nome_arq = f"ndvi_vs_preco_{id_produto}_{regiao.lower()}.png"
    fig.savefig(PLOT_DIR / nome_arq, dpi=130, bbox_inches="tight")
    plt.close(fig)


def plotar_comparacao_sinais(df_comp: pd.DataFrame) -> None:
    """Scatter: força do sinal NDVI vs precipitação. Pontos acima da diagonal = NDVI vence."""
    sub = df_comp.dropna(subset=["r_abs_ndvi", "r_abs_precip"])
    if sub.empty:
        return

    fig, ax = plt.subplots(figsize=(8, 7))

    cores = {"Nordeste": "#e74c3c", "Sul": "#3498db"}
    for regiao, grp in sub.groupby("regiao"):
        ax.scatter(
            grp["r_abs_precip"], grp["r_abs_ndvi"],
            c=cores.get(regiao, "gray"), s=80, alpha=0.8,
            label=regiao, zorder=3,
        )
        for _, row in grp.iterrows():
            ax.annotate(
                row["produto"].replace("IPCA - ", "")[:18],
                (row["r_abs_precip"], row["r_abs_ndvi"]),
                fontsize=7, alpha=0.8,
                xytext=(4, 4), textcoords="offset points",
            )

    lim = max(sub["r_abs_precip"].max(), sub["r_abs_ndvi"].max()) + 0.05
    ax.plot([0, lim], [0, lim], "k--", linewidth=1, alpha=0.4, label="Igual")
    ax.fill_between([0, lim], [0, lim], [lim, lim], alpha=0.05, color="green",
                    label="NDVI mais forte")
    ax.fill_between([0, lim], [0, 0], [0, lim], alpha=0.05, color="orange",
                    label="Precipitacao mais forte")

    ax.set_xlabel("|r| Precipitacao → Preco", fontsize=11)
    ax.set_ylabel("|r| NDVI → Preco",         fontsize=11)
    ax.set_title(
        "NDVI vs Precipitacao como preditor de preco\n"
        "Acima da diagonal = NDVI e sinal mais forte",
        fontsize=11,
    )
    ax.legend(fontsize=9)
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    plt.tight_layout()

    caminho = PLOT_DIR / "ndvi_comparacao_sinais.png"
    fig.savefig(caminho, dpi=130, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Grafico salvo: {caminho}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("  AgroClima Brasil — Correlacao NDVI x Preco")
    logger.info("=" * 60)

    for arq in [RAW_DIR/"nasa_ndvi_regioes.csv", PROC_DIR/"fato_preco.csv",
                PROC_DIR/"correlacao_resultados.csv"]:
        if not arq.exists():
            logger.error(f"Arquivo nao encontrado: {arq}")
            raise SystemExit(1)

    df_ndvi   = pd.read_csv(RAW_DIR  / "nasa_ndvi_regioes.csv", dtype={"periodo": str})
    df_preco  = pd.read_csv(PROC_DIR / "fato_preco.csv",         dtype={"periodo": str})
    df_precip = pd.read_csv(PROC_DIR / "correlacao_resultados.csv")

    if "lag" in df_precip.columns:
        df_precip = df_precip.rename(columns={"lag": "defasagem_meses"})
    if "id_categoria" in df_preco.columns:
        df_preco  = df_preco.rename(columns={"id_categoria": "id_produto"})

    logger.info(f"NDVI: {len(df_ndvi)} registros | Preco: {len(df_preco)} registros")

    # ── 1. Correlação NDVI → Preço ──────────────────────────────
    logger.info("Calculando correlacoes NDVI -> preco (lags 0-6)...")
    df_corr_ndvi = calcular_correlacoes_ndvi(df_ndvi, df_preco)

    saida_corr = PROC_DIR / "correlacao_ndvi.csv"
    df_corr_ndvi.to_csv(saida_corr, index=False, encoding="utf-8")
    logger.info(f"Resultado salvo: {saida_corr} ({len(df_corr_ndvi)} combinacoes)")

    # ── 2. Comparação de sinais ──────────────────────────────────
    logger.info("Comparando NDVI vs precipitacao como preditores...")
    df_comp = comparar_sinais(df_corr_ndvi, df_precip)

    # ── 3. Resultados ────────────────────────────────────────────
    sig_nordeste = df_corr_ndvi[
        (df_corr_ndvi["regiao"] == "Nordeste") & df_corr_ndvi["significativo"]
    ]
    sig_sul = df_corr_ndvi[
        (df_corr_ndvi["regiao"] == "Sul") & df_corr_ndvi["significativo"]
    ]

    print(f"\n{'='*70}")
    print("  NDVI NASA x Preco — Correlacoes Significativas (p < 0.05)")
    print(f"{'='*70}")
    print(f"  Nordeste: {len(sig_nordeste)} combinacoes significativas")
    print(f"  Sul     : {len(sig_sul)} combinacoes significativas")

    print(f"\n  Top correlacoes NDVI -> preco (Nordeste):")
    top = (
        sig_nordeste
        .assign(r_abs=lambda x: x["r_ndvi_preco"].abs())
        .sort_values("r_abs", ascending=False)
        .drop_duplicates(subset="produto")
        .head(8)
    )
    for _, row in top.iterrows():
        sinal = "NDVI cai -> preco sobe" if row["r_ndvi_preco"] < 0 else "NDVI sobe -> preco sobe"
        print(
            f"  {row['produto'][:38]:<38} lag{row['lag_meses']} "
            f"r={row['r_ndvi_preco']:>+.3f}  p={row['p_valor']:.3f}  {sinal}"
        )

    print(f"\n  NDVI vs Precipitacao — quem prediz melhor o preco?")
    if not df_comp.empty:
        ndvi_vence   = (df_comp["melhor_sinal"] == "NDVI").sum()
        precip_vence = (df_comp["melhor_sinal"] == "Precipitacao").sum()
        print(f"    NDVI        vence em {ndvi_vence} produtos")
        print(f"    Precipitacao vence em {precip_vence} produtos")

        print(f"\n  Detalhes por produto:")
        for _, row in df_comp.dropna(subset=["r_abs_ndvi","r_abs_precip"]).iterrows():
            vencedor = "** NDVI **" if row["melhor_sinal"] == "NDVI" else "   precip "
            print(
                f"  {vencedor}  {row['produto'][:35]:<35} "
                f"|r_ndvi|={row.get('r_abs_ndvi',0):.3f}  "
                f"|r_precip|={row.get('r_abs_precip',0):.3f}  "
                f"[{row['regiao']}]"
            )

    print(f"{'='*70}")

    # ── 4. Gráficos ──────────────────────────────────────────────
    logger.info("Gerando graficos...")
    plotar_comparacao_sinais(df_comp)

    # Séries para os 4 produtos com maior correlação NDVI
    top4 = (
        sig_nordeste
        .assign(r_abs=lambda x: x["r_ndvi_preco"].abs())
        .sort_values("r_abs", ascending=False)
        .drop_duplicates(subset="id_produto")
        .head(4)["id_produto"]
        .tolist()
    )
    for id_prod in top4:
        plotar_ndvi_serie(df_ndvi, df_preco, id_prod, "Nordeste")

    n_plots = len(list(PLOT_DIR.glob("ndvi_*.png")))
    logger.info(f"{n_plots} graficos NDVI salvos em plots/")
    logger.info("Analise NDVI concluida.")


if __name__ == "__main__":
    main()
