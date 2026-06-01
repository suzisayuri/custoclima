-- AgroClima Brasil — Schema do Data Warehouse
-- Compatível com PostgreSQL 14+ e Snowflake
--
-- Diferenças Snowflake vs PostgreSQL (comentadas abaixo):
--   • SERIAL            → INTEGER AUTOINCREMENT
--   • IF NOT EXISTS     → suportado em tabelas, mas não em índices
--   • CHECK constraints → sintaxe igual mas Snowflake não as aplica em runtime
--   • CHAR, VARCHAR     → use VARCHAR(n) no Snowflake
--
-- Para criar no PostgreSQL:
--   psql -U postgres -d agroclima -f src/warehouse/schema.sql
--
-- Para criar via Python (ambos):
--   python src/warehouse/carregar.py --db postgres
--   python src/warehouse/carregar.py --db snowflake


-- ═══════════════════════════════════════════════════════════════
--  DIMENSÕES
-- ═══════════════════════════════════════════════════════════════

-- Calendário: granularidade mensal com atributos de período
CREATE TABLE IF NOT EXISTS dim_tempo (
    periodo      CHAR(6)      NOT NULL PRIMARY KEY,   -- YYYYMM (ex: 202301)
    data_ref     DATE         NOT NULL,               -- primeiro dia do mês
    ano          SMALLINT     NOT NULL,
    mes          SMALLINT     NOT NULL CHECK (mes BETWEEN 1 AND 12),
    trimestre    SMALLINT     NOT NULL CHECK (trimestre BETWEEN 1 AND 4),
    semestre     SMALLINT     NOT NULL CHECK (semestre BETWEEN 1 AND 2),
    nome_mes     VARCHAR(20)
);

-- Produtos alimentares do IPCA (classificação IBGE tabela 7060)
CREATE TABLE IF NOT EXISTS dim_produto (
    id_produto   VARCHAR(10)  NOT NULL PRIMARY KEY,   -- código IBGE (ex: 1107)
    nome_produto VARCHAR(150) NOT NULL,
    grupo        VARCHAR(60),                         -- ex: Alimentos, Serviços
    subgrupo     VARCHAR(60)                          -- ex: Carnes, Hortifrúti
);

-- Localidades monitoradas com estado, região geográfica e bioma
CREATE TABLE IF NOT EXISTS dim_regiao (
    id_regiao    SERIAL       PRIMARY KEY,            -- Snowflake: INTEGER AUTOINCREMENT
    estado       CHAR(2)      NOT NULL,               -- ex: CE, RS
    regiao       VARCHAR(30)  NOT NULL,               -- Nordeste, Sul
    bioma        VARCHAR(40),                         -- Caatinga, Pampa, Mata Atlântica
    cidade       VARCHAR(60)  NOT NULL,               -- capital representativa
    UNIQUE (estado, cidade)
);


-- ═══════════════════════════════════════════════════════════════
--  FATOS
-- ═══════════════════════════════════════════════════════════════

-- Variação mensal de preço por produto (fonte: IBGE IPCA tabela 7060)
CREATE TABLE IF NOT EXISTS fato_preco (
    id                   SERIAL        PRIMARY KEY,  -- Snowflake: INTEGER AUTOINCREMENT
    periodo              CHAR(6)       NOT NULL REFERENCES dim_tempo(periodo),
    id_produto           VARCHAR(10)   NOT NULL REFERENCES dim_produto(id_produto),
    nome_produto         VARCHAR(150),
    variacao_mensal_pct  DECIMAL(8,4),               -- ex: 1.23 = +1,23%
    numero_indice        DECIMAL(10,4),              -- base 2019=100
    ano                  SMALLINT,
    mes                  SMALLINT,
    UNIQUE (periodo, id_produto)
);

-- Precipitação mensal por estado com anomalia e classificação de evento
CREATE TABLE IF NOT EXISTS fato_clima (
    id                             SERIAL        PRIMARY KEY,  -- Snowflake: INTEGER AUTOINCREMENT
    periodo                        CHAR(6)       NOT NULL REFERENCES dim_tempo(periodo),
    estado                         CHAR(2)       NOT NULL,
    regiao                         VARCHAR(30),
    bioma                          VARCHAR(40),
    cidade                         VARCHAR(60),
    precipitacao_mm_total          DECIMAL(10,2), -- soma diária do mês (mm)
    precipitacao_dias_sem_chuva    SMALLINT,      -- dias com 0 mm no mês
    temp_max_media                 DECIMAL(6,2),  -- °C
    temp_min_media                 DECIMAL(6,2),  -- °C
    media_hist_mm                  DECIMAL(10,2), -- média histórica do mesmo mês/estado
    anomalia_pct                   DECIMAL(8,2),  -- desvio da média histórica (%)
    evento_climatico               VARCHAR(20),   -- normal / seca_moderada / seca_severa / chuva_intensa / enchente_severa
    UNIQUE (periodo, estado)
);

-- Tabela base para análise de correlação (preço × precipitação com lags)
-- lag1..6 = precipitação do mês anterior (1 = 1 mês antes, 6 = 6 meses antes)
CREATE TABLE IF NOT EXISTS fato_correlacao (
    id                       SERIAL        PRIMARY KEY,  -- Snowflake: INTEGER AUTOINCREMENT
    periodo                  CHAR(6)       NOT NULL REFERENCES dim_tempo(periodo),
    id_produto               VARCHAR(10)   NOT NULL REFERENCES dim_produto(id_produto),
    categoria                VARCHAR(150),
    variacao_mensal_pct      DECIMAL(8,4),
    -- Nordeste
    precip_nordeste_mm       DECIMAL(10,2),
    precip_nordeste_mm_lag1  DECIMAL(10,2),
    precip_nordeste_mm_lag2  DECIMAL(10,2),
    precip_nordeste_mm_lag3  DECIMAL(10,2),
    precip_nordeste_mm_lag6  DECIMAL(10,2),
    -- Sul
    precip_sul_mm            DECIMAL(10,2),
    precip_sul_mm_lag1       DECIMAL(10,2),
    precip_sul_mm_lag2       DECIMAL(10,2),
    precip_sul_mm_lag3       DECIMAL(10,2),
    precip_sul_mm_lag6       DECIMAL(10,2),
    ano                      SMALLINT,
    mes                      SMALLINT,
    UNIQUE (periodo, id_produto)
);


-- ═══════════════════════════════════════════════════════════════
--  ÍNDICES (performance de leitura para o dashboard)
--  Snowflake: omitir — gerenciado automaticamente por micro-partições
-- ═══════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_fato_preco_periodo   ON fato_preco(periodo);
CREATE INDEX IF NOT EXISTS idx_fato_preco_produto   ON fato_preco(id_produto);
CREATE INDEX IF NOT EXISTS idx_fato_clima_periodo   ON fato_clima(periodo);
CREATE INDEX IF NOT EXISTS idx_fato_clima_estado    ON fato_clima(estado);
CREATE INDEX IF NOT EXISTS idx_fato_corr_periodo    ON fato_correlacao(periodo);
CREATE INDEX IF NOT EXISTS idx_fato_corr_produto    ON fato_correlacao(id_produto);
