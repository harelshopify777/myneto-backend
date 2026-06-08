from datetime import date # לוקח ספרייה של תאריך
from decimal import Decimal # לוקח משתנה עשרוני מדויק יותר למניעת טעויות


class Revenue:
    def __init__(self, id: int, amount: Decimal, vat_included: bool, transaction_date: date, description: str):
        self.id = id
        self.amount = amount
        self.vat_included = vat_included
        self.transaction_date = transaction_date
        self.description = description


revenue1 = Revenue(
    id=1001,
    amount=Decimal("1000.00"),
    vat_included=True,
    transaction_date=date(2026, 4, 28),
    description="Website sale"
)

