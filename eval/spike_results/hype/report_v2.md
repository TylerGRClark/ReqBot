# HyPE spike round 2: result

232 queries (35 fragment_hard/ambiguous, 197 others, 46 sealed), 22 gold queries. Only the source row counts as correct, so absolute numbers run low; the paired comparison is the point.

| arm | recall@5 | rise (pts) | 95% interval | recall@10 | MRR | gold p@5 | gold fall | hard rows | other rows | sealed r@5 (A) | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0.267 | +0.0 | +0.0 to +0.0 | 0.315 | 0.193 | 0.200 | +0.0 | +0.0 | +0.0 | 0.348 (0.348) | - |
| B | 0.272 | +0.4 | -3.5 to +3.9 | 0.341 | 0.197 | 0.218 | -1.8 | +2.9 | +0.0 | 0.326 (0.348) | DO NOT BUILD |
| C | 0.267 | +0.0 | -3.9 to +3.5 | 0.332 | 0.191 | 0.218 | -1.8 | +2.9 | -0.5 | 0.348 (0.348) | DO NOT BUILD |
| C2 | 0.267 | +0.0 | -3.9 to +3.5 | 0.332 | 0.189 | 0.209 | -0.9 | +2.9 | -0.5 | 0.348 (0.348) | DO NOT BUILD |

## Newly found / newly lost versus A at recall@5

- B: found 10: Q030, Q044, Q046, Q071, Q098, Q101, Q107, Q126, Q186, Q189; lost 9: Q024, Q055, Q062, Q136, Q168, Q200, Q208, Q210, Q220
- C: found 9: Q030, Q044, Q046, Q071, Q101, Q107, Q126, Q186, Q189; lost 9: Q024, Q062, Q136, Q151, Q168, Q200, Q208, Q210, Q220
- C2: found 9: Q030, Q044, Q046, Q071, Q101, Q107, Q126, Q186, Q189; lost 9: Q024, Q062, Q136, Q151, Q168, Q200, Q208, Q210, Q220

## Per document, recall@5 (A / B / C / C2)

| document | n | A | B | C | C2 |
|---|---|---|---|---|---|
| CJCSI 6510.02G | 12 | 0.42 | 0.33 | 0.33 | 0.33 |
| DODI 5200.01 | 12 | 0.58 | 0.50 | 0.50 | 0.50 |
| DODI 5200.44 | 12 | 0.25 | 0.42 | 0.42 | 0.42 |
| DODI 5200.48 | 22 | 0.27 | 0.36 | 0.32 | 0.32 |
| DODI 8410.03 | 12 | 0.42 | 0.33 | 0.33 | 0.33 |
| DODI 8551.01 | 12 | 0.25 | 0.33 | 0.33 | 0.33 |
| NIST.SP.800-125 | 22 | 0.23 | 0.23 | 0.27 | 0.27 |
| afi10-2402 | 22 | 0.18 | 0.23 | 0.23 | 0.23 |
| afi13-550 | 12 | 0.25 | 0.17 | 0.17 | 0.17 |
| afi17-203 | 18 | 0.11 | 0.11 | 0.11 | 0.11 |
| afman17-2101 | 18 | 0.39 | 0.33 | 0.33 | 0.33 |
| afpd_17-1 | 12 | 0.50 | 0.50 | 0.50 | 0.50 |
| dafi36-2903 | 24 | 0.12 | 0.17 | 0.12 | 0.12 |
| dafman17-1305 | 22 | 0.14 | 0.09 | 0.09 | 0.09 |
