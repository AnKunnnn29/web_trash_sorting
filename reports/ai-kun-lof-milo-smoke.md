# KUN / LOF / MILO carton smoke test

> Product-page images collected after training. They are useful for a packaging smoke test but do not replace real camera photos.

- Unique images: 10
- Expected output: `milk_carton`
- Acceptance threshold: 45%

## Summary

| Model | Brand | Correct | Accepted | Predictions |
| --- | --- | ---: | ---: | --- |
| baseline | KUN | 1/3 (33.3%) | 1/3 | battery: 1, milk_carton: 1, newspaper: 1 |
| baseline | LOF | 1/3 (33.3%) | 0/3 | metal_fork: 1, milk_carton: 1, shampoo_bottle: 1 |
| baseline | MILO | 0/4 (0.0%) | 0/4 | battery: 1, leaf: 1, newspaper: 1, shampoo_bottle: 1 |
| E4-best-seed | KUN | 0/3 (0.0%) | 2/3 | newspaper: 3 |
| E4-best-seed | LOF | 0/3 (0.0%) | 0/3 | bread: 2, soda_can: 1 |
| E4-best-seed | MILO | 1/4 (25.0%) | 0/4 | milk_carton: 1, newspaper: 3 |
| E4-refresh-20260726 | KUN | 2/3 (66.7%) | 3/3 | milk_carton: 2, newspaper: 1 |
| E4-refresh-20260726 | LOF | 3/3 (100.0%) | 1/3 | milk_carton: 3 |
| E4-refresh-20260726 | MILO | 3/4 (75.0%) | 1/4 | milk_carton: 3, soda_can: 1 |

## Per-image baseline results

| Brand | Image | Top-1 | Confidence | Top-2 |
| --- | --- | --- | ---: | --- |
| KUN | `01.png` | milk_carton | 40.1% | newspaper (39.8%) |
| KUN | `03.jpg` | newspaper | 59.0% | battery (6.7%) |
| KUN | `04.jpg` | battery | 21.7% | newspaper (17.5%) |
| LOF | `01.png` | milk_carton | 22.5% | cardboard (17.4%) |
| LOF | `02.png` | metal_fork | 12.0% | egg_shell (10.1%) |
| LOF | `03.jpg` | shampoo_bottle | 34.6% | milk_carton (23.2%) |
| MILO | `01.jpg` | newspaper | 31.2% | soda_can (17.9%) |
| MILO | `02.jpg` | leaf | 20.4% | aerosol (11.5%) |
| MILO | `03.jpg` | battery | 22.0% | thermometer (20.8%) |
| MILO | `04.jpg` | shampoo_bottle | 22.3% | battery (16.6%) |

## Sources

- KUN: <https://www.lof.vn/vi/brand/kun?type=5>, <https://www.bachhoaxanh.com/sua-tuoi/thung-48-hop-sua-tuoi-tiet-trung-it-duong-lof-kun-100-sua-tuoi-180ml>, <https://30day.com.vn/sua-kun-100-tuoi-it-duong-180ml>
- LOF: <https://www.lof.vn/en/brand/lof>, <https://www.bachhoaxanh.com/sua-ca-cao-socola/sua-lua-mach-huong-socola-bac-ha-lof-malto-hop-180ml>
- MILO: <https://www.kidsplaza.vn/loc-4-hop-sua-milo-active-go-180ml-cho-be-tren-6-tuoi.html>, <https://www.bachhoaxanh.com/sua-ca-cao-socola/hop-thuc-uong-lua-mach-uong-lien-milo-hop-180ml/>

The application classifies packaging/material, not brand identity. Therefore KUN, LOF and MILO cartons are correct only when the output is `milk_carton`.
