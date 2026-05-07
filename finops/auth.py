from __future__ import annotations
import os
from enum import Enum
from azure.identity import ClientSecretCredential, AzureCliCredential


class AuthMethod(str, Enum):
    SERVICE_PRINCIPAL = "ServicePrincipal"
    AZURE_CLI = "AzureCLI"


def get_credential() -> tuple[object, AuthMethod]:
    tenant = os.getenv("AZURE_TENANT_ID")
    client = os.getenv("AZURE_CLIENT_ID")
    secret = os.getenv("AZURE_CLIENT_SECRET")

    if tenant and client and secret:
        return ClientSecretCredential(
            tenant_id=tenant, client_id=client, client_secret=secret
        ), AuthMethod.SERVICE_PRINCIPAL

    return AzureCliCredential(), AuthMethod.AZURE_CLI
