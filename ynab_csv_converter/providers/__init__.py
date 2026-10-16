"""Registry of supported banks and export formats.

To add one: create a module exposing `provider = Provider(...)` and list it here.
"""

from . import sparekassen
from .base import Provider

PROVIDERS: dict[str, Provider] = {
    module.provider.key: module.provider
    for module in [
        sparekassen,
    ]
}


def get_provider(key: str) -> Provider:
    try:
        return PROVIDERS[key]
    except KeyError:
        known = ", ".join(sorted(PROVIDERS))
        raise KeyError(f"Unknown format {key!r}. Known formats: {known}") from None
