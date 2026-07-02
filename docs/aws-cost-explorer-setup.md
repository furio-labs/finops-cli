# AWS Cost Explorer setup

`finops` reads AWS cost data from Cost Explorer (`ce:GetCostAndUsage`) and
resource inventory from the Resource Groups Tagging API. Neither requires a
billing export bucket, unlike the GCP integration.

## 1. Enable Cost Explorer

Cost Explorer must be enabled once per payer account: AWS Console → Billing
and Cost Management → Cost Explorer → **Enable Cost Explorer**. Historical
data becomes queryable ~24h after enabling.

## 2. IAM permissions

Attach a policy like this to the credentials `finops` uses (an IAM user,
role, or the role in `role_arn` if using cross-account access):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "tag:GetResources"
      ],
      "Resource": "*"
    }
  ]
}
```

If using `role_arn` for a member account in an AWS Organization, the calling
identity also needs `sts:AssumeRole` on that role, and the role's trust
policy must allow the calling account/identity.

## 3. Credentials

`finops` uses the default boto3 credential chain (env vars, shared
`~/.aws/credentials`, instance/task role, etc.). Set `AWS_ACCESS_KEY_ID` /
`AWS_SECRET_ACCESS_KEY` in `.env` for a static key pair, or leave them unset
to use ambient credentials (e.g. `aws sso login`, an EC2 instance profile).

For multi-account setups, set `role_arn` per entry in `subscriptions.yaml`
instead of managing separate credentials per account — `finops` will call
`sts:AssumeRole` using the ambient credentials as the trust anchor.

## 4. Known limitation: no per-resource cost

Cost Explorer's standard API reports cost per AWS *service*, not per
resource (there's no AWS equivalent of Azure Cost Management's per-resource
breakdown or GCP's per-resource BigQuery billing export). Costs are
collected per-service and bucketed as `aws:unattributed/{service}` — this
means the `idle` and `scheduling` analyzers, which join cost data to a
specific resource, currently produce no findings for AWS resources. `wrong_sku`
similarly needs an instance type the Resource Groups Tagging API doesn't
return, so it has no AWS checks yet. `untagged` (tag compliance) works fully,
since it only needs resource + tag data.
