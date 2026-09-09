from fastapi import FastAPI, HTTPException, Depends, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import date
from decimal import Decimal
from typing import Optional
from supabase import create_client
from dotenv import load_dotenv
import os
import time
import logging
import traceback
import httpx

from MindOfMyNeto import (
    Revenue, Expense, Payment, ExpensePayment,
    Payroll, WorkLog, IncomeTaxPayment, NationalInsurancePayment,
    VATService, IncomeTaxService, NationalInsuranceService,
    FinancialReportService, CashflowReportService,
    YearlyAccountingSettlementService, WorkLogService
)
from auth import (
    CurrentUser, get_current_user, hash_password, verify_password,
    create_session_token, cookie_settings,
    SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS,
)

load_dotenv()

# =========================
# APP SETUP
# =========================

app = FastAPI(title="MyNeto API")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("myneto")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url}")
    logger.error(traceback.format_exc())
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
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

def db_execute(query, retries: int = 3, delay: float = 0.4):
    """
    Executes a Supabase/PostgREST query with automatic retries.
    Handles transient network errors (e.g. "Server disconnected")
    that occur when many requests hit the shared Supabase client
    concurrently.
    """
    last_error = None
    for attempt in range(retries):
        try:
            return query.execute()
        except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout) as e:
            last_error = e
            time.sleep(delay * (attempt + 1))  # simple linear backoff
    raise last_error

# =========================
# AUTH
# =========================

class AuthIn(BaseModel):
    username: str
    password: str


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _set_session_cookie(response: Response, user_id: int, username: str):
    token = create_session_token(user_id, username)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=SESSION_MAX_AGE_SECONDS,
        **cookie_settings(),
    )


@app.post("/auth/signup")
def signup(data: AuthIn, response: Response):
    username = _normalize_username(data.username)
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    existing = db_execute(supabase.table("users").select("id").eq("username", username)).data
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    password_hash = hash_password(data.password)
    result = db_execute(supabase.table("users").insert({
        "username": username,
        "password_hash": password_hash,
    }))
    new_user = result.data[0]

    db_execute(supabase.table("settings").insert({"user_id": new_user["id"]}))

    _set_session_cookie(response, new_user["id"], new_user["username"])
    return {"username": new_user["username"]}


@app.post("/auth/login")
def login(data: AuthIn, response: Response):
    username = _normalize_username(data.username)
    rows = db_execute(supabase.table("users").select("*").eq("username", username)).data
    if not rows or not verify_password(data.password, rows[0]["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user = rows[0]
    _set_session_cookie(response, user["id"], user["username"])
    return {"username": user["username"]}


@app.post("/auth/logout")
def logout(response: Response):
    settings = cookie_settings()
    response.delete_cookie(SESSION_COOKIE_NAME, secure=settings["secure"], samesite=settings["samesite"])
    return {"success": True}


@app.get("/auth/me")
def me(user: CurrentUser = Depends(get_current_user)):
    return {"username": user.username}

# =========================
# LOAD DATA FROM SUPABASE
# =========================

def load_revenues(user_id: int):
    rows = db_execute(supabase.table("revenues").select("*").eq("user_id", user_id)).data
    return [Revenue(
        id=r["id"],
        amount=Decimal(str(r["amount"])),
        vat_included=r["vat_included"],
        transaction_date=date.fromisoformat(r["transaction_date"]),
        description=r["description"] or ""
    ) for r in rows]

def load_expenses(user_id: int):
    rows = db_execute(supabase.table("expenses").select("*").eq("user_id", user_id)).data
    return [Expense(
        id=r["id"],
        amount=Decimal(str(r["amount"])),
        vat_included=r["vat_included"],
        transaction_date=date.fromisoformat(r["transaction_date"]),
        description=r["description"] or "",
        is_deductible=r["is_deductible"]
    ) for r in rows]

def load_payments(user_id: int):
    rows = db_execute(supabase.table("payments").select("*").eq("user_id", user_id)).data
    return [Payment(
        revenue_id=r["revenue_id"],
        amount=Decimal(str(r["amount"])),
        payment_date=date.fromisoformat(r["payment_date"])
    ) for r in rows]

def load_expense_payments(user_id: int):
    rows = db_execute(supabase.table("expense_payments").select("*").eq("user_id", user_id)).data
    return [ExpensePayment(
        expense_id=r["expense_id"],
        amount=Decimal(str(r["amount"])),
        payment_date=date.fromisoformat(r["payment_date"])
    ) for r in rows]

def load_payrolls(user_id: int):
    rows = db_execute(supabase.table("employees").select("*").eq("user_id", user_id)).data
    result = []
    for r in rows:
        # ─── עובדים לא פעילים לא נכללים בחישוב שכר ───
        if not r.get("is_active", True):
            continue

        salary_type = r["salary_type"]

        if salary_type == "monthly":
            units = 1
        else:
            units = 0  # יחושב מיומן עבודה ע"י WorkLogService

        result.append(Payroll(
            id=r["id"],
            employee_name=r["employee_name"],
            salary_type=salary_type,
            rate=Decimal(str(r["rate"])),
            units=units,
            paid_this_month=False,
            calculation_type="auto" if salary_type != "monthly" else "manual"
        ))
    return result
def load_worklogs(user_id: int):
    rows = db_execute(supabase.table("work_logs").select("*").eq("user_id", user_id)).data
    return [WorkLog(
        employee_id=r["employee_id"],
        work_date=date.fromisoformat(r["work_date"]),
        worked=r["worked"],
        units=r.get("units", 1) or 1
    ) for r in rows]

def load_income_tax_payments(user_id: int):
    rows = db_execute(supabase.table("income_tax_payments").select("*").eq("user_id", user_id)).data
    return [IncomeTaxPayment(
        amount=Decimal(str(r["amount"])),
        payment_date=date.fromisoformat(r["payment_date"]),
        description=r["description"] or ""
    ) for r in rows]

def load_ni_payments(user_id: int):
    rows = db_execute(supabase.table("national_insurance_payments").select("*").eq("user_id", user_id)).data
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

def get_accounting_service(user_id: int):
    revenues  = load_revenues(user_id)
    expenses  = load_expenses(user_id)
    payrolls  = load_payrolls(user_id)
    worklogs  = load_worklogs(user_id)
    return FinancialReportService(
        revenues, expenses, payrolls, worklogs,
        vat_service, tax_service, ni_service
    )

def get_cashflow_service(user_id: int):
    return CashflowReportService(
        load_revenues(user_id), load_payments(user_id), load_expenses(user_id), load_expense_payments(user_id),
        vat_service, tax_service, ni_service
    )

def get_yearly_service(user_id: int):
    revenues    = load_revenues(user_id)
    expenses    = load_expenses(user_id)
    payrolls    = load_payrolls(user_id)
    worklogs    = load_worklogs(user_id)
    it_payments = load_income_tax_payments(user_id)
    ni_payments = load_ni_payments(user_id)
    return YearlyAccountingSettlementService(
        revenues, expenses, payrolls, worklogs,
        it_payments, ni_payments,
        vat_service, tax_service, ni_service
    )

# =========================
# ENDPOINTS
# =========================

@app.get("/")
def root():
    return {"status": "MyNeto API running"}

@app.get("/report/accounting")
def get_accounting_report(month: int, year: int, user: CurrentUser = Depends(get_current_user)):
    try:
        report = get_accounting_service(user.id).generate_monthly_report(month, year)
        return {k: float(v) for k, v in report.items()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/cashflow")
def get_cashflow_report(month: int, year: int, user: CurrentUser = Depends(get_current_user)):
    try:
        report = get_cashflow_service(user.id).generate_monthly_cashflow_report(month, year)
        return {k: float(v) for k, v in report.items()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/yearly")
def get_yearly_report(year: int, user: CurrentUser = Depends(get_current_user)):
    try:
        report = get_yearly_service(user.id).generate_yearly_settlement(year)
        result = {}
        for k, v in report.items():
            result[k] = float(v) if isinstance(v, Decimal) else v
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/yearly-cashflow")
def get_yearly_cashflow_report(year: int, user: CurrentUser = Depends(get_current_user)):
    try:
        service = CashflowReportService(
            load_revenues(user.id), load_payments(user.id),
            load_expenses(user.id), load_expense_payments(user.id),
            vat_service, tax_service, ni_service
        )
        report = service.generate_yearly_cashflow_report(year)
        return {k: float(v) for k, v in report.items()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# VAT PAYMENTS
# =========================

class VatPaymentIn(BaseModel):
    amount: float
    payment_date: str
    period: str
    description: str = ""

@app.get("/vat-payments")
def get_vat_payments(user: CurrentUser = Depends(get_current_user)):
    try:
        return db_execute(supabase.table("vat_payments").select("*").eq("user_id", user.id)).data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vat-payments")
def add_vat_payment(data: VatPaymentIn, user: CurrentUser = Depends(get_current_user)):
    try:
        result = db_execute(supabase.table("vat_payments").insert({
            "amount":       data.amount,
            "payment_date": data.payment_date,
            "period":       data.period,
            "description":  data.description,
            "user_id":      user.id,
        }))
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/vat-payments/{id}")
def delete_vat_payment(id: int, user: CurrentUser = Depends(get_current_user)):
    try:
        db_execute(supabase.table("vat_payments").delete().eq("id", id).eq("user_id", user.id))
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# INCOME TAX PAYMENTS — GET + POST + DELETE
# =========================

class TaxPaymentIn(BaseModel):
    amount: float
    payment_date: str
    period: str
    description: str = ""

@app.get("/income-tax-payments")
def get_income_tax_payments(user: CurrentUser = Depends(get_current_user)):
    try:
        return db_execute(supabase.table("income_tax_payments").select("*").eq("user_id", user.id)).data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/income-tax-payments")
def add_income_tax_payment(data: TaxPaymentIn, user: CurrentUser = Depends(get_current_user)):
    try:
        result = db_execute(supabase.table("income_tax_payments").insert({
            "amount":       data.amount,
            "payment_date": data.payment_date,
            "description":  f"{data.period} — {data.description}",
            "user_id":      user.id,
        }))
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/income-tax-payments/{id}")
def delete_income_tax_payment(id: int, user: CurrentUser = Depends(get_current_user)):
    try:
        db_execute(supabase.table("income_tax_payments").delete().eq("id", id).eq("user_id", user.id))
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# NATIONAL INSURANCE PAYMENTS — GET + POST + DELETE
# =========================

@app.get("/ni-payments")
def get_ni_payments(user: CurrentUser = Depends(get_current_user)):
    try:
        return db_execute(supabase.table("national_insurance_payments").select("*").eq("user_id", user.id)).data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ni-payments")
def add_ni_payment(data: TaxPaymentIn, user: CurrentUser = Depends(get_current_user)):
    try:
        result = db_execute(supabase.table("national_insurance_payments").insert({
            "amount":       data.amount,
            "payment_date": data.payment_date,
            "description":  f"{data.period} — {data.description}",
            "user_id":      user.id,
        }))
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/ni-payments/{id}")
def delete_ni_payment(id: int, user: CurrentUser = Depends(get_current_user)):
    try:
        db_execute(supabase.table("national_insurance_payments").delete().eq("id", id).eq("user_id", user.id))
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/yearly-vat")
def get_yearly_vat(year: int, user: CurrentUser = Depends(get_current_user)):
    try:
        service = get_accounting_service(user.id)
        total_vat = 0.0
        for month in range(1, 13):
            report = service.generate_monthly_report(month, year)
            total_vat += float(report["vat_to_pay"])
        return {"yearly_vat_to_pay": total_vat}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/payroll")
def debug_payroll(month: int, year: int, user: CurrentUser = Depends(get_current_user)):
    from MindOfMyNeto import WorkLogService
    worklogs = load_worklogs(user.id)
    wl_service = WorkLogService(worklogs)
    payrolls = load_payrolls(user.id)
    result = []
    for p in payrolls:
        units = wl_service.get_monthly_units(p.id, month, year)
        result.append({
            "id": p.id,
            "name": p.employee_name,
            "salary_type": p.salary_type,
            "calculation_type": p.calculation_type,
            "rate": float(p.rate),
            "units_from_worklog": units,
            "payroll_cost": float(p.rate) * units
        })
    return result

# =========================
# SETTINGS
# =========================

class SettingsUpdate(BaseModel):
    business_name:   str   = None
    business_type:   str   = None
    business_number: str   = None
    address:         str   = None
    phone:           str   = None
    email:           str   = None
    vat_rate:        float = None

@app.get("/settings")
def get_settings(user: CurrentUser = Depends(get_current_user)):
    try:
        rows = db_execute(supabase.table("settings").select("*").eq("user_id", user.id)).data
        if rows:
            return rows[0]
        return {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/settings")
def update_settings(data: SettingsUpdate, user: CurrentUser = Depends(get_current_user)):
    try:
        update = {k: v for k, v in data.dict().items() if v is not None}
        result = db_execute(supabase.table("settings").update(update).eq("user_id", user.id))
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/balances")
def get_balances(month: int, year: int, user: CurrentUser = Depends(get_current_user)):
    try:
        all_revenues         = load_revenues(user.id)
        all_payments         = load_payments(user.id)
        all_expenses         = load_expenses(user.id)
        all_expense_payments = load_expense_payments(user.id)

        monthly_revenues = [r for r in all_revenues
            if r.transaction_date.month == month and r.transaction_date.year == year]
        monthly_expenses = [e for e in all_expenses
            if e.transaction_date.month == month and e.transaction_date.year == year]
        monthly_payments = [p for p in all_payments
            if p.payment_date.month == month and p.payment_date.year == year]
        monthly_expense_payments = [ep for ep in all_expense_payments
            if ep.payment_date.month == month and ep.payment_date.year == year]

        total_revenues     = sum(r.amount for r in monthly_revenues)
        total_payments_in  = sum(p.amount for p in monthly_payments)
        customers_debt     = total_revenues - total_payments_in

        total_expenses     = sum(e.amount for e in monthly_expenses)
        total_payments_out = sum(ep.amount for ep in monthly_expense_payments)
        suppliers_debt     = total_expenses - total_payments_out

        return {
            "customers_debt":    float(customers_debt),
            "suppliers_debt":    float(suppliers_debt),
            "total_revenues":    float(total_revenues),
            "total_payments_in": float(total_payments_in),
            "total_expenses":    float(total_expenses),
            "total_payments_out":float(total_payments_out),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# GET ENDPOINTS
# =========================

@app.get("/revenues")
def get_revenues(user: CurrentUser = Depends(get_current_user)):
    rows = db_execute(supabase.table("revenues").select("*").eq("user_id", user.id)).data
    return [
        {"id":r["id"], "amount":float(r["amount"]), "vat_included":r["vat_included"],
         "date":r["transaction_date"], "description":r["description"],
         "customer_name": r.get("customer_name") or ""}
        for r in rows
    ]

@app.get("/expenses")
def get_expenses(user: CurrentUser = Depends(get_current_user)):
    rows = db_execute(supabase.table("expenses").select("*").eq("user_id", user.id)).data
    return [
        {"id":r["id"], "amount":float(r["amount"]), "vat_included":r["vat_included"],
         "date":r["transaction_date"], "description":r["description"],
         "is_deductible":r["is_deductible"],
         "supplier_name": r.get("supplier_name") or "",
         "deal_reference": r.get("deal_reference") or ""}
        for r in rows
    ]

@app.get("/payroll")
def get_payroll(month: int = None, year: int = None, user: CurrentUser = Depends(get_current_user)):
    rows = db_execute(supabase.table("employees").select("*").eq("user_id", user.id)).data
    has_period = month is not None and year is not None

    # סה"כ ששולם לכל עובד, אי פעם (לא מוגבל לחודש נוכחי) — לצורך יתרה לתשלום.
    # ובמקביל גם הסכום ששולם בדיוק בחודש המבוקש, אם התבקש.
    payments_rows = db_execute(supabase.table("payroll_payments").select("*").eq("user_id", user.id)).data
    total_paid_by_employee = {}
    month_paid_by_employee = {}
    for pp in payments_rows:
        eid = pp["employee_id"]
        total_paid_by_employee[eid] = total_paid_by_employee.get(eid, 0) + float(pp["amount"])
        if has_period and pp["month"] == month and pp["year"] == year:
            month_paid_by_employee[eid] = month_paid_by_employee.get(eid, 0) + float(pp["amount"])

    wl_service = WorkLogService(load_worklogs(user.id))

    result = []
    for r in rows:
        rate         = float(r["rate"])
        salary_type  = r["salary_type"]
        total_paid   = total_paid_by_employee.get(r["id"], 0)

        if salary_type == "monthly":
            # עובדים חודשיים: עדיין אין נקודת עיגון (תאריך תחילת עבודה/יתרת פתיחה)
            # לחישוב צבירה רב-חודשית מדויקת — יתווסף בהמשך.
            total_accrued      = None
            balance_due        = None
            units_this_month   = 1 if has_period else None
            accrued_this_month = rate if has_period else None
        else:
            total_accrued      = rate * wl_service.get_total_units(r["id"])
            balance_due        = total_accrued - total_paid
            units_this_month   = wl_service.get_monthly_units(r["id"], month, year) if has_period else None
            accrued_this_month = rate * units_this_month if has_period else None

        result.append({
            "id":                 r["id"],
            "employee_name":      r["employee_name"],
            "salary_type":        salary_type,
            "rate":               rate,
            "calculation_type":   r.get("calculation_type") or "manual",
            "role":               r.get("role") or "",
            "is_active":          r.get("is_active", True),
            "total_accrued":      total_accrued,
            "total_paid":         total_paid,
            "balance_due":        balance_due,
            # תלויים בחודש/שנה שהתבקשו — null אם לא צוין חודש, כדי לא לשבור קריאות ישנות (כמו עמוד העובדים)
            "units_this_month":   units_this_month,
            "accrued_this_month": accrued_this_month,
            "paid_this_month":    month_paid_by_employee.get(r["id"], 0) if has_period else None,
        })
    return result

@app.get("/worklog/{employee_id}")
def get_worklog(employee_id: int, month: int, year: int, user: CurrentUser = Depends(get_current_user)):
    wl_service = WorkLogService(load_worklogs(user.id))
    calendar   = wl_service.get_monthly_calendar(employee_id, month, year)
    return {"employee_id": employee_id, "month": month, "year": year, "days": calendar}

@app.get("/payments")
def get_payments(user: CurrentUser = Depends(get_current_user)):
    return [
        {"id":p.revenue_id, "amount":float(p.amount), "date":str(p.payment_date)}
        for p in load_payments(user.id)
    ]

@app.get("/expense-payments")
def get_expense_payments(user: CurrentUser = Depends(get_current_user)):
    return [
        {"id":ep.expense_id, "amount":float(ep.amount), "date":str(ep.payment_date)}
        for ep in load_expense_payments(user.id)
    ]

@app.get("/payroll-payments")
def get_payroll_payments(user: CurrentUser = Depends(get_current_user)):
    try:
        return db_execute(supabase.table("payroll_payments").select("*").eq("user_id", user.id)).data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# POST ENDPOINTS
# =========================

class RevenueIn(BaseModel):
    amount: float
    vat_included: bool
    transaction_date: str
    description: str
    customer_name: Optional[str] = None

class ExpenseIn(BaseModel):
    amount: float
    vat_included: bool
    transaction_date: str
    description: str
    is_deductible: bool
    supplier_name: Optional[str] = None
    deal_reference: Optional[str] = None

class EmployeeIn(BaseModel):
    employee_name: str
    salary_type: str
    rate: float
    calculation_type: str = "manual"
    role: str = ""
    is_active: bool = True

class PaymentIn(BaseModel):
    revenue_id: int
    amount: float
    payment_date: str

class ExpensePaymentIn(BaseModel):
    expense_id: int
    amount: float
    payment_date: str

class PayrollPaymentIn(BaseModel):
    employee_id: int
    amount: float
    payment_date: str
    month: int
    year: int

class WorkLogIn(BaseModel):
    employee_id: int
    work_date: str
    worked: bool = True
    units: float = 1

@app.post("/revenues")
def add_revenue(data: RevenueIn, user: CurrentUser = Depends(get_current_user)):
    try:
        result = db_execute(supabase.table("revenues").insert({
            "amount":           data.amount,
            "vat_included":     data.vat_included,
            "transaction_date": data.transaction_date,
            "description":      data.description,
            "customer_name":    data.customer_name,
            "user_id":          user.id,
        }))
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/expenses")
def add_expense(data: ExpenseIn, user: CurrentUser = Depends(get_current_user)):
    try:
        result = db_execute(supabase.table("expenses").insert({
            "amount":           data.amount,
            "vat_included":     data.vat_included,
            "transaction_date": data.transaction_date,
            "description":      data.description,
            "is_deductible":    data.is_deductible,
            "supplier_name":    data.supplier_name,
            "deal_reference":   data.deal_reference,
            "user_id":          user.id,
        }))
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/employees")
def add_employee(data: EmployeeIn, user: CurrentUser = Depends(get_current_user)):
    try:
        result = db_execute(supabase.table("employees").insert({
            "employee_name":    data.employee_name,
            "salary_type":      data.salary_type,
            "rate":             data.rate,
            "calculation_type": data.calculation_type,
            "role":             data.role,
            "is_active":        data.is_active,
            "user_id":          user.id,
        }))
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/payments")
def add_payment(data: PaymentIn, user: CurrentUser = Depends(get_current_user)):
    try:
        result = db_execute(supabase.table("payments").insert({
            "revenue_id":   data.revenue_id,
            "amount":       data.amount,
            "payment_date": data.payment_date,
            "user_id":      user.id,
        }))
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/expense-payments")
def add_expense_payment(data: ExpensePaymentIn, user: CurrentUser = Depends(get_current_user)):
    try:
        result = db_execute(supabase.table("expense_payments").insert({
            "expense_id":   data.expense_id,
            "amount":       data.amount,
            "payment_date": data.payment_date,
            "user_id":      user.id,
        }))
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/payroll-payments")
def add_payroll_payment(data: PayrollPaymentIn, user: CurrentUser = Depends(get_current_user)):
    try:
        result = db_execute(supabase.table("payroll_payments").insert({
            "employee_id":  data.employee_id,
            "amount":       data.amount,
            "payment_date": data.payment_date,
            "month":        data.month,
            "year":         data.year,
            "user_id":      user.id,
        }))
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/payroll-payments/{id}")
def delete_payroll_payment(id: int, user: CurrentUser = Depends(get_current_user)):
    try:
        db_execute(supabase.table("payroll_payments").delete().eq("id", id).eq("user_id", user.id))
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/worklog")
def add_worklog(data: WorkLogIn, user: CurrentUser = Depends(get_current_user)):
    try:
        result = db_execute(supabase.table("work_logs").insert({
            "employee_id": data.employee_id,
            "work_date":   data.work_date,
            "worked":      data.worked,
            "units":       data.units,
            "user_id":     user.id,
        }))
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/worklog/{employee_id}/{work_date}")
def delete_worklog(employee_id: int, work_date: str, user: CurrentUser = Depends(get_current_user)):
    try:
        db_execute(supabase.table("work_logs").delete()\
            .eq("employee_id", employee_id)\
            .eq("work_date", work_date)\
            .eq("user_id", user.id))
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/worklog/{employee_id}/{work_date}")
def update_worklog(employee_id: int, work_date: str, data: WorkLogIn, user: CurrentUser = Depends(get_current_user)):
    try:
        # בדוק אם קיים
        existing = db_execute(supabase.table("work_logs")\
            .select("*")\
            .eq("employee_id", employee_id)\
            .eq("work_date", work_date)\
            .eq("user_id", user.id)).data
        if existing:
            db_execute(supabase.table("work_logs")\
                .update({"worked": data.worked, "units": data.units})\
                .eq("employee_id", employee_id)\
                .eq("work_date", work_date)\
                .eq("user_id", user.id))
        else:
            db_execute(supabase.table("work_logs").insert({
                "employee_id": employee_id,
                "work_date":   work_date,
                "worked":      data.worked,
                "units":       data.units,
                "user_id":     user.id,
            }))
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# DELETE + PUT REVENUES
# =========================

class RevenueUpdate(BaseModel):
    amount: float = None
    vat_included: bool = None
    transaction_date: str = None
    description: str = None
    customer_name: str = None

@app.delete("/revenues/{id}")
def delete_revenue(id: int, user: CurrentUser = Depends(get_current_user)):
    try:
        db_execute(supabase.table("payments").delete().eq("revenue_id", id).eq("user_id", user.id))
        db_execute(supabase.table("revenues").delete().eq("id", id).eq("user_id", user.id))
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/revenues/{id}")
def update_revenue(id: int, data: RevenueUpdate, user: CurrentUser = Depends(get_current_user)):
    try:
        update = {k: v for k, v in data.dict().items() if v is not None}
        result = db_execute(supabase.table("revenues").update(update).eq("id", id).eq("user_id", user.id))
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# DELETE + PUT EXPENSES
# =========================

class ExpenseUpdate(BaseModel):
    amount: float = None
    vat_included: bool = None
    transaction_date: str = None
    description: str = None
    supplier_name: str = None
    is_deductible: bool = None
    deal_reference: str = None

@app.delete("/expenses/{id}")
def delete_expense(id: int, user: CurrentUser = Depends(get_current_user)):
    try:
        db_execute(supabase.table("expense_payments").delete().eq("expense_id", id).eq("user_id", user.id))
        db_execute(supabase.table("expenses").delete().eq("id", id).eq("user_id", user.id))
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/expenses/{id}")
def update_expense(id: int, data: ExpenseUpdate, user: CurrentUser = Depends(get_current_user)):
    try:
        update = {k: v for k, v in data.dict().items() if v is not None}
        result = db_execute(supabase.table("expenses").update(update).eq("id", id).eq("user_id", user.id))
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# DELETE + PUT EMPLOYEES
# =========================

class EmployeeUpdate(BaseModel):
    employee_name:    str  = None
    salary_type:      str  = None
    rate:             float = None
    calculation_type: str  = None
    role:             str  = None
    is_active:        bool = None

@app.delete("/employees/{id}")
def delete_employee(id: int, user: CurrentUser = Depends(get_current_user)):
    try:
        db_execute(supabase.table("payroll_payments").delete().eq("employee_id", id).eq("user_id", user.id))
        db_execute(supabase.table("work_logs").delete().eq("employee_id", id).eq("user_id", user.id))
        db_execute(supabase.table("employees").delete().eq("id", id).eq("user_id", user.id))
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/employees/{id}")
def update_employee(id: int, data: EmployeeUpdate, user: CurrentUser = Depends(get_current_user)):
    try:
        update = {k: v for k, v in data.dict().items() if v is not None}
        result = db_execute(supabase.table("employees").update(update).eq("id", id).eq("user_id", user.id))
        return {"success": True, "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
