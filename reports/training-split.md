# Duplicate-safe training split

- Source images scanned: 9732
- Images retained: 7267
- Train: 5080
- Validation: 1086
- Internal test: 1086
- External boxed-milk test: 15
- Excluded cross-label exact conflicts: 145
- Excluded cross-label visual conflicts: 15
- Removed within-label visual duplicates: 2305
- Removed duplicates of external holdout: 0

| Label | Train | Validation | Test | External |
| --- | ---: | ---: | ---: | ---: |
| aerosol | 218 | 46 | 46 | 0 |
| apple | 121 | 26 | 26 | 0 |
| banana | 97 | 21 | 21 | 0 |
| battery | 100 | 22 | 22 | 0 |
| bone | 91 | 20 | 20 | 0 |
| book | 75 | 16 | 16 | 0 |
| bottle | 472 | 101 | 101 | 0 |
| bread | 132 | 28 | 28 | 0 |
| cardboard | 444 | 95 | 95 | 0 |
| ceramic | 36 | 8 | 8 | 0 |
| chemical_bottle | 37 | 8 | 8 | 0 |
| chewing_gum | 55 | 12 | 12 | 0 |
| cigarette | 82 | 17 | 17 | 0 |
| coffee | 39 | 8 | 8 | 0 |
| diaper | 29 | 6 | 6 | 0 |
| egg_shell | 96 | 21 | 21 | 0 |
| electronic | 166 | 35 | 35 | 0 |
| glass_bottle | 403 | 87 | 87 | 0 |
| leaf | 115 | 25 | 25 | 0 |
| lightbulb | 29 | 6 | 6 | 0 |
| metal_fork | 156 | 33 | 33 | 0 |
| milk_carton | 161 | 34 | 34 | 15 |
| newspaper | 489 | 105 | 105 | 0 |
| orange | 113 | 24 | 24 | 0 |
| pen | 100 | 21 | 21 | 0 |
| plastic_bag | 358 | 76 | 76 | 0 |
| shampoo_bottle | 55 | 12 | 12 | 0 |
| soda_can | 623 | 133 | 133 | 0 |
| styrofoam | 18 | 4 | 4 | 0 |
| thermometer | 48 | 10 | 10 | 0 |
| wipe | 122 | 26 | 26 | 0 |

All exact/dHash conflicts crossing output labels are excluded. Within-label dHash duplicates are represented once. Images from the same SKU, webcam session, or known download source stay in one split. The latest boxed-milk images stay outside training so the baseline and candidate can be compared on the same data.
