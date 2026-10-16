"""The bank-agnostic transaction that every provider produces."""

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

CENT = Decimal("0.01")


@dataclass(frozen=True)
class Transaction:
    date: date
    payee: str
    amount: Decimal
    """Signed. Negative means money left the account."""
    memo: str = ""
    category: str = ""

    @property
    def outflow(self) -> Decimal:
        return -self.amount if self.amount < 0 else Decimal(0)

    @property
    def inflow(self) -> Decimal:
        return self.amount if self.amount > 0 else Decimal(0)

    def scaled(self, factor: Decimal) -> "Transaction":
        """Convert currency by multiplying the amount, rounded to cents."""
        return replace(self, amount=(self.amount * factor).quantize(CENT))
