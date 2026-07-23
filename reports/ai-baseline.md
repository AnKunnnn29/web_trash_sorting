# AI baseline smoke benchmark

> Images come from the repository dataset and may overlap training data. Do not treat these metrics as independent release accuracy.

- Samples: 310
- Top-1 accuracy: 68.4%
- Macro F1: 66.4%
- Coverage at threshold 45%: 65.5%
- Accuracy among accepted predictions: 84.2%
- Average confidence: 61.8%

## Per-label metrics

| Label | Samples | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| aerosol | 10 | 83.3% | 50.0% | 62.5% |
| apple | 10 | 81.8% | 90.0% | 85.7% |
| banana | 10 | 76.9% | 100.0% | 87.0% |
| battery | 10 | 50.0% | 100.0% | 66.7% |
| bone | 10 | 62.5% | 50.0% | 55.6% |
| book | 10 | 66.7% | 100.0% | 80.0% |
| bottle | 10 | 100.0% | 40.0% | 57.1% |
| bread | 10 | 40.0% | 20.0% | 26.7% |
| cardboard | 10 | 66.7% | 60.0% | 63.2% |
| ceramic | 10 | 75.0% | 90.0% | 81.8% |
| chemical_bottle | 10 | 53.3% | 80.0% | 64.0% |
| chewing_gum | 10 | 80.0% | 40.0% | 53.3% |
| cigarette | 10 | 72.7% | 80.0% | 76.2% |
| coffee | 10 | 100.0% | 90.0% | 94.7% |
| diaper | 10 | 83.3% | 100.0% | 90.9% |
| egg_shell | 10 | 80.0% | 80.0% | 80.0% |
| electronic | 10 | 61.5% | 80.0% | 69.6% |
| glass_bottle | 10 | 66.7% | 60.0% | 63.2% |
| leaf | 10 | 60.0% | 90.0% | 72.0% |
| lightbulb | 10 | 81.8% | 90.0% | 85.7% |
| metal_fork | 10 | 70.0% | 70.0% | 70.0% |
| milk_carton | 10 | 40.0% | 40.0% | 40.0% |
| newspaper | 10 | 41.2% | 70.0% | 51.9% |
| orange | 10 | 88.9% | 80.0% | 84.2% |
| pen | 10 | 50.0% | 20.0% | 28.6% |
| plastic_bag | 10 | 100.0% | 20.0% | 33.3% |
| shampoo_bottle | 10 | 70.0% | 70.0% | 70.0% |
| soda_can | 10 | 66.7% | 60.0% | 63.2% |
| styrofoam | 10 | 81.8% | 90.0% | 85.7% |
| thermometer | 10 | 90.0% | 90.0% | 90.0% |
| wipe | 10 | 40.0% | 20.0% | 26.7% |

## Most common confusions

| Expected | Predicted | Count |
|---|---|---:|
| plastic_bag | newspaper | 3 |
| aerosol | chemical_bottle | 2 |
| bone | bread | 2 |
| bread | milk_carton | 2 |
| chewing_gum | leaf | 2 |
| chewing_gum | cigarette | 2 |
| glass_bottle | chemical_bottle | 2 |
| glass_bottle | soda_can | 2 |
| milk_carton | newspaper | 2 |
| newspaper | milk_carton | 2 |
| pen | battery | 2 |
| plastic_bag | battery | 2 |
| shampoo_bottle | chemical_bottle | 2 |
| soda_can | glass_bottle | 2 |
| wipe | battery | 2 |
