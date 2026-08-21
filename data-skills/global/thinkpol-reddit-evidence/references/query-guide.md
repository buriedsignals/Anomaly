# ThinkPol query guide

Use `q` for one term or `terms` for multiple case-insensitive AND terms. Set
`content_type` to `comment` or `submission` when needed, and use non-negative
`from` and `to` Unix timestamps for a bounded interval.

Record the exact query and treat an empty response as a bounded search result,
not as proof that no matching Reddit content exists.
