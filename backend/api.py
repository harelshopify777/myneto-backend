from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date
from decimal import Decimal
from typing import Optional

from MindOfMyNeto import (
    Revenue, Expense, Payment, ExpensePayment,
    Payroll, WorkLog, IncomeTaxPayment, NationalInsurancePayment,
    VATService, IncomeTaxService, NationalInsuranceService,
    FinancialReportService, CashflowReportService,
    YearlyAccountingSettlementService, WorkLogService
)

# =========================
# APP SETUP
# =========================

app = FastAPI(title="MyNeto API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5176"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# SAMPLE DATA (זמני — יוחלף במסד נתונים)
# =========================

revenues = [
    Revenue(1, Decimal("11800"), True,  date(2025, 5, 5),  "שירותי ייעוץ - לקוח א"),
    Revenue(2, Decimal("8260"),  True,  date(2025, 5, 12), "פיתוח אתר - לקוח ב"),
    Revenue(3, Decimal("5900"),  True,  date(2025, 5, 18), "תחזוקה חודשית - לקוח ג"),
    Revenue(4, Decimal("9440"),  True,  date(2025, 5, 22), "עיצוב גרפי - לקוח ד"),
]

payments = [
    Payment(1, Decimal("11800"), date(2025, 5, 10)),
    Payment(2, Decimal("5000"),  date(2025, 5, 15)),
    Payment(3, Decimal("5900"),  date(2025, 5, 20)),
]

expenses = [
    Expense(1, Decimal("2360"), True,  date(2025, 5, 3),  "שכירות משרד",    True),
    Expense(2, Decimal("590"),  True,  date(2025, 5, 8),  "ציוד משרדי",     True),
    Expense(3, Decimal("354"),  True,  date(2025, 5, 10), "אינטרנט וטלפון", True),
    Expense(4, Decimal("1180"), True,  date(2025, 5, 15), "תוכנות ומנויים", True),
    Expense(5, Decimal("708"),  False, date(2025, 5, 20), "נסיעות",         False),
]

expense_payments = [
    ExpensePayment(1, Decimal("2360"), date(2025, 5, 5)),
    ExpensePayment(2, Decimal("590"),  date(2025, 5, 10)),
    ExpensePayment(3, Decimal("354"),  date(2025, 5, 12)),
]

payrolls = [
    Payroll(1, "דנה כהן",  "monthly", Decimal("6000"), 1,  True, "manual"),
    Payroll(2, "יוסי לוי", "hourly",  Decimal("120"),  16, True, "auto"),
]

worklogs = [
    WorkLog(2, date(2025, 5, 1),  True),
    WorkLog(2, date(2025, 5, 4),  True),
    WorkLog(2, date(2025, 5, 5),  True),
    WorkLog(2, date(2025, 5, 6),  True),
    WorkLog(2, date(2025, 5, 7),  True),
    WorkLog(2, date(2025, 5, 8),  True),
    WorkLog(2, date(2025, 5, 11), True),
    WorkLog(2, date(2025, 5, 12), True),
    WorkLog(2, date(2025, 5, 13), True),
    WorkLog(2, date(2025, 5, 14), True),
    WorkLog(2, date(2025, 5, 15), True),
    WorkLog(2, date(2025, 5, 18), True),
    WorkLog(2, date(2025, 5, 19), True),
    WorkLog(2, date(2025, 5, 20), True),
    WorkLog(2, date(2025, 5, 21), True),
    WorkLog(2, date(2025, 5, 22), True),
]

income_tax_payments = [
    IncomeTaxPayment(Decimal("1500"), date(2025, 5, 15), "מקדמה מס הכנסה מאי"),
]

ni_payments = [
    NationalInsurancePayment(Decimal("800"), date(2025, 5, 15), "ביטוח לאומי מאי"),
]

# =========================
# SERVICES
# =========================

vat_service = VATService()
tax_service = IncomeTaxService()
ni_service  = NationalInsuranceService()

accounting_service = FinancialReportService(
    revenues, expenses, payrolls, worklogs,
    vat_service, tax_service, ni_service
)

cashflow_service = CashflowReportService(
    revenues, payments, expenses, expense_payments,
    vat_service, tax_service, ni_service
)

yearly_service = YearlyAccountingSettlementService(
    revenues, expenses, payrolls, worklogs,
    income_tax_payments, ni_payments,
    vat_service, tax_service, ni_service
)

# =========================
# ENDPOINTS
# =========================

@app.get("/")
def root():
    return {"status": "MyNeto API running"}

@app.get("/report/accounting")
def get_accounting_report(month: int, year: int):
    try:
        report = accounting_service.generate_monthly_report(month, year)
        return {k: float(v) for k, v in report.items()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/cashflow")
def get_cashflow_report(month: int, year: int):
    try:
        report = cashflow_service.generate_monthly_cashflow_report(month, year)
        return {k: float(v) for k, v in report.items()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/yearly")
def get_yearly_report(year: int):
    try:
        report = yearly_service.generate_yearly_settlement(year)
        result = {}
        for k, v in report.items():
            result[k] = float(v) if isinstance(v, Decimal) else v
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/revenues")
def get_revenues():
    return [
        {
            "id": r.id,
            "amount": float(r.amount),
            "vat_included": r.vat_included,
            "date": str(r.transaction_date),
            "description": r.description
        }
        for r in revenues
    ]

@app.get("/expenses")
def get_expenses():
    return [
        {
            "id": e.id,
            "amount": float(e.amount),
            "vat_included": e.vat_included,
            "date": str(e.transaction_date),
            "description": e.description,
            "is_deductible": e.is_deductible
        }
        for e in expenses
    ]

@app.get("/payroll")
def get_payroll():
    return [
        {
            "id": p.id,
            "employee_name": p.employee_name,
            "salary_type": p.salary_type,
            "rate": float(p.rate),
            "units": p.units,
            "paid_this_month": p.paid_this_month,
            "calculation_type": p.calculation_type
        }
        for p in payrolls
    ]

@app.get("/worklog/{employee_id}")
def get_worklog(employee_id: int, month: int, year: int):
    wl_service = WorkLogService(worklogs)
    calendar = wl_service.get_monthly_calendar(employee_id, month, year)
    return {"employee_id": employee_id, "month": month, "year": year, "days": calendar}
    return {"employee_id": employee_id, "month": month, "year": year, "days": calendar}