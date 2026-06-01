"""
Backtesting v2 — compara dois sinais para o Sul:
  v1: ONI (El Niño/La Niña)         → era só 9-14% de acerto no Sul
  v2: indice_enchente (dados diários) → baseado em precipitação diária extrema

Nordeste continua usando ONI (63% no El Niño forte).

Entradas: data/raw/noaa_enso_oni.csv
          data/raw/openmeteo_extremos_sul.csv   ← NOVO sinal para o Sul
          data/processed/fato_preco.csv
          data/processed/correlacao_resultados.csv
Saídas  : data/processed/backtesting_v1.csv
          data/processed/backtesting_v2.csv
          plots/backtesting_comparacao.png
          plots/backtesting_acuracia_v2.png

Uso:
  python src/analise/backtesting.py
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
import matplotlib.patches as mpatches

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

LIMIAR_PCT = 0.3   # variacao de preco: acima = ALTA, abaixo = QUEDA


# ── Helpers ───────────────────────────────────────────────────────────────────

def classificar_variacao(v) -> str:
    if pd.isna(v):
        return "desconhecido"
    return "ALTA" if v > LIMIAR_PCT else "QUEDA" if v < -LIMIAR_PCT else "ESTAVEL"


def periodo_mais_lag(periodo: str, lag: int) -> str:
    """Retorna o período YYYYMM somando lag meses."""
    ano = int(periodo[:4])
    mes = int(periodo[4:]) + lag
    ano += (mes - 1) // 12
    mes  = ((mes - 1) % 12) + 1
    return f"{ano}{str(mes).zfill(2)}"


# ── Backtesting v1: ONI → Sul (método original) ───────────────────────────────

def prever_oni(oni: float, r_pearson: float, regiao: str) -> str:
    if abs(oni) < 0.5:
        return "ESTAVEL"
    if oni > 0.5 and regiao == "Nordeste":
        return "ALTA" if r_pearson < 0 else "QUEDA"
    if oni < -0.5 and regiao == "Sul":
        return "ALTA" if r_pearson > 0 else "QUEDA"
    return "ESTAVEL"


def rodar_v1(df_oni, df_preco, df_corr) -> pd.DataFrame:
    """Versão original: usa ONI para Nordeste e Sul."""
    idx = df_preco.set_index(["periodo", "id_produto"])["variacao_mensal_pct"].to_dict()
    corr_sig = df_corr[df_corr["significativo"].astype(bool)]
    resultados = []

    for _, oni_row in df_oni.iterrows():
        periodo_t = str(oni_row["periodo"])
        oni_val   = float(oni_row["oni"])
        fase      = str(oni_row["fase_enso"])
        if abs(oni_val) < 0.5:
            continue

        for _, c in corr_sig.iterrows():
            lag         = int(c["defasagem_meses"])
            periodo_alvo = periodo_mais_lag(periodo_t, lag)
            previsao    = prever_oni(oni_val, float(c["r_pearson"]), c["regiao"])
            var_real    = idx.get((periodo_alvo, c["id_produto"]), np.nan)
            real        = classificar_variacao(var_real)
            if real == "desconhecido":
                continue

            resultados.append({
                "periodo_previsao": periodo_t,
                "periodo_alvo":     periodo_alvo,
                "lag_meses":        lag,
                "sinal":            f"ONI={oni_val:+.1f}",
                "fase_enso":        fase,
                "regiao":           c["regiao"],
                "produto":          c["produto"],
                "id_produto":       c["id_produto"],
                "previsao":         previsao,
                "real":             real,
                "variacao_real":    round(var_real, 3) if not pd.isna(var_real) else None,
                "acerto":           previsao == real,
            })

    return pd.DataFrame(resultados)


# ── Backtesting v2: indice_enchente → Sul ─────────────────────────────────────

def calcular_correlacao_enchente_preco(
    df_extremos: pd.DataFrame,
    df_preco: pd.DataFrame,
    df_corr: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calcula a correlação entre indice_enchente e variação de preço para produtos do Sul.
    Retorna o melhor lag e r de Pearson para cada produto.
    """
    # Índice médio mensal por período (média das cidades do Sul)
    idx_mensal = (
        df_extremos.groupby("periodo")["indice_enchente"]
        .mean()
        .reset_index()
        .sort_values("periodo")
    )

    produtos_sul = df_corr[df_corr["regiao"] == "Sul"]["id_produto"].unique()
    resultados = []

    for id_prod in produtos_sul:
        nome = df_corr[df_corr["id_produto"] == id_prod]["produto"].iloc[0]
        df_p = df_preco[df_preco["id_produto"] == id_prod][["periodo", "variacao_mensal_pct"]].copy()

        for lag in range(0, 7):
            idx_lag = idx_mensal.copy()
            idx_lag["periodo_alvo"] = idx_lag["periodo"].apply(
                lambda p: periodo_mais_lag(str(p), lag)
            )
            merged = idx_lag.merge(
                df_p.rename(columns={"periodo": "periodo_alvo"}),
                on="periodo_alvo", how="inner"
            ).dropna()

            if len(merged) < 12:
                continue

            r, p = stats.pearsonr(merged["variacao_mensal_pct"], merged["indice_enchente"])
            resultados.append({
                "id_produto":       id_prod,
                "produto":          nome,
                "lag_meses":        lag,
                "r_enchente_preco": round(r, 4),
                "p_valor":          round(p, 4),
                "significativo":    p < 0.05,
            })

    return pd.DataFrame(resultados)


def prever_enchente(indice: float, r_pearson: float) -> str:
    """Previsão baseada no índice de enchente diário."""
    if indice < 5:
        return "ESTAVEL"
    # Índice alto + correlação positiva → preço sobe
    return "ALTA" if r_pearson > 0 else "QUEDA"


def rodar_v2(df_oni, df_preco, df_corr, df_extremos, df_corr_enchente) -> pd.DataFrame:
    """
    v2: Nordeste usa ONI (igual à v1), Sul usa indice_enchente diário.
    """
    idx = df_preco.set_index(["periodo", "id_produto"])["variacao_mensal_pct"].to_dict()

    # Índice médio mensal Sul
    idx_enchente = (
        df_extremos.groupby("periodo")["indice_enchente"]
        .mean()
        .to_dict()
    )

    corr_sig = df_corr[df_corr["significativo"].astype(bool)]

    # Melhor correlação enchente→preço por produto
    best_enchente = (
        df_corr_enchente[df_corr_enchente["significativo"]]
        .sort_values("r_enchente_preco", key=abs, ascending=False)
        .drop_duplicates(subset="id_produto")
        .set_index("id_produto")
    )

    resultados = []

    # ── Nordeste: mesmo que v1 ──
    for _, oni_row in df_oni.iterrows():
        periodo_t = str(oni_row["periodo"])
        oni_val   = float(oni_row["oni"])
        fase      = str(oni_row["fase_enso"])
        if abs(oni_val) < 0.5:
            continue

        nordeste = corr_sig[corr_sig["regiao"] == "Nordeste"]
        for _, c in nordeste.iterrows():
            lag          = int(c["defasagem_meses"])
            periodo_alvo = periodo_mais_lag(periodo_t, lag)
            previsao     = prever_oni(oni_val, float(c["r_pearson"]), "Nordeste")
            var_real     = idx.get((periodo_alvo, c["id_produto"]), np.nan)
            real         = classificar_variacao(var_real)
            if real == "desconhecido":
                continue
            resultados.append({
                "periodo_previsao": periodo_t,
                "periodo_alvo":     periodo_alvo,
                "lag_meses":        lag,
                "sinal":            f"ONI={oni_val:+.1f}",
                "fase_enso":        fase,
                "regiao":           "Nordeste",
                "produto":          c["produto"],
                "id_produto":       c["id_produto"],
                "previsao":         previsao,
                "real":             real,
                "variacao_real":    round(var_real, 3) if not pd.isna(var_real) else None,
                "acerto":           previsao == real,
            })

    # ── Sul: usa indice_enchente ──
    for periodo_t, indice in idx_enchente.items():
        if indice < 5:   # sem sinal relevante
            continue

        for id_prod, row_enc in best_enchente.iterrows():
            lag          = int(row_enc["lag_meses"])
            periodo_alvo = periodo_mais_lag(str(periodo_t), lag)
            previsao     = prever_enchente(indice, float(row_enc["r_enchente_preco"]))
            var_real     = idx.get((periodo_alvo, id_prod), np.nan)
            real         = classificar_variacao(var_real)
            if real == "desconhecido":
                continue

            # ONI do mesmo período para contexto
            oni_ref = df_oni[df_oni["periodo"] == str(periodo_t)]["oni"]
            oni_str = f"IE={indice:.0f}"

            resultados.append({
                "periodo_previsao": str(periodo_t),
                "periodo_alvo":     periodo_alvo,
                "lag_meses":        lag,
                "sinal":            oni_str,
                "fase_enso":        "enchente" if indice >= 20 else "chuva_intensa",
                "regiao":           "Sul",
                "produto":          row_enc["produto"],
                "id_produto":       id_prod,
                "previsao":         previsao,
                "real":             real,
                "variacao_real":    round(var_real, 3) if not pd.isna(var_real) else None,
                "acerto":           previsao == real,
            })

    return pd.DataFrame(resultados)


# ── Visualizações ─────────────────────────────────────────────────────────────

def plotar_comparacao(df_v1: pd.DataFrame, df_v2: pd.DataFrame) -> None:
    """Gráfico lado a lado: acurácia v1 vs v2 por produto e região."""
    def resumo(df, label):
        return (
            df.groupby(["regiao", "produto"])["acerto"]
            .mean().mul(100).round(1)
            .reset_index()
            .rename(columns={"acerto": label})
        )

    r1 = resumo(df_v1, "v1_ONI")
    r2 = resumo(df_v2, "v2_Diario")
    comp = r1.merge(r2, on=["regiao", "produto"], how="outer").fillna(0)
    comp["melhora"] = comp["v2_Diario"] - comp["v1_ONI"]
    comp = comp.sort_values(["regiao", "melhora"], ascending=[True, False])

    fig, axes = plt.subplots(1, 2, figsize=(15, max(5, len(comp) * 0.45 + 1)),
                              sharey=True)

    for ax, col, titulo, cor in zip(
        axes,
        ["v1_ONI", "v2_Diario"],
        ["v1 — Sinal ONI (La Nina/El Nino)", "v2 — Sinal Diario (Indice Enchente no Sul)"],
        ["#3498db", "#2ecc71"],
    ):
        cores = [cor if r == "Sul" else "#e67e22" for r in comp["regiao"]]
        ax.barh(comp["produto"], comp[col], color=cores, alpha=0.85)
        ax.axvline(50, color="black", linewidth=1, linestyle="--", alpha=0.4)
        ax.axvline(60, color="green", linewidth=1, linestyle=":", alpha=0.4)
        ax.set_xlabel("Acuracia (%)")
        ax.set_title(titulo, fontsize=10, fontweight="bold")
        ax.set_xlim(0, 100)
        for i, (_, row) in enumerate(comp.iterrows()):
            ax.text(row[col] + 0.5, i, f"{row[col]:.0f}%", va="center", fontsize=7)

    sul_p    = mpatches.Patch(color="#2ecc71", label="Sul (sinal novo)")
    nord_p   = mpatches.Patch(color="#e67e22", label="Nordeste (mesmo)")
    linha50  = mpatches.Patch(color="black",   alpha=0.4, label="50% = acaso")
    axes[1].legend(handles=[sul_p, nord_p, linha50], fontsize=8, loc="lower right")

    fig.suptitle("Comparacao de acuracia: ONI vs Indice de Enchente Diario",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    caminho = PLOT_DIR / "backtesting_comparacao.png"
    fig.savefig(caminho, dpi=130, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Grafico salvo: {caminho}")


def plotar_acuracia_v2(df: pd.DataFrame) -> None:
    resumo = (
        df.groupby(["regiao", "produto"])["acerto"]
        .agg(acertos="sum", total="count")
        .assign(acuracia=lambda x: x["acertos"] / x["total"] * 100)
        .sort_values(["regiao", "acuracia"])
        .reset_index()
    )

    cores = []
    for _, row in resumo.iterrows():
        if row["acuracia"] >= 60:
            cores.append("#2ecc71")
        elif row["acuracia"] >= 50:
            cores.append("#e67e22")
        else:
            cores.append("#e74c3c")

    labels = [f"[{r}] {p[:30]}" for r, p in zip(resumo["regiao"], resumo["produto"])]

    fig, ax = plt.subplots(figsize=(11, max(5, len(resumo) * 0.5)))
    ax.barh(labels, resumo["acuracia"], color=cores)
    ax.axvline(50, color="black", linewidth=1, linestyle="--", alpha=0.5)
    ax.axvline(60, color="green", linewidth=1, linestyle=":", alpha=0.5)

    for i, (acc, tot) in enumerate(zip(resumo["acuracia"], resumo["total"])):
        ax.text(acc + 0.5, i, f"{acc:.0f}% (n={tot})", va="center", fontsize=8)

    verde  = mpatches.Patch(color="#2ecc71", label=">= 60% (bom)")
    laranj = mpatches.Patch(color="#e67e22", label="50-60% (razoavel)")
    verm   = mpatches.Patch(color="#e74c3c", label="< 50% (ruim)")
    ax.legend(handles=[verde, laranj, verm], fontsize=8)
    ax.set_title("Backtesting v2 — Acuracia por produto\n"
                 "Nordeste: ONI | Sul: Indice de Enchente Diario",
                 fontsize=11)
    ax.set_xlabel("Acuracia (%)")
    ax.set_xlim(0, 105)
    plt.tight_layout()
    caminho = PLOT_DIR / "backtesting_acuracia_v2.png"
    fig.savefig(caminho, dpi=130, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Grafico salvo: {caminho}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("  AgroClima Brasil — Backtesting v2 (Enchente Diario)")
    logger.info("=" * 60)

    for arq in [RAW_DIR/"noaa_enso_oni.csv", RAW_DIR/"openmeteo_extremos_sul.csv",
                PROC_DIR/"fato_preco.csv",   PROC_DIR/"correlacao_resultados.csv"]:
        if not arq.exists():
            logger.error(f"Arquivo nao encontrado: {arq}")
            raise SystemExit(1)

    df_oni     = pd.read_csv(RAW_DIR  / "noaa_enso_oni.csv",        dtype={"periodo": str})
    df_extremos= pd.read_csv(RAW_DIR  / "openmeteo_extremos_sul.csv",dtype={"periodo": str})
    df_preco   = pd.read_csv(PROC_DIR / "fato_preco.csv",            dtype={"periodo": str})
    df_corr    = pd.read_csv(PROC_DIR / "correlacao_resultados.csv")

    if "lag" in df_corr.columns:
        df_corr = df_corr.rename(columns={"lag": "defasagem_meses"})
    if "id_categoria" in df_preco.columns:
        df_preco = df_preco.rename(columns={"id_categoria": "id_produto"})

    # ── v1: método original ──
    logger.info("Rodando backtesting v1 (ONI)...")
    df_v1 = rodar_v1(df_oni, df_preco, df_corr)
    df_v1.to_csv(PROC_DIR / "backtesting_v1.csv", index=False, encoding="utf-8")
    logger.info(f"  v1: {len(df_v1):,} previsoes | acuracia geral: {df_v1['acerto'].mean()*100:.1f}%")

    # ── Correlação enchente → preço (Sul) ──
    logger.info("Calculando correlacao indice_enchente -> preco (Sul)...")
    df_corr_enc = calcular_correlacao_enchente_preco(df_extremos, df_preco, df_corr)
    sig = df_corr_enc[df_corr_enc["significativo"]]
    logger.info(f"  {len(sig)} combinacoes produto×lag significativas para o Sul")

    # ── v2: Sul com índice diário ──
    logger.info("Rodando backtesting v2 (ONI + Enchente Diario)...")
    df_v2 = rodar_v2(df_oni, df_preco, df_corr, df_extremos, df_corr_enc)
    df_v2.to_csv(PROC_DIR / "backtesting_v2.csv", index=False, encoding="utf-8")
    logger.info(f"  v2: {len(df_v2):,} previsoes | acuracia geral: {df_v2['acerto'].mean()*100:.1f}%")

    # ── Comparação ──
    def acc_regiao(df, regiao):
        sub = df[df["regiao"] == regiao]
        return sub["acerto"].mean() * 100 if len(sub) > 0 else 0.0

    print(f"\n{'='*65}")
    print("  Comparacao de Acuracia: v1 (ONI) vs v2 (Enchente Diario)")
    print(f"{'='*65}")
    print(f"  {'Regiao':<12} {'v1 (ONI)':<15} {'v2 (Diario)':<15} {'Melhora'}")
    print(f"  {'-'*55}")

    for regiao in ["Nordeste", "Sul"]:
        a1 = acc_regiao(df_v1, regiao)
        a2 = acc_regiao(df_v2, regiao)
        melhora = a2 - a1
        sinal   = "+" if melhora >= 0 else ""
        print(f"  {regiao:<12} {a1:>6.1f}%         {a2:>6.1f}%         {sinal}{melhora:.1f}%")

    print(f"\n  Acuracia por fase ENSO (v2):")
    for fase, acc in df_v2.groupby("fase_enso")["acerto"].mean().mul(100).round(1).items():
        print(f"    {fase:<20} {acc:>5.1f}%")

    print(f"\n  Top produtos Sul — acuracia v1 vs v2:")
    sul_v1 = df_v1[df_v1["regiao"]=="Sul"].groupby("produto")["acerto"].mean().mul(100)
    sul_v2 = df_v2[df_v2["regiao"]=="Sul"].groupby("produto")["acerto"].mean().mul(100)
    comp_sul = pd.DataFrame({"v1": sul_v1, "v2": sul_v2}).dropna()
    comp_sul["melhora"] = comp_sul["v2"] - comp_sul["v1"]
    for prod, row in comp_sul.sort_values("melhora", ascending=False).iterrows():
        sinal = "+" if row["melhora"] >= 0 else ""
        print(f"    {prod[:40]:<40} v1:{row['v1']:>5.1f}%  v2:{row['v2']:>5.1f}%  ({sinal}{row['melhora']:.1f}%)")

    print(f"\n  Graficos salvos em plots/")
    print(f"{'='*65}")

    # Gráficos
    plotar_comparacao(df_v1, df_v2)
    plotar_acuracia_v2(df_v2)


if __name__ == "__main__":
    main()
