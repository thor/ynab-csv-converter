"""Registry of supported banks and export formats.

To add one: create a module exposing `provider = Provider(...)` and list it here.
"""

from . import (
    americanexpress,
    banknordik,
    banknorwegian,
    danskebank,
    eika,
    hypovereinsbank,
    laanspar,
    nordnet,
    saxotradergo,
    sparebanken,
    sparekassen,
    starmoney,
)
from .base import Provider
from .obos import archive as obos_archive
from .obos import recent as obos_recent

PROVIDERS: dict[str, Provider] = {
    module.provider.key: module.provider
    for module in [
        americanexpress,
        banknordik,
        banknorwegian,
        danskebank,
        eika,
        hypovereinsbank,
        laanspar,
        nordnet,
        obos_archive,
        obos_recent,
        saxotradergo,
        sparebanken,
        sparekassen,
        starmoney,
    ]
}
