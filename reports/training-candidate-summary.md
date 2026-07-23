# Candidate training summary

- Decision: **KEEP baseline**
- Scope: local data/model work only; no hardware or deployment.

## Experiment comparison

| Model | Seeds | Test accuracy | Test macro F1 | External milk recall |
| --- | ---: | ---: | ---: | ---: |
| Current-split baseline | 1 | 61.0% | 59.0% | 33.3% |
| E4: L2 + Dropout 0.3 + smoothing 0.05 | 3 | 55.0% | 44.8% ± 0.8% | 97.8% ± 3.1% |

## E4 seeds

| Seed | Test accuracy | Macro F1 | External milk recall |
| ---: | ---: | ---: | ---: |
| 20260727 | 55.6% | 45.4% | 100.0% |
| 20260728 | 54.2% | 43.7% | 93.3% |
| 20260729 | 55.1% | 45.5% | 100.0% |

## Mean recall for critical labels (E4)

| Label | Recall |
| --- | ---: |
| milk_carton | 64.7% |
| bottle | 60.1% |
| bread | 51.2% |
| wipe | 23.1% |
| pen | 42.9% |
| plastic_bag | 36.0% |
| styrofoam | 0.0% |

## Quality gate

| Gate | Result |
| --- | --- |
| three_current_split_seeds | PASS |
| accuracy_not_below_baseline | FAIL |
| macro_f1_not_below_baseline | FAIL |
| macro_f1_std_le_2pp | PASS |
| external_milk_recall_ge_75 | PASS |
| external_accepted_accuracy_ge_90 | PASS |
| external_coverage_ge_60 | PASS |
| external_std_le_2pp | FAIL |
| milk_carton_f1_not_below_baseline | PASS |

Only metrics matching current split SHA-256 `21b97193a87022a5e1e6576901cc4e759dd4fc902ec7cec3e09c61a6dac38267` are included. The baseline internal-test score remains a regression reference because the old model may have seen some source images. The 15 boxed-milk images, brand smoke holdout, hard negatives and real-camera holdout are separate gates.

No production model files are replaced when any mandatory gate fails.
