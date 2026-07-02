"""Provider dispatch: given a config entry, build the credential and the three
collectors for its cloud. The three `collect()` signatures are the interface,
so no ABC is needed — just a factory keyed on `entry.provider`.

Collectors raise a common exception taxonomy so the CLI can handle every
provider uniformly:
  - ProviderPermissionError  -> the entry is skipped ("sin permisos")
  - ProviderUnavailableError -> the entry is skipped with a specific reason
"""
from __future__ import annotations


class ProviderError(Exception):
    """Base class for provider-level failures that should skip an entry."""


class ProviderPermissionError(ProviderError):
    """Credentials lack permission for this account/project (skip)."""


class ProviderUnavailableError(ProviderError):
    """A prerequisite is missing/unreachable (bad export table, auth, etc.)."""


def get_credential(entry):
    """Return (credential, auth_method_label) for the entry's provider."""
    if entry.provider == "gcp":
        from finops.providers import gcp
        return gcp.build_credential(entry)
    if entry.provider == "aws":
        from finops.providers import aws
        return aws.build_credential(entry)
    from finops.providers import azure
    return azure.build_credential(entry)


def get_collectors(entry, credential):
    """Return (resource_collector, cost_collector, invoice_collector)."""
    if entry.provider == "gcp":
        from finops.providers import gcp
        return gcp.build_collectors(entry, credential)
    if entry.provider == "aws":
        from finops.providers import aws
        return aws.build_collectors(entry, credential)
    from finops.providers import azure
    return azure.build_collectors(entry, credential)
