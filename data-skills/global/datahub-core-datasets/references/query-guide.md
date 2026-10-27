# DataHub Core query guide

1. Call `get-package` first. Record `license`, `last_updated`, and the
   resource names.
2. Call `fetch-resource` with an explicit `resource` and a `limit` up to 1000;
   continue with `offset` = `next_offset` until it is null.
3. Values are strings; apply the field types from the package schema.
4. Cite both DataHub and the upstream publisher named in the description.
