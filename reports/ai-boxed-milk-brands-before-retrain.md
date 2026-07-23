# AI baseline smoke benchmark

> Images are newly collected, manually approved product images from the provenance manifest. They were not added until after the baseline model was trained, but are not a substitute for an independent camera test set.

- Samples: 15
- Top-1 accuracy: 33.3%
- Macro F1: 50.0%
- Coverage at threshold 45%: 33.3%
- Accuracy among accepted predictions: 0.0%
- Average confidence: 44.4%

## Per-label metrics

| Label | Samples | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| aerosol | 0 | 0.0% | 0.0% | 0.0% |
| apple | 0 | 0.0% | 0.0% | 0.0% |
| banana | 0 | 0.0% | 0.0% | 0.0% |
| battery | 0 | 0.0% | 0.0% | 0.0% |
| bone | 0 | 0.0% | 0.0% | 0.0% |
| book | 0 | 0.0% | 0.0% | 0.0% |
| bottle | 0 | 0.0% | 0.0% | 0.0% |
| bread | 0 | 0.0% | 0.0% | 0.0% |
| cardboard | 0 | 0.0% | 0.0% | 0.0% |
| ceramic | 0 | 0.0% | 0.0% | 0.0% |
| chemical_bottle | 0 | 0.0% | 0.0% | 0.0% |
| chewing_gum | 0 | 0.0% | 0.0% | 0.0% |
| cigarette | 0 | 0.0% | 0.0% | 0.0% |
| coffee | 0 | 0.0% | 0.0% | 0.0% |
| diaper | 0 | 0.0% | 0.0% | 0.0% |
| egg_shell | 0 | 0.0% | 0.0% | 0.0% |
| electronic | 0 | 0.0% | 0.0% | 0.0% |
| glass_bottle | 0 | 0.0% | 0.0% | 0.0% |
| leaf | 0 | 0.0% | 0.0% | 0.0% |
| lightbulb | 0 | 0.0% | 0.0% | 0.0% |
| metal_fork | 0 | 0.0% | 0.0% | 0.0% |
| milk_carton | 15 | 100.0% | 33.3% | 50.0% |
| newspaper | 0 | 0.0% | 0.0% | 0.0% |
| orange | 0 | 0.0% | 0.0% | 0.0% |
| pen | 0 | 0.0% | 0.0% | 0.0% |
| plastic_bag | 0 | 0.0% | 0.0% | 0.0% |
| shampoo_bottle | 0 | 0.0% | 0.0% | 0.0% |
| soda_can | 0 | 0.0% | 0.0% | 0.0% |
| styrofoam | 0 | 0.0% | 0.0% | 0.0% |
| thermometer | 0 | 0.0% | 0.0% | 0.0% |
| wipe | 0 | 0.0% | 0.0% | 0.0% |

## Most common confusions

| Expected | Predicted | Count |
|---|---|---:|
| milk_carton | shampoo_bottle | 4 |
| milk_carton | soda_can | 4 |
| milk_carton | battery | 1 |
| milk_carton | cardboard | 1 |
