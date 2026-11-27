# Online safety

For a public demo, `.env` turns on three limits (decision 0015). Each is off when set to 0:

- `RATE_LIMIT_PER_MINUTE` limits each client address on chat, card actions and previews
  (HTTP 429 with `Retry-After`).
- `DAILY_TOKEN_CAP` stops the assistant for the rest of the UTC day once its tokens reach
  the cap. The panel and the cards keep working.
- `DESIGNS_RETENTION_HOURS` deletes generated designs and their renders that many hours
  after their last change, with an audit row for each.

Without Blender, the render card says that renders run on a designer's computer, and the
Renders tab shows the pre-generated [gallery](gallery/) (decision 0006).

The guards that hold whatever the deployment (the confirmation gate, the validators, free
text as data, confined writes) are in the README's
[invariants table](../README.md#the-ai-guides-the-code-decides).
