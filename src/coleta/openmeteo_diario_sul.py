"""
Coleta de precipitação DIÁRIA para os estados do Sul via Open-Meteo
Foco: detectar eventos extremos (enchentes) que somem na média mensal
Saída: data/raw/openmeteo_diario_sul.csv   ← dados diários brutos
       data/raw/openmeteo_extremos_sul.csv  ← indicadores mensais de extremos

Por que dados diários importam para enchentes:
  A enchente de maio/2024 no RS teve 300mm em 3 dias.
  Na média mensal (maio/2024 inteiro) isso some.
  Mas contando "dias com >50mm nesse mês" o evento aparece claramente.

Indicadores calculados por mês/estado:
  - precip_max_dia_mm      → maior precipitação em um único dia do mês
  - dias_extremo_leve      → dias com >30mm (começa a causar alagamentos)
  - dias_extremo_moderado  → dias com >50mm (risco de enchente)
  - dias_extremo_severo    → dias com >80mm (enchente grave)
  - dias_consecutivos_max  → maior sequência de dias chuvosos seguidos
  - indice_enchente        → score composto 0-100 para uso no modelo

Uso:
  python src/coleta/openmeteo_diario_sul.py
"""

import sys
import io
import requests
import pandas as pd
import numpy as np
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

BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Múltiplos pontos por estado para melhor cobertura geográfica
# Enchentes do RS afetam principalmente Vale do Taquari, Serra Gaúcha e litoral
LOCALIDADES_SUL = [
    # Rio Grande do Sul — áreas mais afetadas por enchentes
    {"estado": "RS", "cidade": "Porto Alegre",  "lat": -30.033, "lon": -51.230},
    {"estado": "RS", "cidade": "Caxias do Sul", "lat": -29.168, "lon": -51.179},
    {"estado": "RS", "cidade": "Santa Maria",   "lat": -29.688, "lon": -53.807},
    {"estado": "RS", "cidade": "Lajeado",       "lat": -29.467, "lon": -51.961},  # Vale do Taquari
    # Santa Catarina
    {"estado": "SC", "cidade": "Florianopolis", "lat": -27.595, "lon": -48.548},
    {"estado": "SC", "cidade": "Blumenau",      "lat": -26.919, "lon": -49.066},  # historico de enchentes
    # Paraná
    {"estado": "PR", "cidade": "Curitiba",      "lat": -25.428, "lon": -49.273},
    {"estado": "PR", "cidade": "Londrina",      "lat": -23.310, "lon": -51.162},
]

PAUSA = 1.5

# Limiares de precipitação diária (mm)
LIMIAR_LEVE     = 30   # alagamentos locais
LIMIAR_MODERADO = 50   # enchente moderada
LIMIAR_SEVERO   = 80   # enchente grave / estado de emergência


def coletar_diario(localidade: dict, ano_inicio: int = 2015, ano_fim: int = 2024) -> pd.DataFrame:
    """Coleta precipitação diária do Open-Meteo para uma localidade."""
    params = {
        "latitude":   localidade["lat"],
        "longitude":  localidade["lon"],
        "start_date": f"{ano_inicio}-01-01",
        "end_date":   f"{ano_fim}-12-31",
        "daily":      "precipitation_sum,rain_sum",
        "timezone":   "America/Sao_Paulo",
    }

    for tentativa in range(1, 4):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=60)
            if resp.status_code == 429:
                espera = tentativa * 15
                logger.warning(f"  Rate limit para {localidade['cidade']} — aguardando {espera}s...")
                time.sleep(espera)
                continue
            resp.raise_for_status()
            dados = resp.json()
            break
        except requests.exceptions.RequestException as e:
            if tentativa < 3:
                time.sleep(5)
            else:
                logger.error(f"Falhou para {localidade['cidade']}: {e}")
                return pd.DataFrame()
    else:
        return pd.DataFrame()

    diario = dados.get("daily", {})
    datas  = diario.get("time", [])
    if not datas:
        return pd.DataFrame()

    df = pd.DataFrame({
        "data":           pd.to_datetime(datas),
        "precipitacao_mm": pd.to_numeric(diario.get("precipitation_sum", []), errors="coerce"),
        "chuva_mm":        pd.to_numeric(diario.get("rain_sum", []),         errors="coerce"),
    })
    df["estado"] = localidade["estado"]
    df["cidade"] = localidade["cidade"]
    return df


def calcular_indicadores_mensais(df_diario: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega dados diários em indicadores mensais de eventos extremos.
    Um mês com muitos dias >50mm é muito mais perigoso do que
    um mês com precipitação total alta mas distribuída.
    """
    df = df_diario.copy()
    df["periodo"] = df["data"].dt.strftime("%Y%m")
    df["ano"]     = df["data"].dt.year.astype("int16")
    df["mes"]     = df["data"].dt.month.astype("int16")
    df["precip"]  = df["precipitacao_mm"].fillna(0)

    def dias_consecutivos_chuva(serie: pd.Series, limiar: float = 1.0) -> int:
        """Maior sequência de dias com chuva > limiar."""
        chuvoso = (serie > limiar).astype(int)
        max_seq = 0
        atual   = 0
        for v in chuvoso:
            if v:
                atual += 1
                max_seq = max(max_seq, atual)
            else:
                atual = 0
        return max_seq

    def score_enchente(row) -> float:
        """
        Score composto 0-100:
          - Dias extremo severo pesam mais (x4)
          - Dias extremo moderado (x2)
          - Dias extremo leve (x1)
          - Dias consecutivos (bônus)
        Normalizado pelo máximo histórico implícito.
        """
        score = (
            row["dias_extremo_severo"]   * 4 +
            row["dias_extremo_moderado"] * 2 +
            row["dias_extremo_leve"]     * 1 +
            row["dias_consecutivos_max"] * 0.5
        )
        return min(round(score * 5, 1), 100.0)  # escala 0-100

    registros = []
    for (periodo, estado, cidade), grupo in df.groupby(["periodo", "estado", "cidade"]):
        p = grupo["precip"]
        registros.append({
            "periodo":                periodo,
            "ano":                    grupo["ano"].iloc[0],
            "mes":                    grupo["mes"].iloc[0],
            "estado":                 estado,
            "cidade":                 cidade,
            "precipitacao_total_mm":  round(p.sum(), 1),
            "precip_max_dia_mm":      round(p.max(), 1),
            "dias_com_chuva":         int((p > 1).sum()),
            "dias_extremo_leve":      int((p > LIMIAR_LEVE).sum()),
            "dias_extremo_moderado":  int((p > LIMIAR_MODERADO).sum()),
            "dias_extremo_severo":    int((p > LIMIAR_SEVERO).sum()),
            "dias_consecutivos_max":  dias_consecutivos_chuva(p),
        })

    df_mensal = pd.DataFrame(registros)
    df_mensal["indice_enchente"] = df_mensal.apply(score_enchente, axis=1)

    # Classifica risco
    def classificar_risco(score: float) -> str:
        if score >= 20:  return "CRITICO"
        if score >= 10:  return "ALTO"
        if score >= 5:   return "MODERADO"
        if score >= 1:   return "BAIXO"
        return "NORMAL"

    df_mensal["risco_enchente"] = df_mensal["indice_enchente"].apply(classificar_risco)
    return df_mensal.sort_values(["estado", "periodo"]).reset_index(drop=True)


def main():
    logger.info("=" * 60)
    logger.info("  AgroClima Brasil — Dados Diarios Sul (Enchentes)")
    logger.info("=" * 60)

    todos_diarios = []

    for i, loc in enumerate(LOCALIDADES_SUL, 1):
        logger.info(f"[{i}/{len(LOCALIDADES_SUL)}] {loc['cidade']} ({loc['estado']})...")
        df = coletar_diario(loc)
        if not df.empty:
            todos_diarios.append(df)
            logger.info(f"  -> {len(df)} dias coletados")
        if i < len(LOCALIDADES_SUL):
            time.sleep(PAUSA)

    if not todos_diarios:
        logger.error("Nenhum dado coletado.")
        raise SystemExit(1)

    df_diario = pd.concat(todos_diarios, ignore_index=True)

    # Salva dados diários brutos
    saida_diario = OUTPUT_DIR / "openmeteo_diario_sul.csv"
    df_diario.to_csv(saida_diario, index=False, encoding="utf-8")
    logger.info(f"Diario salvo: {saida_diario} ({saida_diario.stat().st_size/1024:.0f} KB)")

    # Calcula e salva indicadores mensais
    logger.info("Calculando indicadores mensais de eventos extremos...")
    df_extremos = calcular_indicadores_mensais(df_diario)

    saida_ext = OUTPUT_DIR / "openmeteo_extremos_sul.csv"
    df_extremos.to_csv(saida_ext, index=False, encoding="utf-8")

    # Resumo
    print(f"\n{'='*65}")
    print("  Eventos Extremos detectados no Sul (2015-2024)")
    print(f"{'='*65}")

    criticos = df_extremos[df_extremos["risco_enchente"] == "CRITICO"].sort_values(
        "indice_enchente", ascending=False
    )
    print(f"  Meses classificados como CRITICO: {len(criticos)}")
    print(f"\n  Top 10 piores meses por indice de enchente:")
    print(f"  {'Periodo':<8} {'Estado':<4} {'Cidade':<15} {'MaxDia(mm)':<12} "
          f"{'DiasExtr.':<10} {'Score':<6}")
    print(f"  {'-'*65}")
    for _, row in criticos.head(10).iterrows():
        print(f"  {row['periodo']:<8} {row['estado']:<4} {row['cidade'][:14]:<15} "
              f"{row['precip_max_dia_mm']:<12.0f} {row['dias_extremo_moderado']:<10} "
              f"{row['indice_enchente']:<6.1f}")

    # Verifica se capturou maio/2024 no RS (enchente histórica)
    print(f"\n  Verificacao: enchente RS maio/2024")
    mai24 = df_extremos[
        (df_extremos["periodo"] == "202405") &
        (df_extremos["estado"] == "RS")
    ]
    if not mai24.empty:
        for _, row in mai24.iterrows():
            print(f"    {row['cidade']}: max {row['precip_max_dia_mm']}mm/dia | "
                  f"{row['dias_extremo_moderado']} dias >50mm | "
                  f"score={row['indice_enchente']} | {row['risco_enchente']}")
    else:
        print("    Periodo nao encontrado nos dados.")

    print(f"\n  Indicadores mensais salvos em: {saida_ext}")
    print(f"{'='*65}")
    logger.info("Coleta diaria concluida.")


if __name__ == "__main__":
    main()
