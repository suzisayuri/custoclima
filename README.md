# AgroClima Brasil

Pipeline de dados que conecta eventos climáticos extremos no Brasil (seca no Nordeste e enchentes no Sul) à variação de preços de alimentos pagos pelo consumidor urbano.

## Estrutura

```
agroclima-brasil/
├── data/
│   ├── raw/          # dados brutos baixados pelas APIs
│   └── processed/    # dados tratados e prontos para o DW
├── src/
│   ├── coleta/       # um script por fonte de dados
│   ├── etl/          # limpeza, transformação, merge
│   ├── warehouse/    # carga no Snowflake / PostgreSQL
│   └── analise/      # correlação clima × preço, gráficos
├── notebooks/        # exploração em Jupyter
├── .env.example      # template de variáveis de ambiente
└── requirements.txt
```

## Instalação

```bash
pip install -r requirements.txt
cp .env.example .env   # preencha os tokens no .env
```

## Coleta de dados

```bash
# Fonte mais confiável — sem autenticação
python src/coleta/ibge_ipca.py

# Requer token INMET no .env
python src/coleta/inmet_chuva.py

# Requer conta NASA EarthData no .env
python src/coleta/nasa_ndvi.py
```

## Fontes de dados

| Fonte | Dado | Autenticação |
|---|---|---|
| IBGE SIDRA | IPCA mensal por produto | Não |
| INMET | Precipitação por estação | Token gratuito |
| Open-Meteo | Clima histórico (fallback INMET) | Não |
| NASA AppEEARS | NDVI + precipitação CHIRPS | Conta gratuita |

## Período

Janeiro 2015 a Dezembro 2024
