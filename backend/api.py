from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date
from decimal import Decimal
from typing import Optional
from supabase import create_client
from dotenv import load_dotenv
import os

from MindOfMyNeto import (
    Revenue, Expense, Payment, ExpensePayment,
    Payroll, WorkLog, IncomeTaxPayment, NationalInsurancePayment,
    VATService, IncomeTaxService, NationalInsuranceService,
    FinancialReportService, CashflowReportService,
    YearlyAccountingSettlementService, WorkLogService
)

load_dotenv()

# =========================
# APP SETUP
# =========================

app = FastAPI(title="MyNeto API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174",
                   "http://localhost:5175", "http://localhost:5176"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# SUPABASE CONNECTION
# =========================

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# =========================
# LOAD DATA FROM SUPABASE
# =========================

def load_revenues():
    rows = supabase.table("revenues").select("*").execute().data
    return [Revenue(
        id=r["id"],
        amount=Decimal(str(r["amount"])),
        vat_included=r["vat_included"],
        transaction_date=date.fromisoformat(r["transaction_date"]),
        description=r["description"] or ""
    ) for r in rows]

def load_expenses():
    rows = supabase.table("expenses").select("*").execute().data
    return [Expense(
        id=r["id"],
        amount=Decimal(str(r["amount"])),
        vat_included=r["vat_included"],
        transaction_date=date.fromisoformat(r["transaction_date"]),
        description=r["description"] or "",
        is_deductible=r["is_deductible"]
    ) for r in rows]

def load_payments():
    rows = supabase.table("payments").select("*").execute().data
    return [Payment(
        revenue_id=r["revenue_id"],
        amount=Decimal(str(r["amount"])),
        payment_date=date.fromisoformat(r["payment_date"])
    ) for r in rows]

def load_expense_payments():
    rows = supabase.table("expense_payments").select("*").execute().data
    return [ExpensePayment(
        expense_id=r["expense_id"],
        amount=Decimal(str(r["amount"])),
        payment_date=date.fromisoformat(r["payment_date"])
    ) for r in rows]

def load_payrolls():
    rows = supabase.table("employees").select("*").execute().data
    return [Payroll(
        id=r["id"],
        employee_name=r["employee_name"],
        salary_type=r["salary_type"],
        rate=Decimal(str(r["rate"])),
        units=0,
        paid_this_month=False,
        calculation_type=r["calculation_type"] or "manual"
    ) for r in rows]

def load_worklogs():
    rows = supabase.table("work_logs").select("*").execute().data
    return [WorkLog(
        employee_id=r["employee_id"],
        work_date=date.fromisoformat(r["work_date"]),
        worked=r["worked"]
    ) for r in rows]

def load_income_tax_payments():
    rows = supabase.table("income_tax_payments").select("*").execute().data
    return [IncomeTaxPayment(
        amount=Decimal(str(r["amount"])),
        payment_date=date.fromisoformat(r["payment_date"]),
        description=r["description"] or ""
    ) for r in rows]

def load_ni_payments():
    rows = supabase.table("national_insurance_payments").select("*").execute().data
    return [NationalInsurancePayment(
        amount=Decimal(str(r["amount"])),
        payment_date=date.fromisoformat(r["payment_date"]),
        description=r["description"] or ""
    ) for r in rows]

# =========================
# SERVICES
# =========================

vat_service = VATService()
tax_service = IncomeTaxService()
ni_service  = NationalInsuranceService()

def get_accounting_service():
    return FinancialReportService(
        load_revenues(), load_expenses(), load_payrolls(), load_worklogs(),
        vat_service, tax_service, ni_service
    )

def get_cashflow_service():
    return CashflowReportService(
        load_revenues(), load_payments(), load_expenses(), load_expense_payments(),
        vat_service, tax_service, ni_service
    )

def get_yearly_service():
    return YearlyAccountingSettlementService(
        load_revenues(), load_expenses(), load_payrolls(), load_worklogs(),
        load_income_tax_payments(), load_ni_payments(),
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
        report = get_accounting_service().generate_monthly_report(month, year)
        return {k: float(v) for k, v in report.items()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/cashflow")
def get_cashflow_report(month: int, year: int):
    try:
        report = get_cashflow_service().generate_monthly_cashflow_report(month, year)
        return {k: float(v) for k, v in report.items()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/yearly")
def get_yearly_report(year: int):
    try:
        report = get_yearly_service().generate_yearly_settlement(year)
        result = {}
        for k, v in report.items():
            result[k] = float(v) if isinstance(v, Decimal) else v
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/revenues")
def get_revenues():
    return [
        {"id":r.id, "amount":float(r.amount), "vat_included":r.vat_included,
         "date":str(r.transaction_date), "description":r.description}
        for r in load_revenues()
    ]

@app.get("/expenses")
def get_expenses():
    return [
        {"id":e.id, "amount":float(e.amount), "vat_included":e.vat_included,
         "date":str(e.transaction_date), "description":e.description,
         "is_deductible":e.is_deductible}
        for e in load_expenses()
    ]

@app.get("/payroll")
def get_payroll():
    return [
        {"id":p.id, "employee_name":p.employee_name, "salary_type":p.salary_type,
         "rate":float(p.rate), "units":p.units, "paid_this_month":p.paid_this_month,
         "calculation_type":p.calculation_type}
        for p in load_payrolls()
    ]

@app.get("/worklog/{employee_id}")
def get_worklog(employee_id: int, month: int, year: int):
    wl_service = WorkLogService(load_worklogs())
    calendar = wl_service.get_monthly_calendar(employee_id, month, year)
    return {"employee_id": employee_id, "month": month, "year": year, "days": calendar}

@app.get("/payments")
def get_payments():
    return [
        {"id":p.revenue_id, "amount":float(p.amount), "date":str(p.payment_date)}
        for p in load_payments()
    ]

@app.get("/expense-payments")
def get_expense_payments():
    return [
        {"id":ep.expense_id, "amount":float(ep.amount), "date":str(ep.payment_date)}
        for ep in load_expense_payments()
    ]

# =========================
# POST ENDPOINTS — הוספת נתונים
# =========================

class RevenueIn(BaseModel):
    amount: float
    vat_included: bool
    transaction_date: str
    description: str

class ExpenseIn(BaseModel):
    amount: float
    vat_included: bool
    transaction_date: str
    description: str
    is_deductible: bool

class EmployeeIn(BaseModel):
    employee_name: str
    salary_type: str
    rate: float
    calculation_type: str = "manual"

class PaymentIn(BaseModel):
    revenue_id: int
    amount: float
    payment_date: str

class ExpensePaymentIn(BaseModel):
    expense_id: int
    amount: float
    payment_date: str

class WorkLogIn(BaseModel):
    employee_id: int
    work_date: str
    worked: bool = True
    units: float = 1

@app.post("/revenues")
def add_revenue(data: RevenueIn):
    try:
        result = supabase.table("revenues").insert({
            "amount": data.amount,
            "vat_included": data.vat_included,
            "transaction_date": data.transaction_date,
            "description": data.description
        }).execute()
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/expenses")
def add_expense(data: ExpenseIn):
    try:
        result = supabase.table("expenses").insert({
            "amount": data.amount,
            "vat_included": data.vat_included,
            "transaction_date": data.transaction_date,
            "description": data.description,
            "is_deductible": data.is_deductible
        }).execute()
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/employees")
def add_employee(data: EmployeeIn):
    try:
        result = supabase.table("employees").insert({
            "employee_name": data.employee_name,
            "salary_type": data.salary_type,
            "rate": data.rate,
            "calculation_type": data.calculation_type
        }).execute()
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/payments")
def add_payment(data: PaymentIn):
    try:
        result = supabase.table("payments").insert({
            "revenue_id": data.revenue_id,
            "amount": data.amount,
            "payment_date": data.payment_date
        }).execute()
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/expense-payments")
def add_expense_payment(data: ExpensePaymentIn):
    try:
        result = supabase.table("expense_payments").insert({
            "expense_id": data.expense_id,
            "amount": data.amount,
            "payment_date": data.payment_date
        }).execute()
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/worklog")
def add_worklog(data: WorkLogIn):
    try:
        result = supabase.table("work_logs").insert({
            "employee_id": data.employee_id,
            "work_date": data.work_date,
            "worked": data.worked,
            "units": data.units
        }).execute()
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/employees")
def add_employee(employee_name: str, salary_type: str, rate: float,
                 calculation_type: str = "manual"):
    try:
        result = supabase.table("employees").insert({
            "employee_name": employee_name,
            "salary_type": salary_type,
            "rate": rate,
            "calculation_type": calculation_type
        }).execute()
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/worklog")
def add_worklog(employee_id: int, work_date: str, worked: bool = True, units: float = 1):
    try:
        result = supabase.table("work_logs").insert({
            "employee_id": employee_id,
            "work_date": work_date,
            "worked": worked,
            "units": units
        }).execute()
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/balances")
def get_balances(month: int, year: int):
    try:
        # טעינת נתונים מ-Supabase
        all_revenues = load_revenues()
        all_payments = load_payments()
        all_expenses = load_expenses()
        all_expense_payments = load_expense_payments()

        # סינון לפי חודש ושנה
        monthly_revenues = [
            r for r in all_revenues
            if r.transaction_date.month == month
            and r.transaction_date.year == year
        ]
        monthly_expenses = [
            e for e in all_expenses
            if e.transaction_date.month == month
            and e.transaction_date.year == year
        ]
        monthly_payments = [
            p for p in all_payments
            if p.payment_date.month == month
            and p.payment_date.year == year
        ]
        monthly_expense_payments = [
            ep for ep in all_expense_payments
            if ep.payment_date.month == month
            and ep.payment_date.year == year
        ]

        # חישוב לקוחות חייבים
        total_revenues = sum(r.amount for r in monthly_revenues)
        total_payments_in = sum(p.amount for p in monthly_payments)
        customers_debt = total_revenues - total_payments_in

        # חישוב תשלום לספקים
        total_expenses = sum(e.amount for e in monthly_expenses)
        total_payments_out = sum(ep.amount for ep in monthly_expense_payments)
        suppliers_debt = total_expenses - total_payments_out

        return {
            "customers_debt": float(customers_debt),
            "suppliers_debt": float(suppliers_debt),
            "total_revenues": float(total_revenues),
            "total_payments_in": float(total_payments_in),
            "total_expenses": float(total_expenses),
            "total_payments_out": float(total_payments_out),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
