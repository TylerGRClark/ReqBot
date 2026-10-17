# HyPE spike result

Verdict (pre-registered rule): **DO NOT BUILD**

- Miss set (15 queries): recall@5 A 0.467 -> B 0.533 (+6.7 points; need at least +15): NOT met
- Gold set (22 queries with live labels): precision@5 A 0.200 -> B 0.218 (fell -1.8 points; allowed at most 2): met
- Questions: 13095 kept, 217 rejected as ungrounded or bad, for 4427 of 4462 records
- Scratch collection: grc_hype_spike_20261013_173015

## Miss set, per query (rank of the target record in the top 20; `q` = reached through a generated question)

| query | A rank | B rank | gain via question |
|---|---|---|---|
| H-M01 | - | - |  |
| H-M02 | - | 16 | q |
| H-M03 | 1 | 1 |  |
| H-M04 | - | - |  |
| H-M05 | 1 | 1 |  |
| H-M06 | 1 | 1 |  |
| H-M07 | 1 | 1 |  |
| H-M08 | 1 | 1 |  |
| H-M09 | 2 | 2 |  |
| H-F01 | - | - |  |
| H-F02 | - | - |  |
| H-F03 | 14 | 9 | q |
| H-F04 | 8 | 10 |  |
| H-F05 | 6 | 1 | q |
| H-F06 | 1 | 1 |  |

## Gold set, queries whose precision@5 differs

| query | A | B |
|---|---|---|
| Q-B01 | 0.00 | 0.20 |
| Q-B03 | 0.20 | 0.40 |
| Q-B04 | 0.00 | 0.20 |
| Q-B05 | 0.00 | 0.20 |
| Q-N08 | 0.20 | 0.00 |
| Q-B08 | 0.40 | 0.20 |
