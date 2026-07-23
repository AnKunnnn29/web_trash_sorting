# E4 refresh evaluation — 2026-07-26

## Decision

Do not replace the current production baseline. The refreshed candidate improves
boxed-milk external recognition and brand smoke results, but fails the global
quality gate and lowers internal `milk_carton` precision/recall/F1.

## Comparable clean-split results

| Metric | Baseline | E4 refresh | Delta |
| --- | ---: | ---: | ---: |
| Test accuracy | 62.89% | 54.79% | -8.10 pp |
| Test macro F1 | 60.23% | 43.74% | -16.49 pp |
| `milk_carton` precision | 47.73% | 34.62% | -13.11 pp |
| `milk_carton` recall | 61.76% | 52.94% | -8.82 pp |
| `milk_carton` F1 | 53.85% | 41.86% | -11.99 pp |
| External boxed-milk accuracy | 40.00% | 100.00% | +60.00 pp |
| External coverage at 45% | 26.67% | 86.67% | +60.00 pp |
| External accepted accuracy | 0.00% | 100.00% | +100.00 pp |

## KUN / LOF / MILO smoke test

| Brand | Baseline raw top-1 | E4 refresh raw top-1 | E4 accepted result |
| --- | ---: | ---: | --- |
| KUN | 1/3 | 2/3 | 2/3 correct; one confident false positive |
| LOF | 1/3 | 3/3 | 1/1 accepted correct |
| MILO | 0/4 | 3/4 | 0/1 accepted correct; accepted error was `soda_can` |

The ten product-page samples are a smoke test, not an unbiased accuracy set.
Real-camera images from unseen products remain necessary.

## Training behavior

- CPU training time: 14.61 minutes.
- Best validation accuracy: 56.63%.
- Best validation loss: 1.8827.
- Final training accuracy: 72.84%.
- The growing train/validation gap indicates moderate overfitting.
- Learning-rate reduction, augmentation, L2, dropout, label smoothing and
  best-weight restoration operated as configured.

## Next data action

Keep the baseline. Add real-camera cartons and hard negatives for
`newspaper`, `cardboard`, `soda_can`, `battery`, `leaf`, and
`shampoo_bottle`; group all views of one SKU/source into the same split. Train
another candidate only after expanding this targeted set.
