"""The bank-agnostic transaction that every provider produces."""

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal


def scale_amount(amount: Decimal, factor: Decimal) -> Decimal:
    """Multiply and round to cents."""
    # Reproduces 1.x float rounding so dedup against files converted by 1.x keeps working.
    return Decimal(format(round(float(amount) * float(factor), 2), ".2f"))


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
        if factor == 1:
            return self
        return replace(self, amount=scale_amount(self.amount, factor))
