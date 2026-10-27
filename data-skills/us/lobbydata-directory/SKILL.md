---
name: lobbydata-directory
description: >-
  Reference for LobbyData (lobbydata.com), a paid directory of US federal
  lobbying firms, lobbyists, agencies, and issues. Catalogued only: no
  adapter, no public API. Use it to decide whether a manual subscription
  lookup is worth it; Anomaly cannot query it.
metadata:
  author: Buried Signals
  version: "1.0"
  source-id: us/lobbydata/directory
---

# LobbyData (catalogued, not queryable)

Status: **catalogued**. Anomaly has no adapter for this source; loading it
returns `unavailable` with `source-not-queryable`.

## What it is

A commercial site that organises US federal lobbying disclosures into firm,
lobbyist, client, issue, and agency profiles. The free directory
(http://lobbydata.com/Directory) lists firms by name and links agency and
issue listings; detailed reports need payment.

## Access

- Auth: paid account; log in at http://lobbydata.com/Tool.
- Cost (pricing page, 2026-10-27): $29.95 one-time report for one firm,
  agency, or issue (30 days); subscriptions $100/month (1 user), $250/month
  or $3,000/year (3 users), $400/month or $4,800/year (5 users).
- Setup: http://lobbydata.com/Pricing.
- API: none found. Subscribers get export, PDF printing, and email alerts.

## Licence

No data licence or reuse terms were found. Treat exports as for internal
research only and cite the underlying disclosure filings, not LobbyData.

## Limitations

- Single commercial intermediary; the footer reads "©2010" and update
  frequency is unknown.
- The site does not name its source beyond "the entire disclosure
  database". Confirm any finding against the original filings.
- Reports advertise "Estimated Spending Amounts"; treat them as estimates and
  use filed amounts.
