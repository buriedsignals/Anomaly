# TED procurement query guide

## Choose a query form

Use shortcuts for a simple category/location search:

```json
{"cpv":"72000000","country":"DE","only_latest_versions":true,"limit":10,"page":1}
```

Use `query` for exact documented TED expert fields and boolean logic. Preserve
the expert string verbatim in notes so results are reproducible.

## CPV discipline

CPV codes are hierarchical. A broad division can include many goods and
services; a narrow code can miss notices classified only at a parent. Record
the code and label, and test parent/child variants only as separate scopes.

## Notice-to-contract evidence chain

1. Search notice metadata and preserve publication number.
2. Open the full TED notice.
3. Identify notice form, procedure, lots, buyer, dates, and whether it is a
   planning, competition, result, change, or other notice.
4. For an award claim, locate the result notice and exact lot, winner, amount,
   currency, and contract date.
5. Check later change/cancellation notices and primary buyer records.

A competition notice is not proof of award. A result notice is not necessarily
proof of contract execution or payment.

## No-result recovery

1. Validate expert syntax and country/CPV codes.
2. Check `scope` and `only_latest_versions`.
3. Broaden one boolean clause or move one level up the CPV hierarchy.
4. Remove country only when cross-border buyer scope is intended.
5. Report exact query, scope, page, version setting, date searched, and total.

## Large result sets

Page-number mode stops at 15,000 retrievable notices. Do not present that slice
as complete when the total is larger. Iteration mode and XML bulk retrieval are
documented provider workflows but not released Navigator operations.

## Reporting checklist

- Preserve publication number and TED link.
- State expert query/shortcuts, scope, version flag, page, and search date.
- Identify notice type and lot before describing an award.
- Verify winner, value, currency, and dates in the full notice and buyer record.
- State multilingual fallback and pagination limitations.
