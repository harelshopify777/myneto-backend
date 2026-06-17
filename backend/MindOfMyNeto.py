from datetime import date
from decimal import Decimal
import calendar as cal


# =========================
# CONSTANTS
# =========================

VAT_RATE = Decimal("0.18")
VAT_DIVISOR = Decimal("1.18")


# =========================
# MODELS
# =========================

class Revenue:

    def __init__(
            self,
            id: int,
            amount: Decimal,
            vat_included: bool,
            transaction_date: date,
            description: str
    ):

        self.id = id
        self.amount = amount
        self.vat_included = vat_included
        self.transaction_date = transaction_date
        self.description = description


class Payment:

    def __init__(
            self,
            revenue_id: int,
            amount: Decimal,
            payment_date: date
    ):

        self.revenue_id = revenue_id
        self.amount = amount
        self.payment_date = payment_date


class Expense:

    def __init__(
            self,
            id: int,
            amount: Decimal,
            vat_included: bool,
            transaction_date: date,
            description: str,
            is_deductible: bool
    ):

        self.id = id
        self.amount = amount
        self.vat_included = vat_included
        self.transaction_date = transaction_date
        self.description = description
        self.is_deductible = is_deductible


class ExpensePayment:

    def __init__(
            self,
            expense_id: int,
            amount: Decimal,
            payment_date: date
    ):

        self.expense_id = expense_id
        self.amount = amount
        self.payment_date = payment_date

class IncomeTaxPayment:

    def __init__(
            self,
            amount: Decimal,
            payment_date: date,
            description: str
    ):

        self.amount = amount
        self.payment_date = payment_date
        self.description = description


class NationalInsurancePayment:

    def __init__(
            self,
            amount: Decimal,
            payment_date: date,
            description: str
    ):

        self.amount = amount
        self.payment_date = payment_date
        self.description = description


class Payroll:

    def __init__(
            self,
            id,
            employee_name,
            salary_type,
            rate,
            units,
            paid_this_month,
            calculation_type
    ):

        self.id = id
        self.employee_name = employee_name
        self.salary_type = salary_type
        self.rate = rate
        self.units = units
        self.paid_this_month = paid_this_month
        self.calculation_type = calculation_type


class WorkLog:

    def __init__(
            self,
            employee_id: int,
            work_date: date,
            worked: bool
    ):

        self.employee_id = employee_id
        self.work_date = work_date
        self.worked = worked


# =========================
# VAT SERVICE
# =========================

class VATService:

    @staticmethod
    def vat_from_included(amount: Decimal) -> Decimal:

        net = amount / VAT_DIVISOR

        return amount - net

    @staticmethod
    def vat_from_excluded(amount: Decimal) -> Decimal:

        return amount * VAT_RATE

    @staticmethod
    def vat_refund_from_expenses(expenses) -> Decimal:

        total_refund = Decimal("0")

        for e in expenses:

            if e.is_deductible:

                if e.vat_included:

                    net = e.amount / VAT_DIVISOR
                    vat = e.amount - net

                else:

                    vat = e.amount * VAT_RATE

                total_refund += vat

        return total_refund


# =========================
# INCOME TAX SERVICE
# =========================

class IncomeTaxService:

    def calculate_tax(self, income: Decimal, brackets) -> Decimal:

        tax = Decimal("0")
        previous_limit = Decimal("0")

        for limit, rate in brackets:

            bracket_size = limit - previous_limit
            remaining_income = income - previous_limit

            if remaining_income <= 0:
                break

            if remaining_income < bracket_size:
                taxable = remaining_income
            else:
                taxable = bracket_size

            tax += taxable * rate

            previous_limit = limit

        return tax

    def calculate_monthly_tax(self, income: Decimal) -> Decimal:

        brackets = [
            (Decimal("7010"),      Decimal("0.10")),
            (Decimal("10060"),     Decimal("0.14")),
            (Decimal("19000"),     Decimal("0.20")),
            (Decimal("25100"),     Decimal("0.31")),
            (Decimal("46690"),     Decimal("0.35")),
            (Decimal("60130"),     Decimal("0.47")),
            (Decimal("999999999"), Decimal("0.50")),
        ]

        return self.calculate_tax(income, brackets)

    def calculate_yearly_tax(self, income: Decimal):

        brackets = [
            (Decimal("84200"),     Decimal("0.10")),
            (Decimal("120720"),    Decimal("0.14")),
            (Decimal("228000"),    Decimal("0.20")),
            (Decimal("301200"),    Decimal("0.31")),
            (Decimal("560280"),    Decimal("0.35")),
            (Decimal("721560"),    Decimal("0.47")),
            (Decimal("999999999"), Decimal("0.50")),
        ]

        return self.calculate_tax(income, brackets)


# =========================
# NATIONAL INSURANCE
# =========================

class NationalInsuranceService:

    def calculate_monthly_ni(self, income: Decimal) -> Decimal:

        ni = Decimal("0")

        brackets = [
            (Decimal("7703"),  Decimal("0.077")),
            (Decimal("51910"), Decimal("0.18")),
        ]

        previous_limit = Decimal("0")

        for limit, rate in brackets:

            bracket_size = limit - previous_limit
            remaining_income = income - previous_limit

            if remaining_income <= 0:
                break

            if remaining_income < bracket_size:
                taxable = remaining_income
            else:
                taxable = bracket_size

            ni += taxable * rate

            previous_limit = limit

        return ni

    def calculate_yearly_ni(self, income: Decimal):

        ni = Decimal("0")

        brackets = [
            (Decimal("92436"),  Decimal("0.077")),
            (Decimal("622920"), Decimal("0.18")),
        ]

        previous_limit = Decimal("0")

        for limit, rate in brackets:

            bracket_size = limit - previous_limit
            remaining_income = income - previous_limit

            if remaining_income <= 0:
                break

            if remaining_income < bracket_size:
                taxable = remaining_income
            else:
                taxable = bracket_size

            ni += taxable * rate

            previous_limit = limit

        return ni


# =========================
# WORKLOG SERVICE
# =========================

class WorkLogService:

    def __init__(self, worklogs):

        self.worklogs = worklogs

    def get_monthly_units(self, employee_id, month, year):

        count = 0

        for w in self.worklogs:

            if (
                    w.employee_id == employee_id
                    and
                    w.work_date.month == month
                    and
                    w.work_date.year == year
                    and
                    w.worked
            ):

                count += 1

        return count

    def get_monthly_calendar(self, employee_id, month, year):

        calendar_data = {}

        num_days = cal.monthrange(year, month)[1]

        for day in range(1, num_days + 1):

            calendar_data[day] = False

        for w in self.worklogs:

            if (
                    w.employee_id == employee_id
                    and
                    w.work_date.month == month
                    and
                    w.work_date.year == year
            ):

                calendar_data[w.work_date.day] = w.worked

        return calendar_data


# =========================
# NET SERVICE
# =========================

class NetServiceByMonth:

    def __init__(self, revenues, expenses, payrolls):

        self.revenues = revenues
        self.expenses = expenses
        self.payrolls = payrolls

    def get_monthly_data(self, month, year):

        monthly_revenues = []

        for r in self.revenues:

            if (
                    r.transaction_date.month == month
                    and
                    r.transaction_date.year == year
            ):

                monthly_revenues.append(r)

        monthly_expenses = []

        for e in self.expenses:

            if (
                    e.transaction_date.month == month
                    and
                    e.transaction_date.year == year
            ):

                monthly_expenses.append(e)

        monthly_payrolls = []

        for p in self.payrolls:

            if p.paid_this_month:

                monthly_payrolls.append(p)

        return {
            "revenues": monthly_revenues,
            "expenses": monthly_expenses,
            "payrolls": monthly_payrolls
        }


# =========================
# ACCOUNTING REPORT
# =========================

class FinancialReportService:

    def __init__(
            self,
            revenues,
            expenses,
            payrolls,
            worklogs,
            vat_service,
            tax_service,
            ni_service
    ):

        self.revenues = revenues
        self.expenses = expenses
        self.payrolls = payrolls
        self.worklogs = worklogs

        self.vat_service = vat_service
        self.tax_service = tax_service
        self.ni_service = ni_service

    def generate_monthly_report(self, month, year):

        net_service = NetServiceByMonth(
            self.revenues,
            self.expenses,
            self.payrolls
        )

        data = net_service.get_monthly_data(month, year)

        revenues = data["revenues"]
        expenses = data["expenses"]
        payrolls = data["payrolls"]

        output_vat = Decimal("0")

        for r in revenues:

            if r.vat_included:

                output_vat += VATService.vat_from_included(r.amount)

            else:

                output_vat += VATService.vat_from_excluded(r.amount)

        input_vat = self.vat_service.vat_refund_from_expenses(expenses)

        vat_to_pay = output_vat - input_vat

        net_revenue = Decimal("0")

        for r in revenues:

            if r.vat_included:

                net_revenue += r.amount / VAT_DIVISOR

            else:

                net_revenue += r.amount

        net_expenses = Decimal("0")

        for e in expenses:

            if e.vat_included:

                net_expenses += e.amount / VAT_DIVISOR

            else:

                net_expenses += e.amount

        worklog_service = WorkLogService(self.worklogs)

        total_payroll = Decimal("0")

        for p in payrolls:

            if p.salary_type == "monthly":
                # עובד חודשי — שכר קבוע, יחידה אחת
                units = 1

            else:
                # עובד יומי/שעתי — תמיד מיומן עבודה
                units = worklog_service.get_monthly_units(
                    p.id,
                    month,
                    year
                )

            total_payroll += p.rate * units

        operating_profit = (
                net_revenue
                -
                net_expenses
                -
                total_payroll
        )

        ni = self.ni_service.calculate_monthly_ni(
            operating_profit
        )

        deductible_ni = ni * Decimal("0.52")

        adjusted_profit = (
                operating_profit
                -
                deductible_ni
        )

        income_tax = self.tax_service.calculate_monthly_tax(
            adjusted_profit
        )

        net_profit = (
                operating_profit
                -
                income_tax
                -
                ni
        )

        return {

            "revenues_including_vat":
                sum(r.amount for r in revenues),

            "net_revenue":
                net_revenue,

            "net_expenses":
                net_expenses,

            "payroll_expenses":
                total_payroll,

            "output_vat":
                output_vat,

            "input_vat":
                input_vat,

            "vat_to_pay":
                vat_to_pay,

            "operating_profit":
                operating_profit,

            "national_insurance":
                ni,

            "income_tax":
                income_tax,

            "net_profit":
                net_profit
        }


# =========================
# CASHFLOW SERVICE
# =========================

class CashflowService:

    def __init__(
            self,
            revenues,
            payments,
            expenses,
            expense_payments
    ):

        self.revenues = revenues
        self.payments = payments
        self.expenses = expenses
        self.expense_payments = expense_payments

    def get_monthly_cash_in(self, month, year):

        total_cash_in = Decimal("0")

        for p in self.payments:

            if (
                    p.payment_date.month == month
                    and
                    p.payment_date.year == year
            ):

                total_cash_in += p.amount

        return total_cash_in

    def get_monthly_cash_out(self, month, year):

        total_cash_out = Decimal("0")

        for ep in self.expense_payments:

            if (
                    ep.payment_date.month == month
                    and
                    ep.payment_date.year == year
            ):

                total_cash_out += ep.amount

        return total_cash_out

    def get_monthly_cashflow(self, month, year):

        cash_in = self.get_monthly_cash_in(month, year)

        cash_out = self.get_monthly_cash_out(month, year)

        return cash_in - cash_out


# =========================
# CASHFLOW REPORT
# =========================

class CashflowReportService:

    def __init__(
            self,
            revenues,
            payments,
            expenses,
            expense_payments,
            vat_service,
            tax_service,
            ni_service
    ):

        self.revenues = revenues
        self.payments = payments
        self.expenses = expenses
        self.expense_payments = expense_payments

        self.vat_service = vat_service
        self.tax_service = tax_service
        self.ni_service = ni_service

    def generate_monthly_cashflow_report(self, month, year):

        cash_revenue  = Decimal("0")
        cash_expenses = Decimal("0")

        output_vat = Decimal("0")
        input_vat  = Decimal("0")

        for p in self.payments:

            if (
                    p.payment_date.month == month
                    and
                    p.payment_date.year == year
            ):

                related_revenue = None

                for r in self.revenues:

                    if r.id == p.revenue_id:

                        related_revenue = r
                        break

                if related_revenue:

                    if related_revenue.vat_included:

                        vat        = p.amount - (p.amount / VAT_DIVISOR)
                        net_amount = p.amount / VAT_DIVISOR

                    else:

                        vat        = p.amount * VAT_RATE
                        net_amount = p.amount

                    output_vat    += vat
                    cash_revenue  += net_amount

        for ep in self.expense_payments:

            if (
                    ep.payment_date.month == month
                    and
                    ep.payment_date.year == year
            ):

                related_expense = None

                for e in self.expenses:

                    if e.id == ep.expense_id:

                        related_expense = e
                        break

                if related_expense:

                    if related_expense.vat_included:

                        vat        = ep.amount - (ep.amount / VAT_DIVISOR)
                        net_amount = ep.amount / VAT_DIVISOR

                    else:

                        vat        = ep.amount * VAT_RATE
                        net_amount = ep.amount

                    input_vat     += vat
                    cash_expenses += net_amount

        vat_to_pay = output_vat - input_vat

        operating_cash_profit = cash_revenue - cash_expenses

        ni = self.ni_service.calculate_monthly_ni(operating_cash_profit)

        deductible_ni = ni * Decimal("0.52")

        adjusted_profit = operating_cash_profit - deductible_ni

        income_tax = self.tax_service.calculate_monthly_tax(adjusted_profit)

        net_cash_profit = operating_cash_profit - income_tax - ni

        return {

            "cash_revenue":
                cash_revenue,

            "cash_expenses":
                cash_expenses,

            "output_vat":
                output_vat,

            "input_vat":
                input_vat,

            "vat_to_pay":
                vat_to_pay,

            "operating_cash_profit":
                operating_cash_profit,

            "national_insurance":
                ni,

            "income_tax":
                income_tax,

            "net_cash_profit":
                net_cash_profit
        }

    # ─────────────────────────────────────────
    # פונקציה חדשה — תזרים שנתי
    # מחשבת סכום כל התשלומים שנכנסו ויצאו בשנה
    # ─────────────────────────────────────────
    def generate_yearly_cashflow_report(self, year):

        cash_revenue  = Decimal("0")
        cash_expenses = Decimal("0")

        # סכום כל התשלומים שנכנסו בשנה
        for p in self.payments:

            if p.payment_date.year == year:

                related_revenue = None

                for r in self.revenues:

                    if r.id == p.revenue_id:

                        related_revenue = r
                        break

                if related_revenue:

                    if related_revenue.vat_included:

                        net_amount = p.amount / VAT_DIVISOR

                    else:

                        net_amount = p.amount

                    cash_revenue += net_amount

        # סכום כל התשלומים שיצאו בשנה
        for ep in self.expense_payments:

            if ep.payment_date.year == year:

                related_expense = None

                for e in self.expenses:

                    if e.id == ep.expense_id:

                        related_expense = e
                        break

                if related_expense:

                    if related_expense.vat_included:

                        net_amount = ep.amount / VAT_DIVISOR

                    else:

                        net_amount = ep.amount

                    cash_expenses += net_amount

        operating_cash_profit = cash_revenue - cash_expenses

        ni = self.ni_service.calculate_yearly_ni(operating_cash_profit)

        deductible_ni = ni * Decimal("0.52")

        adjusted_profit = operating_cash_profit - deductible_ni

        income_tax = self.tax_service.calculate_yearly_tax(adjusted_profit)

        net_cash_profit = operating_cash_profit - income_tax - ni

        return {

            "cash_revenue":
                cash_revenue,

            "cash_expenses":
                cash_expenses,

            "operating_cash_profit":
                operating_cash_profit,

            "national_insurance":
                ni,

            "income_tax":
                income_tax,

            "net_cash_profit":
                net_cash_profit
        }


# =========================
# YEARLY ACCOUNTING SETTLEMENT
# =========================

class YearlyAccountingSettlementService:

    def __init__(
            self,
            revenues,
            expenses,
            payrolls,
            worklogs,
            income_tax_payments,
            national_insurance_payments,
            vat_service,
            tax_service,
            ni_service
    ):

        self.revenues = revenues
        self.expenses = expenses
        self.payrolls = payrolls
        self.worklogs = worklogs

        self.income_tax_payments = income_tax_payments
        self.national_insurance_payments = national_insurance_payments

        self.vat_service = vat_service
        self.tax_service = tax_service
        self.ni_service = ni_service

    def generate_yearly_settlement(self, year):

        # =========================
        # YEARLY REVENUES
        # =========================

        yearly_net_revenue = Decimal("0")

        for r in self.revenues:

            if r.transaction_date.year == year:

                if r.vat_included:

                    yearly_net_revenue += r.amount / VAT_DIVISOR

                else:

                    yearly_net_revenue += r.amount

        # =========================
        # YEARLY EXPENSES
        # =========================

        yearly_net_expenses = Decimal("0")

        for e in self.expenses:

            if e.transaction_date.year == year:

                if e.vat_included:

                    yearly_net_expenses += e.amount / VAT_DIVISOR

                else:

                    yearly_net_expenses += e.amount

        # =========================
        # YEARLY PAYROLL
        # =========================

        worklog_service = WorkLogService(self.worklogs)

        yearly_payroll = Decimal("0")

        for month in range(1, 13):

            for p in self.payrolls:

                if p.salary_type == "monthly":
                    units = 1
                else:
                    units = worklog_service.get_monthly_units(
                        p.id,
                        month,
                        year
                    )

                yearly_payroll += p.rate * units

        # =========================
        # OPERATING PROFIT
        # =========================

        yearly_operating_profit = (
                yearly_net_revenue
                -
                yearly_net_expenses
                -
                yearly_payroll
        )

        # =========================
        # YEARLY NATIONAL INSURANCE
        # =========================

        actual_yearly_ni = self.ni_service.calculate_yearly_ni(
            yearly_operating_profit
        )

        # =========================
        # DEDUCTIBLE NI
        # =========================

        deductible_ni = actual_yearly_ni * Decimal("0.52")

        # =========================
        # ADJUSTED PROFIT
        # =========================

        adjusted_yearly_profit = yearly_operating_profit - deductible_ni

        # =========================
        # YEARLY INCOME TAX
        # =========================

        actual_yearly_income_tax = self.tax_service.calculate_yearly_tax(
            adjusted_yearly_profit
        )

        # =========================
        # PAID INCOME TAX
        # =========================

        paid_income_tax = Decimal("0")

        for payment in self.income_tax_payments:

            if payment.payment_date.year == year:

                paid_income_tax += payment.amount

        # =========================
        # PAID NATIONAL INSURANCE
        # =========================

        paid_ni = Decimal("0")

        for payment in self.national_insurance_payments:

            if payment.payment_date.year == year:

                paid_ni += payment.amount

        # =========================
        # TAX DIFFERENCES
        # =========================

        income_tax_difference = actual_yearly_income_tax - paid_income_tax

        ni_difference = actual_yearly_ni - paid_ni

        # =========================
        # TAX STATUS
        # =========================

        if income_tax_difference > 0:
            income_tax_status = "to_pay"
        elif income_tax_difference < 0:
            income_tax_status = "refund"
        else:
            income_tax_status = "balanced"

        # =========================
        # NI STATUS
        # =========================

        if ni_difference > 0:
            ni_status = "to_pay"
        elif ni_difference < 0:
            ni_status = "refund"
        else:
            ni_status = "balanced"

        # =========================
        # FINAL NET PROFIT
        # =========================

        final_net_profit = (
                yearly_operating_profit
                -
                actual_yearly_income_tax
                -
                actual_yearly_ni
        )

        # =========================
        # RETURN
        # =========================

        return {

            "yearly_net_revenue":
                yearly_net_revenue,

            "yearly_net_expenses":
                yearly_net_expenses,

            "yearly_payroll":
                yearly_payroll,

            "yearly_operating_profit":
                yearly_operating_profit,

            "actual_yearly_national_insurance":
                actual_yearly_ni,

            "paid_national_insurance":
                paid_ni,

            "national_insurance_difference":
                ni_difference,

            "national_insurance_status":
                ni_status,

            "adjusted_yearly_profit":
                adjusted_yearly_profit,

            "actual_yearly_income_tax":
                actual_yearly_income_tax,

            "paid_income_tax":
                paid_income_tax,

            "income_tax_difference":
                income_tax_difference,

            "income_tax_status":
                income_tax_status,

            "final_net_profit":
                final_net_profit
        }
