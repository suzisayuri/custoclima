"""
Carregamento dos dados processados no Data Warehouse.
Suporta MySQL (padrão), PostgreSQL e Snowflake.

O script:
  1. Detecta qual banco usar pelo .env
  2. Cria o banco e as tabelas via schema (se não existirem)
  3. Carrega os CSVs de data/processed/ em append
  4. Valida a carga com contagem por tabela

Uso:
  python src/warehouse/carregar.py             # detecta pelo .env
  python src/warehouse/carregar.py --db mysql
  python src/warehouse/carregar.py --db postgres
  python src/warehouse/carregar.py --db snowflake
"""

import argparse
import os
import logging
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PROC_DIR       = Path("data/processed")
SCHEMA_MYSQL   = Path("src/warehouse/schema_mysql.sql")
SCHEMA_POSTGRES = Path("src/warehouse/schema.sql")

# Ordem importa: dimensões antes dos fatos (FK)
TABELAS = [
    ("dim_tempo.csv",            "dim_tempo"),
    ("dim_produto.csv",          "dim_produto"),
    ("dim_regiao.csv",           "dim_regiao"),
    ("fato_preco.csv",           "fato_preco"),
    ("fato_clima.csv",           "fato_clima"),
    ("fato_correlacao_base.csv", "fato_correlacao"),
]


# ── Conexões ──────────────────────────────────────────────────────────────────

def conectar_mysql():
    try:
        from sqlalchemy import create_engine, text
        import pymysql  # noqa: F401
    except ImportError:
        logger.error("Execute: python -m pip install pymysql sqlalchemy")
        raise

    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    db   = os.getenv("MYSQL_DB",   "agroclima")
    user = os.getenv("MYSQL_USER", "root")
    pwd  = os.getenv("MYSQL_PASSWORD", "")

    # Primeiro conecta sem banco para criá-lo se não existir
    url_sem_db = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/?charset=utf8mb4"
    engine_sem_db = create_engine(url_sem_db, echo=False)
    try:
        with engine_sem_db.connect() as conn:
            conn.execute(text(
                f"CREATE DATABASE IF NOT EXISTS `{db}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            ))
            conn.commit()
        logger.info(f"Banco '{db}' verificado/criado.")
    except Exception as e:
        logger.error(f"Nao foi possivel criar o banco '{db}': {e}")
        raise

    url = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}?charset=utf8mb4"
    engine = create_engine(url, echo=False)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info(f"Conectado ao MySQL: {host}:{port}/{db}")
    return engine


def conectar_postgres():
    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        logger.error("Execute: python -m pip install sqlalchemy psycopg2-binary")
        raise

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db   = os.getenv("POSTGRES_DB",   "agroclima")
    user = os.getenv("POSTGRES_USER", "postgres")
    pwd  = os.getenv("POSTGRES_PASSWORD", "")

    url    = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"
    engine = create_engine(url, echo=False)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info(f"Conectado ao PostgreSQL: {host}:{port}/{db}")
    return engine


def conectar_snowflake():
    try:
        from sqlalchemy import create_engine
    except ImportError:
        logger.error("Execute: python -m pip install sqlalchemy snowflake-connector-python snowflake-sqlalchemy")
        raise

    account   = os.getenv("SNOWFLAKE_ACCOUNT")
    user      = os.getenv("SNOWFLAKE_USER")
    password  = os.getenv("SNOWFLAKE_PASSWORD")
    database  = os.getenv("SNOWFLAKE_DATABASE", "AGROCLIMA")
    schema    = os.getenv("SNOWFLAKE_SCHEMA",   "PUBLIC")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")

    if not all([account, user, password]):
        raise ValueError("Configure SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER e SNOWFLAKE_PASSWORD no .env")

    conn_str = (
        f"snowflake://{user}:{password}@{account}/"
        f"{database}/{schema}?warehouse={warehouse}"
    )
    engine = create_engine(conn_str)
    logger.info(f"Conectado ao Snowflake: {account}/{database}.{schema}")
    return engine


def detectar_db() -> str:
    """Detecta qual banco usar: MySQL se configurado, senão verifica Snowflake, senão postgres."""
    mysql_pwd = os.getenv("MYSQL_PASSWORD", "")
    mysql_user = os.getenv("MYSQL_USER", "")
    if mysql_user and mysql_user != "root":
        return "mysql"
    if os.getenv("SNOWFLAKE_ACCOUNT", "seu_account_id") != "seu_account_id":
        return "snowflake"
    # MySQL é o padrão quando está instalado localmente
    return "mysql"


# ── Schema ────────────────────────────────────────────────────────────────────

def criar_schema(engine, db_tipo: str) -> None:
    """Executa o schema SQL para criar tabelas."""
    if db_tipo == "mysql":
        schema_path = SCHEMA_MYSQL
    else:
        schema_path = SCHEMA_POSTGRES

    if not schema_path.exists():
        logger.warning(f"Schema nao encontrado: {schema_path}")
        return

    sql_completo = schema_path.read_text(encoding="utf-8")

    if db_tipo == "snowflake":
        sql_completo = sql_completo.replace("SERIAL", "INTEGER AUTOINCREMENT")

    from sqlalchemy import text

    with engine.begin() as conn:
        for stmt in sql_completo.split(";"):
            stmt = stmt.strip()
            if not stmt or stmt.startswith("--"):
                continue
            try:
                conn.execute(text(stmt))
            except Exception as e:
                logger.debug(f"Schema (ja existia ou aviso): {e}")

    logger.info("Schema criado/verificado.")


# ── Carga ─────────────────────────────────────────────────────────────────────

def carregar_tabela(engine, csv_path: Path, nome_tabela: str) -> int:
    if not csv_path.exists():
        logger.warning(f"  {nome_tabela:<30} PULADO (arquivo nao encontrado: {csv_path})")
        return 0

    df = pd.read_csv(csv_path)
    df = df.drop(columns=["id"], errors="ignore")  # banco gera o id automatico

    df.to_sql(
        nome_tabela,
        engine,
        if_exists="append",
        index=False,
        chunksize=1000,
        method="multi",
    )
    logger.info(f"  {nome_tabela:<30} {len(df):>8,} linhas inseridas")
    return len(df)


# ── Validação ─────────────────────────────────────────────────────────────────

def validar_carga(engine) -> None:
    from sqlalchemy import text, inspect

    tabelas_existentes = inspect(engine).get_table_names()

    print(f"\n{'='*50}")
    print("  Validacao de carga — contagem por tabela")
    print(f"{'='*50}")

    with engine.connect() as conn:
        for _, nome in TABELAS:
            if nome in tabelas_existentes:
                n = conn.execute(text(f"SELECT COUNT(*) FROM {nome}")).scalar()
                print(f"  {nome:<30} {n:>8,} linhas")
            else:
                print(f"  {nome:<30} NAO ENCONTRADA")

    print(f"{'='*50}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Carga AgroClima no Data Warehouse")
    parser.add_argument(
        "--db",
        choices=["mysql", "postgres", "snowflake"],
        default=None,
        help="Banco de destino (default: detecta pelo .env, prioridade MySQL)",
    )
    args = parser.parse_args()

    db_tipo = args.db or detectar_db()
    logger.info(f"Banco selecionado: {db_tipo.upper()}")

    if db_tipo == "mysql":
        engine = conectar_mysql()
    elif db_tipo == "postgres":
        engine = conectar_postgres()
    else:
        engine = conectar_snowflake()

    logger.info("Criando schema...")
    criar_schema(engine, db_tipo)

    logger.info("Carregando tabelas...")
    total = 0
    for csv_nome, tabela_nome in TABELAS:
        total += carregar_tabela(engine, PROC_DIR / csv_nome, tabela_nome)

    logger.info(f"\nTotal inserido: {total:,} linhas")
    validar_carga(engine)
    logger.info("Carga concluida.")


if __name__ == "__main__":
    main()
