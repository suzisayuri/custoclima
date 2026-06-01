-- AgroClima Brasil — Schema MySQL 8.0+
-- Cria o banco e todas as tabelas do Data Warehouse
--
-- Para executar:
--   mysql -u root -p < src/warehouse/schema_mysql.sql
-- Ou cole no MySQL Workbench e execute.

CREATE DATABASE IF NOT EXISTS agroclima
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE agroclima;

-- ═══════════════════════════════════════════════════════════════
--  DIMENSÕES
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS dim_tempo (
    periodo      CHAR(6)      NOT NULL,   -- YYYYMM (ex: 202301)
    data_ref     DATE         NOT NULL,
    ano          SMALLINT     NOT NULL,
    mes          SMALLINT     NOT NULL,
    trimestre    SMALLINT     NOT NULL,
    semestre     SMALLINT     NOT NULL,
    nome_mes     VARCHAR(20),
    PRIMARY KEY (periodo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dim_produto (
    id_produto   VARCHAR(20)  NOT NULL,
    nome_produto VARCHAR(150) NOT NULL,
    grupo        VARCHAR(60),
    subgrupo     VARCHAR(60),
    PRIMARY KEY (id_produto)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dim_regiao (
    id_regiao    INT          NOT NULL AUTO_INCREMENT,
    estado       CHAR(2)      NOT NULL,
    regiao       VARCHAR(30)  NOT NULL,
    bioma        VARCHAR(40),
    cidade       VARCHAR(60)  NOT NULL,
    PRIMARY KEY (id_regiao),
    UNIQUE KEY uq_estado_cidade (estado, cidade)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ═══════════════════════════════════════════════════════════════
--  FATOS
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS fato_preco (
    id                   INT          NOT NULL AUTO_INCREMENT,
    periodo              CHAR(6)      NOT NULL,
    id_produto           VARCHAR(20)  NOT NULL,
    nome_produto         VARCHAR(150),
    variacao_mensal_pct  DECIMAL(8,4),
    numero_indice        DECIMAL(10,4),
    ano                  SMALLINT,
    mes                  SMALLINT,
    PRIMARY KEY (id),
    UNIQUE KEY uq_periodo_produto (periodo, id_produto),
    FOREIGN KEY (periodo)    REFERENCES dim_tempo(periodo),
    FOREIGN KEY (id_produto) REFERENCES dim_produto(id_produto)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fato_clima (
    id                             INT          NOT NULL AUTO_INCREMENT,
    periodo                        CHAR(6)      NOT NULL,
    estado                         CHAR(2)      NOT NULL,
    regiao                         VARCHAR(30),
    bioma                          VARCHAR(40),
    cidade                         VARCHAR(60),
    precipitacao_mm_total          DECIMAL(10,2),
    precipitacao_dias_sem_chuva    SMALLINT,
    temp_max_media                 DECIMAL(6,2),
    temp_min_media                 DECIMAL(6,2),
    media_hist_mm                  DECIMAL(10,2),
    anomalia_pct                   DECIMAL(8,2),
    evento_climatico               VARCHAR(20),
    PRIMARY KEY (id),
    UNIQUE KEY uq_periodo_estado (periodo, estado),
    FOREIGN KEY (periodo) REFERENCES dim_tempo(periodo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fato_correlacao (
    id                       INT          NOT NULL AUTO_INCREMENT,
    periodo                  CHAR(6)      NOT NULL,
    id_produto               VARCHAR(20)  NOT NULL,
    categoria                VARCHAR(150),
    variacao_mensal_pct      DECIMAL(8,4),
    precip_nordeste_mm       DECIMAL(10,2),
    precip_nordeste_mm_lag1  DECIMAL(10,2),
    precip_nordeste_mm_lag2  DECIMAL(10,2),
    precip_nordeste_mm_lag3  DECIMAL(10,2),
    precip_nordeste_mm_lag6  DECIMAL(10,2),
    precip_sul_mm            DECIMAL(10,2),
    precip_sul_mm_lag1       DECIMAL(10,2),
    precip_sul_mm_lag2       DECIMAL(10,2),
    precip_sul_mm_lag3       DECIMAL(10,2),
    precip_sul_mm_lag6       DECIMAL(10,2),
    ano                      SMALLINT,
    mes                      SMALLINT,
    PRIMARY KEY (id),
    UNIQUE KEY uq_periodo_produto (periodo, id_produto),
    FOREIGN KEY (periodo)    REFERENCES dim_tempo(periodo),
    FOREIGN KEY (id_produto) REFERENCES dim_produto(id_produto)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ═══════════════════════════════════════════════════════════════
--  ÍNDICES
-- ═══════════════════════════════════════════════════════════════

CREATE INDEX idx_fato_preco_periodo  ON fato_preco(periodo);
CREATE INDEX idx_fato_preco_produto  ON fato_preco(id_produto);
CREATE INDEX idx_fato_clima_periodo  ON fato_clima(periodo);
CREATE INDEX idx_fato_clima_estado   ON fato_clima(estado);
CREATE INDEX idx_fato_corr_periodo   ON fato_correlacao(periodo);
CREATE INDEX idx_fato_corr_produto   ON fato_correlacao(id_produto);
