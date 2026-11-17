# H&L mock SAP

A **mock** of an SAP Gateway OData v2 service, `ZHL_MM_MATERIAL_SRV`, for the Bead Studio
demo. It looks up materials (the product master: SKUs and SAP material numbers) and reserves
new ones. It is not a real SAP and contains no SAP code. The company and products are
fictional.

The backend talks to it only through `SapClient` (invariant 5). Pointing `SAP_BASE_URL` at a
real system with a matching service would, in principle, be the only change.

## Run

```bash
cd sap-mock
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8100
pytest -q && ruff check . && ruff format --check .
```

On first start the service creates `DATA_DIR/sap_mock.db` and loads `seed/materials.json`
(25 materials: the 10 products of luna-hybrid-agent and 15 fictional ones).
**To reset the demo, stop the service and delete that file.**

## Configuration

Read from environment variables or the repo's `.env` (see `.env.example`).

| Variable | Default | Meaning |
|---|---|---|
| `SAP_USER` / `SAP_PASSWORD` | `demo` / `demo` | Basic auth credentials the mock accepts (the backend sends the same ones) |
| `DATA_DIR` | `./data` | Folder of `sap_mock.db` (relative paths start at the repo root) |
| `SAP_TODAY` | empty (today) | Pins the date written on new materials (`2026-11-17`) |
| `SAP_LATENCY_MS` | `0` | Delay added to every OData request |
| `SAP_FAIL_RATE` | `0` | Share of OData requests (0–1) answered with 503 |
| `SAP_MAINTENANCE` | `false` | Every OData request answers 503 with `Retry-After` |

The chaos switches run before authentication and before any data is touched, so a failed
request never reserves a number. `/health` needs no auth and ignores them.

## Endpoints

Service root: `/sap/opu/odata/sap/ZHL_MM_MATERIAL_SRV`. All of it needs Basic auth.

| Method and path | What it does |
|---|---|
| `GET /` | Service document; also where clients fetch the CSRF token |
| `GET /$metadata` | EDMX (XML) of the `Material` entity |
| `GET /MaterialSet` | Materials, ordered by SKU. `$filter`, `$top`, `$skip` |
| `GET /MaterialSet('CH-2004')` | One material |
| `POST /MaterialSet` | Reserve the next SKU and material number. Needs the CSRF token |
| `GET /health` | Liveness probe (outside the service, no auth) |

`$filter` supports `<Property> eq '<value>'` clauses joined with `and`, on `MaterialType`
(`GLASS_BEAD`, `CHARM`), `Status` (`IN_DESIGN`, `ACTIVE`, `DISCONTINUED`), `Family`,
`Collection` and `Description`. Anything else is a 400.

**Payloads** follow OData v2 JSON: `{"d": {...}}` for an entity, `{"d": {"results": [...]}}`
for a collection, `__metadata` with the entity's URI and type, dates as `/Date(ms)/`
(UTC midnight), decimals as strings (`"16.0"`), and `""` for empty strings, as ABAP has no
null strings. Material numbers always have 18 digits (`000000000050000103`); screens and the
drawing title block drop the leading zeros.

**Reserving a SKU.** The body is
`{"MaterialType", "Description", "CreatedBy", "Family"?, "Collection"?}`; other fields are
ignored because SAP issues them. In one SQLite transaction the mock takes:

- the next SKU of the material type's number range: `GB-1034` for the first glass bead and
  `CH-2034` for the first charm on the seed data. Numbers continue after the highest one
  ever issued, so seeded SKUs and gaps are never reissued, also after a failure;
- the next material number (`000000000050000134` first), shared by both types;
- status `IN_DESIGN` and revision `A`, dated today.

It answers `201 Created` with the new material and a `Location` header. SAP checks its own
domain values (material type, family for the type, collection). The product name is stored
as sent: the company naming rules (`GEN-03` in the Product Design Manual) are checked by the
backend before it calls SAP.

## Try it with curl

Use a POSIX shell (Git Bash on Windows; in PowerShell call `curl.exe`, not `curl`).

```bash
SAP=http://localhost:8100/sap/opu/odata/sap/ZHL_MM_MATERIAL_SRV

# Look up the best seller
curl -s -u demo:demo "$SAP/MaterialSet('CH-2004')?\$format=json"

# All charms (-G with --data-urlencode encodes the spaces and quotes)
curl -s -u demo:demo -G "$SAP/MaterialSet" --data-urlencode "\$filter=MaterialType eq 'CHARM'"

# Filter and page
curl -s -u demo:demo -G "$SAP/MaterialSet" \
  --data-urlencode "\$filter=MaterialType eq 'GLASS_BEAD' and Status eq 'ACTIVE'" \
  --data-urlencode '$top=3'

# The service description
curl -s -u demo:demo "$SAP/\$metadata"
```

Reserving a SKU takes the CSRF handshake, like a real Gateway: fetch a token with a GET,
keep the session cookie, and send both with the POST.

```bash
# 1. Fetch the token; the cookie jar keeps the session cookie
TOKEN=$(curl -s -u demo:demo -c jar.txt -D - -o /dev/null -H "x-csrf-token: Fetch" "$SAP/" \
  | tr -d '\r' | awk -F': ' 'tolower($1)=="x-csrf-token" {print $2}')

# 2. Reserve: 201 Created, Location: .../MaterialSet('GB-1034')
curl -s -i -u demo:demo -b jar.txt -X POST "$SAP/MaterialSet" \
  -H "x-csrf-token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"MaterialType": "GLASS_BEAD", "Description": "Honey Glow Faceted",
       "Family": "FAC", "Collection": "Amber Hollow", "CreatedBy": "Product Design"}'
```

And the failures:

```bash
curl -s -i "$SAP/MaterialSet"                                    # 401, no credentials
curl -s -i -u demo:demo -X POST "$SAP/MaterialSet" -d '{}'       # 403, x-csrf-token: Required
curl -s -i -u demo:demo "$SAP/MaterialSet('GB-1999')"            # 404, ZHL_MM/001
SAP_MAINTENANCE=true uvicorn app.main:app --port 8100            # then any call: 503
```

## Errors

Every error uses the SAP Gateway error body:

```json
{"error": {"code": "ZHL_MM/001",
           "message": {"lang": "en", "value": "Material GB-1999 does not exist"},
           "innererror": {"transactionid": "…", "timestamp": "20261117093000",
                          "errordetails": [{"code": "ZHL_MM/001", "message": "…",
                                            "severity": "error", "target": ""}]}}}
```

| Status | Code | When |
|---|---|---|
| 401 | `ZHL_GW/001` | Missing or wrong Basic credentials (`WWW-Authenticate` is set) |
| 403 | `ZHL_GW/002` | Modifying request without a valid CSRF token and session (`x-csrf-token: Required`) |
| 503 | `ZHL_GW/003` | `SAP_MAINTENANCE` is on (`Retry-After: 300`) |
| 503 | `ZHL_GW/004` | Random failure from `SAP_FAIL_RATE` |
| 400 | `ZHL_GW/005` | Invalid request: body, `$filter`, `$format` |
| 404 | `ZHL_GW/006` | Unknown path in the service |
| 404 | `ZHL_MM/001` | The material (SKU) does not exist |
| 400 | `ZHL_MM/010` | Unknown material type |
| 400 | `ZHL_MM/011` | Family not valid for the material type |
| 400 | `ZHL_MM/012` | Unknown collection |
| 400 | `ZHL_MM/013` | SKU number range exhausted (GB-1999, CH-2999) |
| 400 | `ZHL_MM/014` | Material number range exhausted (59999999) |

The codes and message classes are invented for the mock.
