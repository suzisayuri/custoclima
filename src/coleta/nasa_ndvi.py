"""
Coleta do índice NDVI via NASA AppEEARS API
Produto: MOD13A3.061 — MODIS/Terra Vegetation Indices Monthly (1km)
Saída  : data/raw/nasa_ndvi.csv

O que é o NDVI:
  Normalized Difference Vegetation Index — calculado por satélite.
  Mede o quanto a vegetação está verde e saudável.
    >= 0.5  = vegetação densa (lavoura produtiva)
    0.3-0.5 = vegetação moderada
    0.1-0.3 = vegetação estressada (seca começando)
    < 0.1   = solo exposto (seca severa)

Por que usar pontos do interior e não as capitais:
  As capitais têm muito asfalto e área urbana que distorce o NDVI.
  Aqui usamos municípios produtores — onde a lavoura realmente existe.
  Petrolina/PE e Juazeiro/BA = maior polo de fruticultura irrigada
  Passo Fundo/RS = principal região de trigo e soja do Sul

Cadeia causal que o NDVI fecha:
  El Niño → Seca → NDVI cai (plantas morrendo) → Safra prejudicada → Preço sobe

Uso:
  python src/coleta/nasa_ndvi.py
"""

import sys, io, os, time, json
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
import logging

load_dotenv()
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://appeears.earthdatacloud.nasa.gov/api"
PRODUTO  = "MOD13A3.061"
CAMADA   = "_1_km_monthly_NDVI"

# Pontos no interior agrícola — onde a lavoura existe de verdade
PONTOS = [
    # ── Nordeste (sertão produtor) ────────────────────────────────
    {"id": "Petrolina_PE",  "regiao": "Nordeste", "estado": "PE", "lat": -9.389,  "lon": -40.503},
    {"id": "Juazeiro_BA",   "regiao": "Nordeste", "estado": "BA", "lat": -9.411,  "lon": -40.502},
    {"id": "Quixada_CE",    "regiao": "Nordeste", "estado": "CE", "lat": -4.971,  "lon": -39.016},
    {"id": "Mossoro_RN",    "regiao": "Nordeste", "estado": "RN", "lat": -5.188,  "lon": -37.344},
    {"id": "Vitoria_BA",    "regiao": "Nordeste", "estado": "BA", "lat": -14.863, "lon": -40.840},
    # ── Sul (principal área produtora) ───────────────────────────
    {"id": "PassoFundo_RS", "regiao": "Sul",      "estado": "RS", "lat": -28.263, "lon": -52.406},
    {"id": "Lajeado_RS",    "regiao": "Sul",      "estado": "RS", "lat": -29.467, "lon": -51.961},
    {"id": "Chapeco_SC",    "regiao": "Sul",      "estado": "SC", "lat": -27.101, "lon": -52.620},
    {"id": "Cascavel_PR",   "regiao": "Sul",      "estado": "PR", "lat": -24.957, "lon": -53.455},
    {"id": "Maringa_PR",    "regiao": "Sul",      "estado": "PR", "lat": -23.421, "lon": -51.933},
]


def obter_token() -> str:
    user = os.getenv("NASA_USERNAME")
    pwd  = os.getenv("NASA_PASSWORD")
    if not user or not pwd:
        raise ValueError("Configure NASA_USERNAME e NASA_PASSWORD no .env")
    r = requests.post(f"{BASE_URL}/login", auth=(user, pwd), timeout=20)
    r.raise_for_status()
    logger.info("Autenticacao NASA: OK")
    return r.json()["token"]


def submeter_tarefa(token: str, ano_inicio: int = 2015, ano_fim: int = 2025) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    tarefa = {
        "task_type": "point",
        "task_name": f"AgroClima_NDVI_{ano_inicio}_{ano_fim}",
        "params": {
            "dates": [{
                "startDate": f"01-01-{ano_inicio}",
                "endDate":   f"12-31-{ano_fim}",
            }],
            "layers": [{"product": PRODUTO, "layer": CAMADA}],
            "coordinates": [
                {"latitude": p["lat"], "longitude": p["lon"], "id": p["id"]}
                for p in PONTOS
            ],
        },
    }
    r = requests.post(f"{BASE_URL}/task", json=tarefa, headers=headers, timeout=30)
    r.raise_for_status()
    task_id = r.json()["task_id"]
    logger.info(f"Tarefa submetida: {task_id}")
    return task_id


def aguardar_tarefa(token: str, task_id: str, timeout_min: int = 30) -> bool:
    headers = {"Authorization": f"Bearer {token}"}
    inicio  = time.time()
    logger.info("Aguardando processamento NASA (pode levar alguns minutos)...")
    while True:
        r      = requests.get(f"{BASE_URL}/task/{task_id}", headers=headers, timeout=15)
        status = r.json().get("status", "unknown")
        elapsed = (time.time() - inicio) / 60

        if status == "done":
            logger.info(f"Tarefa concluida em {elapsed:.1f} min")
            return True
        if status == "error":
            logger.error(f"Erro na tarefa: {r.json()}")
            return False
        if elapsed > timeout_min:
            logger.warning(f"Timeout ({timeout_min} min). Status: {status}")
            return False

        logger.info(f"  {status} ({elapsed:.1f} min)...")
        time.sleep(20)


def baixar_resultado(token: str, task_id: str) -> pd.DataFrame:
    headers = {"Authorization": f"Bearer {token}"}

    # Lista arquivos disponíveis
    r = requests.get(f"{BASE_URL}/bundle/{task_id}", headers=headers, timeout=15)
    arquivos = r.json().get("files", [])

    # Pega o CSV de resultados
    csv_arq = next((a for a in arquivos if a["file_name"].endswith(".csv")), None)
    if not csv_arq:
        logger.error("Nenhum CSV encontrado no bundle.")
        logger.info(f"Arquivos disponíveis: {[a['file_name'] for a in arquivos]}")
        return pd.DataFrame()

    logger.info(f"Baixando: {csv_arq['file_name']}")
    r2 = requests.get(
        f"{BASE_URL}/bundle/{task_id}/{csv_arq['file_id']}",
        headers=headers, stream=True, timeout=60,
    )
    r2.raise_for_status()

    from io import StringIO
    return pd.read_csv(StringIO(r2.content.decode("utf-8", errors="replace")))


def processar_ndvi(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Padroniza o CSV do AppEEARS para o formato do projeto."""
    if df_raw.empty:
        return pd.DataFrame()

    logger.info(f"Colunas do AppEEARS: {df_raw.columns.tolist()}")

    # AppEEARS usa nomes como 'Date', 'MOD13A3.061__1_km_monthly_NDVI', 'ID', etc.
    col_data  = next((c for c in df_raw.columns if c.lower() in ("date", "datetime", "time")), None)
    col_id    = next((c for c in df_raw.columns if c.lower() in ("id", "site", "point", "name")), None)
    col_ndvi  = next((c for c in df_raw.columns if "ndvi" in c.lower()), None)
    col_qa    = next((c for c in df_raw.columns if "quality" in c.lower() or "_qa" in c.lower()), None)

    if not col_ndvi:
        logger.error("Coluna NDVI não encontrada. Inspecione o arquivo manualmente.")
        return df_raw

    df = df_raw.copy()

    # Mapa ID → metadados do ponto
    mapa = {p["id"]: p for p in PONTOS}

    registros = []
    for _, row in df.iterrows():
        id_ponto = str(row.get(col_id, "")) if col_id else ""
        info     = mapa.get(id_ponto, {})

        val_raw = row[col_ndvi]
        try:
            ndvi = float(val_raw)
            # MODIS escala: -2000 a 10000 → dividir por 10000
            if abs(ndvi) > 10:
                ndvi = ndvi / 10000.0
            ndvi = round(ndvi, 4)
        except (ValueError, TypeError):
            ndvi = None

        if ndvi is not None and (ndvi < -0.3 or ndvi > 1.0):
            ndvi = None  # valor inválido (nuvem ou dado ausente)

        data_str = str(row[col_data]) if col_data else ""
        try:
            data = pd.to_datetime(data_str)
        except Exception:
            continue

        registros.append({
            "periodo":  data.strftime("%Y%m"),
            "ano":      data.year,
            "mes":      data.month,
            "id_ponto": id_ponto,
            "regiao":   info.get("regiao", ""),
            "estado":   info.get("estado", ""),
            "ndvi":     ndvi,
        })

    df_proc = pd.DataFrame(registros)
    if df_proc.empty:
        return df_proc

    # Classifica saúde da vegetação
    def classificar(v):
        if pd.isna(v):   return "sem_dado"
        if v >= 0.5:     return "saudavel"
        if v >= 0.3:     return "moderado"
        if v >= 0.1:     return "estressado"
        return "seco_critico"

    df_proc["saude_vegetacao"] = df_proc["ndvi"].apply(classificar)

    # Média mensal por região (para usar no modelo de correlação)
    df_reg = (
        df_proc.groupby(["periodo", "ano", "mes", "regiao"])["ndvi"]
        .mean()
        .round(4)
        .reset_index()
        .rename(columns={"ndvi": "ndvi_medio_regiao"})
    )
    df_reg["saude_vegetacao"] = df_reg["ndvi_medio_regiao"].apply(classificar)

    return df_proc, df_reg


def main():
    logger.info("=" * 60)
    logger.info("  AgroClima Brasil — NDVI Satelital (NASA MODIS)")
    logger.info("=" * 60)

    token   = obter_token()
    task_id = submeter_tarefa(token)

    ok = aguardar_tarefa(token, task_id)
    if not ok:
        logger.error("Tarefa nao concluida. Tente novamente.")
        raise SystemExit(1)

    df_raw = baixar_resultado(token, task_id)
    if df_raw.empty:
        raise SystemExit(1)

    resultado = processar_ndvi(df_raw)
    if isinstance(resultado, tuple):
        df_pontos, df_regioes = resultado
    else:
        logger.error("Processamento falhou. Salvando CSV bruto para inspeção.")
        df_raw.to_csv(OUTPUT_DIR / "nasa_ndvi_bruto.csv", index=False)
        raise SystemExit(1)

    # Salva ambos os datasets
    saida_pt  = OUTPUT_DIR / "nasa_ndvi_pontos.csv"
    saida_reg = OUTPUT_DIR / "nasa_ndvi_regioes.csv"
    df_pontos.to_csv(saida_pt,  index=False, encoding="utf-8")
    df_regioes.to_csv(saida_reg, index=False, encoding="utf-8")

    # Resumo
    print(f"\n{'='*65}")
    print("  NDVI NASA MODIS — Resultado")
    print(f"{'='*65}")
    print(f"  Pontos coletados : {df_pontos['id_ponto'].nunique()}")
    print(f"  Registros totais : {len(df_pontos):,}")
    print(f"  Periodo          : {df_pontos['periodo'].min()} a {df_pontos['periodo'].max()}")

    print(f"\n  NDVI medio por regiao:")
    for reg, grp in df_pontos.groupby("regiao"):
        media = grp["ndvi"].mean()
        print(f"    {reg:<12} {media:.3f}  ({grp['saude_vegetacao'].value_counts().index[0]})")

    print(f"\n  Meses com vegetacao CRITICA (NDVI < 0.1):")
    criticos = df_regioes[df_regioes["saude_vegetacao"] == "seco_critico"]
    if not criticos.empty:
        for _, row in criticos.sort_values("ndvi_medio_regiao").head(8).iterrows():
            print(f"    {row['periodo']}  {row['regiao']:<12} NDVI={row['ndvi_medio_regiao']:.3f}")
    else:
        print("    Nenhum mes critico no periodo.")

    print(f"\n  Salvo em: {saida_pt}")
    print(f"           {saida_reg}")
    print(f"{'='*65}")
    logger.info("Coleta NDVI concluida.")


if __name__ == "__main__":
    main()
