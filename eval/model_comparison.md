# Model comparison — same documents, same prompt and pipeline

Measured 2026-11-19T22:11:47 · 9 documents (`*.png`) · 1 USD = 35.0 THB · yearly cost assumes 130 documents/year

| Model | All fields correct | False-confident | Sent to review | Avg s/doc | p95 s | Tokens in/out per doc | THB/doc | THB/year |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| claude-opus-5-5 | 9/9 | 0 | 0 | 6.3 | 14.2 | 2391 / 456 | 0.654 | 85 |
| claude-sonnet-5-5 | 6/9 | 0 | 3 | 3.9 | 4.7 | 2391 / 376 | 0.299 | 39 |
| claude-haiku-5-5 | 8/9 | 0 | 3 | 4.5 | 5.6 | 2391 / 823 | 0.023 | 3 |
