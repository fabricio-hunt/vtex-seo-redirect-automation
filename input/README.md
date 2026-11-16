# Pasta de Entrada de Relatórios 404 (`input/`)

Esta pasta armazena os relatórios de erros 404 exportados do Google Search Console (GSC) ou de outras fontes para cruzamento contra o feed de produtos.

## Estrutura Recomendada

Organize as exportações em subpastas com data e descrição:

```text
input/
├── 2026-11-05_coverage/
│   └── Tabela.csv
├── 2026-07-28_gsc/
│   └── Tabela.csv
└── legacy_adhoc/
    ├── acoes_404_soft404.csv
    └── webapp404.txt
```

O CLI (`python cli.py`) detecta automaticamente a planilha mais recente em `input/` caso `--input` não seja informado.

