"""AWS provider: a boto3 Session (env creds, shared credentials file, or an
assumed role for cross-account access) shared by Cost Explorer, EC2, and the
Resource Groups Tagging API clients."""
from __future__ import annotations
import os

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from finops.providers import ProviderPermissionError, ProviderUnavailableError


def build_credential(entry):
    """Return (boto3.Session, auth_method_label). `entry.role_arn`, if set, is
    assumed via STS so a single set of ambient credentials can reach many AWS
    accounts (the common multi-account FinOps setup)."""
    region = entry.region
    try:
        if entry.role_arn:
            base_session = boto3.Session(region_name=region)
            sts = base_session.client("sts")
            resp = sts.assume_role(
                RoleArn=entry.role_arn,
                RoleSessionName="finops-cli",
            )
            creds = resp["Credentials"]
            session = boto3.Session(
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
                region_name=region,
            )
            return session, "AssumeRole"

        if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            return boto3.Session(region_name=region), "AccessKey"

        return boto3.Session(region_name=region), "DefaultChain"
    except (ClientError, BotoCoreError) as exc:
        raise ProviderUnavailableError(f"AWS auth failed: {exc}") from exc


def build_collectors(entry, credential):
    """Return (resource_collector, cost_collector, invoice_collector) for AWS."""
    from finops.collectors.aws.resources import ResourceCollector
    from finops.collectors.aws.cost import CostCollector
    from finops.collectors.aws.invoices import InvoiceCollector
    return (
        ResourceCollector(credential, entry),
        CostCollector(credential, entry),
        InvoiceCollector(credential),
    )
