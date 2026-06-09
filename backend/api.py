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

@app.post("/revenues")
def add_revenue(amount: float, vat_included: bool, transaction_date: str, description: str):
    try:
        result = supabase.table("revenues").insert({
            "amount": amount,
            "vat_included": vat_included,
            "transaction_date": transaction_date,
            "description": description
        }).execute()
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/expenses")
def add_expense(amount: float, vat_included: bool, transaction_date: str,
                description: str, is_deductible: bool):
    try:
        result = supabase.table("expenses").insert({
            "amount": amount,
            "vat_included": vat_included,
            "transaction_date": transaction_date,
            "description": description,
            "is_deductible": is_deductible
        }).execute()
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/payments")
def add_payment(revenue_id: int, amount: float, payment_date: str):
    try:
        result = supabase.table("payments").insert({
            "revenue_id": revenue_id,
            "amount": amount,
            "payment_date": payment_date
        }).execute()
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/expense-payments")
def add_expense_payment(expense_id: int, amount: float, payment_date: str):
    try:
        result = supabase.table("expense_payments").insert({
            "expense_id": expense_id,
            "amount": amount,
            "payment_date": payment_date
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
