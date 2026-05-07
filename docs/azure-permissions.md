# Azure Permissions

The tool makes read-only API calls. It requires the following roles on **each subscription** being analyzed.

## Required RBAC Roles

| Role | Scope | Purpose |
|---|---|---|
| **Reader** | Subscription | List all resources, read resource metadata and tags |
| **Cost Management Reader** | Subscription | Query daily cost data via Cost Management API |
| **Billing Reader** *(optional)* | Subscription | Read invoice list. If absent, the invoice section is omitted from the report with no error. |

## Assigning Roles (Azure Portal)

1. Go to **Subscriptions** → select the subscription
2. **Access control (IAM)** → **Add role assignment**
3. Role: `Reader` → assign to your Service Principal or user
4. Repeat for `Cost Management Reader`

## Assigning Roles (Azure CLI)

```bash
SUBSCRIPTION_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
SP_OBJECT_ID="yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"   # your SP's object ID

az role assignment create \
  --assignee "$SP_OBJECT_ID" \
  --role "Reader" \
  --scope "/subscriptions/$SUBSCRIPTION_ID"

az role assignment create \
  --assignee "$SP_OBJECT_ID" \
  --role "Cost Management Reader" \
  --scope "/subscriptions/$SUBSCRIPTION_ID"
```

## Creating a Service Principal

```bash
az ad sp create-for-rbac \
  --name "finops-reader" \
  --role "Reader" \
  --scopes "/subscriptions/$SUBSCRIPTION_ID" \
  --sdk-auth
```

Copy the output values into your `.env`:

```
AZURE_TENANT_ID=<tenant>
AZURE_CLIENT_ID=<clientId>
AZURE_CLIENT_SECRET=<clientSecret>
```

## Troubleshooting Permission Errors

If a subscription is skipped with `⚠ Omitida — Insufficient permissions (403)`:

1. Verify the SP or user has both `Reader` and `Cost Management Reader` on that subscription
2. Cost Management data can take up to 24 hours to propagate after role assignment
3. Some subscription types (CSP, MCA) require billing-account-level roles instead of subscription-level — contact your Azure billing admin
