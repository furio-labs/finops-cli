# GCP Support — Setup Guide

`finops` analyzes GCP projects alongside Azure. This guide walks through the one
prerequisite that makes GCP cost analysis possible: enabling **detailed** Cloud
Billing export to BigQuery.

## Why this is required

GCP has **no per-resource cost API**. The Cloud Billing API only returns
billing-account metadata and the SKU/pricing catalog — not what each resource
actually cost. The `idle`, `scheduling`, and other cost-leak detectors need
per-resource daily spend, and the only source for that is the **detailed usage
cost** export to BigQuery, whose table (`gcp_billing_export_resource_v1_*`)
populates the `resource.name` column.

Without this export enabled, `finops` will skip the GCP entry with a clear
message (`Billing export table not found: …`).

> **Data flow.** Resources come from **Cloud Asset Inventory**; per-resource
> costs come from the **BigQuery detailed export**; the two are joined on the
> resource's full name (`//service/…`). GCP invoices are **not** collected —
> there is no comparable programmatic API — but all spend is captured via the
> cost export.

## Prerequisites

- A GCP project whose costs you want to analyze (its **project id**, e.g. `my-gcp-project-123`).
- The **billing account id** the project is linked to (e.g. `0123AB-4567CD-89EF01`).
  Find it in the Console: **Billing → Account management**, or:
  ```bash
  gcloud billing projects describe my-gcp-project-123 --format="value(billingAccountName)"
  ```
- `roles/billing.admin` on the billing account (to enable the export), and
  `roles/owner`/`roles/editor` on the project that will hold the BigQuery dataset.

## Step 1 — Create a BigQuery dataset for the export

Pick (or create) a project and dataset to hold the billing export. In the
Console: **BigQuery → Create dataset**, or:

```bash
bq --location=US mk --dataset my-gcp-project-123:billing_export
```

Note the dataset id (`billing_export` above) — it goes in `subscriptions.yaml`.

## Step 2 — Enable the *detailed* usage cost export

In the Console: **Billing → Billing export → BigQuery export**, then under
**Detailed cost usage** click **Edit settings** and select the project + dataset
from Step 1. **Save.**

> ⚠️ Enable **Detailed cost usage**, not "Standard usage cost". Only the detailed
> export includes the `resource.name` / `resource.global_name` columns that
> per-resource attribution depends on. The table it creates is named
> `gcp_billing_export_resource_v1_<BILLING_ACCOUNT_ID>` (dashes become
> underscores, e.g. `gcp_billing_export_resource_v1_0123AB_4567CD_89EF01`).

> ⏳ The export is **not backfilled** and takes a few hours to begin populating.
> A `finops` run before data lands will simply report `$0` / no findings for
> that project.

## Step 3 — Service account and IAM roles

Create a service account (or reuse one) and grant it:

| Role | Granted on | Purpose |
|------|-----------|---------|
| `roles/cloudasset.viewer` | the analyzed **project** | list resources (Asset Inventory) |
| `roles/bigquery.dataViewer` | the export **dataset** | read the billing export table |
| `roles/bigquery.jobUser` | the BigQuery **project** | run the cost query |

```bash
SA="finops@my-gcp-project-123.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding my-gcp-project-123 \
  --member="serviceAccount:$SA" --role="roles/cloudasset.viewer"
gcloud projects add-iam-policy-binding my-gcp-project-123 \
  --member="serviceAccount:$SA" --role="roles/bigquery.jobUser"
bq add-iam-policy-binding \
  --member="serviceAccount:$SA" --role="roles/bigquery.dataViewer" \
  my-gcp-project-123:billing_export

# Download a key for finops to use:
gcloud iam service-accounts keys create ~/finops-gcp-key.json --iam-account="$SA"
```

Point `finops` at the key via `.env`:

```
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/finops-gcp-key.json
```

If unset, `finops` falls back to Application Default Credentials (`gcloud auth
application-default login`).

## Step 4 — Configure the GCP entry

Add a GCP entry to `subscriptions.yaml` (Azure entries are unchanged; a missing
`provider` still defaults to `azure`):

```yaml
subscriptions:
  - provider: gcp
    id: my-gcp-project-123              # GCP project id
    name: Prod GCP
    billing_account_id: 0123AB-4567CD-89EF01
    billing_export_dataset: billing_export
    # billing_export_table: ""          # optional; defaults to gcp_billing_export_resource_v1_<ACCT>
    # billing_export_project: ""        # optional; defaults to the project id above
    tags:
      environment: production
      client: acme
```

Set `billing_export_project` only if the BigQuery dataset lives in a **different**
project than the one being analyzed.

## Step 5 — Run

```bash
uv run finops run --config subscriptions.yaml
```

`finops` collects resources (Asset Inventory), per-resource costs (BigQuery), runs
the five analyzers, and writes the HTML/Markdown/Excel/JSON reports — Azure and
GCP subscriptions side by side.

## Caveats & limitations

- **Validate the join key on first use.** Costs attach to resources when the
  export's `resource.global_name` equals the Asset Inventory resource id
  (`//service/…`). This is derived from GCP's export schema, not a stable SDK
  contract — confirm that idle/scheduling findings reference real resources on
  your first real run. The join logic is isolated in `_canonical_id`
  (`finops/collectors/gcp/cost.py`) for a one-line fix if the format differs.
- **Partial per-resource coverage.** Not every GCP service emits `resource.name`
  in the export. Spend for services that don't is still counted in totals but is
  bucketed as *unattributable* and won't trigger per-resource detectors (idle,
  scheduling) — the same way Azure Marketplace charges are handled.
- **USD only (v1).** The export is denominated in the billing account's currency.
  A non-USD export causes the entry to be skipped with a clear message rather
  than reported with a wrong currency symbol.
- **No invoices.** GCP invoices are not collected (no comparable API); the
  Invoices section will be empty for GCP subscriptions.

### Validate on the first live run

The GCP collectors are unit-tested with mocks; the following depend on the real
Asset/BigQuery surfaces and schema, so confirm them on your first live run:

- **Asset `read_mask` field paths.** `finops/collectors/gcp/resources.py` requests
  `versioned_resources` (snake_case) in the FieldMask. If a run fails with
  `INVALID_ARGUMENT: … field path`, switch the paths to camelCase
  (`versionedResources`, `additionalAttributes`).
- **The BigQuery cost query.** The SQL (column paths like `resource.global_name`,
  `service.description`, and the `GROUP BY`) is validated only against mocked rows.
  Confirm it runs against your real export table and that costs land on resources.
- **The join key** (see the first caveat above) — the single most important thing
  to eyeball: do idle/scheduling findings point at real resources?
