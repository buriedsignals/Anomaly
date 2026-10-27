# Party Facts query guide

1. Search by the party's English or original-language name and add the
   alpha-3 `country` to cut false matches. `q` is a case-insensitive
   substring across `name`, `name_short`, `name_english`, and `name_other`.
2. Disambiguate candidates by `year_first`/`year_last` and `country`.
   Identical names used by different parties carry the first year in the
   English name (codebook "Party names").
3. Call `list-external-links` with the chosen `partyfacts_id`. Join the
   external dataset on `dataset_key` (e.g. `parlgov`, `manifesto`) and
   `dataset_party_id`.
4. Check party changes and alliances before joining across periods: a
   successor party has its own ID.
5. Record the run date; the live tables change as users edit them.
