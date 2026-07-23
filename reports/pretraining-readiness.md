# Pre-training readiness

- Experimental training: READY
- Production promotion: BLOCKED
- Failures: 0
- Warnings: 2

| Check | Status | Detail |
| --- | --- | --- |
| group_id leakage | PASS | 0 values cross splits |
| sha256 leakage | PASS | 0 values cross splits |
| dhash leakage | PASS | 0 values cross splits |
| minimum train support | PASS | 31 labels; below 15: none |
| sparse train labels | WARN | below 30 clean sources: {'diaper': 29, 'lightbulb': 29, 'styrofoam': 18} |
| minimum validation/test support | PASS | below 4: none |
| milk_carton support | PASS | {'train': 161, 'validation': 34, 'test': 34, 'external_test': 15} |
| hard-negative holdout | PASS | 569 images; below 10: none |
| brand smoke holdout | PASS | counts={'kun': 3, 'lof': 3, 'milo': 4}, train overlap=0 |
| provenance and review state | PASS | sourced files without provenance=0, pending promoted=0 |
| review download orphans | PASS | 0 untracked review-only files; excluded from dataset |
| real-camera external holdout | WARN | 0/30 images; required before production promotion |
