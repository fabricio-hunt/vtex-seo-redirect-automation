# Pasta de Saída de Redirecionamentos (`output/`)

Armazena os arquivos de redirecionamento gerados pela ferramenta.

## Estrutura

- **`output/redirects.csv`**: Arquivo final pronto para importação no VTEX IO (`from;to;type;endDate`), formatado em UTF-8 com BOM (`utf-8-sig`) e contendo apenas destinos 200 OK verificados.
- **`output/redirects_review.csv`**: Diagnóstico completo de auditoria SEO para todas as URLs analisadas (`from;to;type;endDate;match_type;match_score;status_code`).
- **`output/archive/`**: Arquivo histórico de execuções anteriores organizadas por data.

