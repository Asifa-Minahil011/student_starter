# Behaviour Table (derived from requirements.md)

## A. State x Operation table

| # | State | Operation | Condition | Accepted? | Next state | Data change | Rule # |
|---|-------|-----------|-----------|-----------|------------|-------------|--------|
| 1 | AVAILABLE | RESERVE | none | Yes | RESERVED | set customer_id, reservation_code = R-<cid> | 1, 2 |
| 2 | AVAILABLE | CANCEL | none | No | AVAILABLE | none | 3, 12 |
| 3 | AVAILABLE | DEPOSIT | any code | No | AVAILABLE | none | 4, 12 |
| 4 | AVAILABLE | RETRIEVE | any code | No | AVAILABLE | none | 6, 12 |
| 5 | AVAILABLE | EXPIRE | any flag | No | AVAILABLE | none | 8, 12 |
| 6 | AVAILABLE | DISABLE | none | Yes | MAINTENANCE | none | 9 |
| 7 | AVAILABLE | ENABLE | none | No | AVAILABLE | none | 10, 12 |
| 8 | AVAILABLE | INVALID_ACCESS | none | No | AVAILABLE | none | 11, 12 |
| 9 | RESERVED | RESERVE | none | No | RESERVED | none | 1, 12 |
| 10 | RESERVED | CANCEL | none | Yes | AVAILABLE | clear customer_id, reservation_code, retrieval_code | 3 |
| 11 | RESERVED | DEPOSIT | see section B | see B | see B | see B | 4, 5 |
| 12 | RESERVED | RETRIEVE | any code | No | RESERVED | none | 6, 12 |
| 13 | RESERVED | EXPIRE | see section B | see B | see B | see B | 8 |
| 14 | RESERVED | DISABLE | none | No | RESERVED | none | 9, 12 |
| 15 | RESERVED | ENABLE | none | No | RESERVED | none | 10, 12 |
| 16 | RESERVED | INVALID_ACCESS | none | No | RESERVED | none | 11, 12 |
| 17 | OCCUPIED | RESERVE | none | No | OCCUPIED | none | 1, 12 |
| 18 | OCCUPIED | CANCEL | none | No | OCCUPIED | none | 3, 12 |
| 19 | OCCUPIED | DEPOSIT | any code | No | OCCUPIED | none | 4, 12 |
| 20 | OCCUPIED | RETRIEVE | see section B | see B | see B | see B | 6, 7 |
| 21 | OCCUPIED | EXPIRE | any flag | No | OCCUPIED | none | 8, 12 |
| 22 | OCCUPIED | DISABLE | none | No | OCCUPIED | none | 9, 12 |
| 23 | OCCUPIED | ENABLE | none | No | OCCUPIED | none | 10, 12 |
| 24 | OCCUPIED | INVALID_ACCESS | none | No | OCCUPIED | none | 11, 12 |
| 25 | MAINTENANCE | RESERVE | none | No | MAINTENANCE | none | 1, 12 |
| 26 | MAINTENANCE | CANCEL | none | No | MAINTENANCE | none | 3, 12 |
| 27 | MAINTENANCE | DEPOSIT | any code | No | MAINTENANCE | none | 4, 12 |
| 28 | MAINTENANCE | RETRIEVE | any code | No | MAINTENANCE | none | 6, 12 |
| 29 | MAINTENANCE | EXPIRE | any flag | No | MAINTENANCE | none | 8, 12 |
| 30 | MAINTENANCE | DISABLE | none | No | MAINTENANCE | none | 9, 12 |
| 31 | MAINTENANCE | ENABLE | none | Yes | AVAILABLE | none | 10 |
| 32 | MAINTENANCE | INVALID_ACCESS | none | No | MAINTENANCE | none | 11, 12 |

## B. Rows where a guard splits the outcome

| State | Operation | Condition | Accepted? | Next state | Data change | Rule # |
|-------|-----------|-----------|-----------|------------|-------------|--------|
| RESERVED | DEPOSIT | code == R-<cid> | Yes | OCCUPIED | set retrieval_code = P-<cid> | 4, 5 |
| RESERVED | DEPOSIT | wrong code | No | RESERVED | none | 4, 12 |
| OCCUPIED | RETRIEVE | code == P-<cid> | Yes | AVAILABLE | clear all data | 6, 7 |
| OCCUPIED | RETRIEVE | wrong code | No | OCCUPIED | none | 6, 12 |
| RESERVED | EXPIRE | expired=True | Yes | AVAILABLE | clear all data | 8 |
| RESERVED | EXPIRE | expired=False | No | RESERVED | none | 8, 12 |

Total distinct transitions: 32 state/operation pairs + 3 extra guard splits = 35
(7 accepted, 28 rejected).

## C. Assumptions

1. DISABLE while RESERVED or OCCUPIED is rejected. Rule 9 allows it only in AVAILABLE,
   and this also prevents a parcel or reservation being stranded in maintenance.
2. CANCEL while OCCUPIED is rejected. Rule 3 allows it only in RESERVED
   (a deposited parcel must be retrieved, not cancelled).
3. CANCEL clears customer_id and all codes. The requirements only say it returns
   to AVAILABLE, so this is an assumption consistent with Rules 7 and 8.
4. Customer ID is not validated. Any string, including empty, is accepted by RESERVE.
5. Message strings are not specified in requirements.md. The oracle compares the
   `accepted` flag and the full snapshot strictly. Message text is not compared.
6. After DEPOSIT, customer_id and reservation_code are kept (OCCUPIED holds
   customer_id, R-<cid> and P-<cid>). The requirements are silent on this.
7. INVALID_ACCESS is rejected in every state and never changes anything (Rules 11, 12).
8. The `expired` flag is only meaningful for EXPIRE. For all other operations it is ignored.
9. A DEPOSIT code that is the retrieval-style code (P-<cid>) is a wrong code.

## D. Invariants

1. In AVAILABLE and MAINTENANCE: customer_id, reservation_code and retrieval_code are all None.
2. In RESERVED: customer_id is set, reservation_code == "R-" + customer_id, retrieval_code is None.
3. In OCCUPIED: customer_id is set, reservation_code == "R-" + customer_id,
   retrieval_code == "P-" + customer_id.
4. After a successful RETRIEVE, CANCEL or EXPIRE, the locker is AVAILABLE and the snapshot is completely empty.
5. A rejected operation leaves the snapshot unchanged (Rule 12).
6. The state is always one of the four defined states.