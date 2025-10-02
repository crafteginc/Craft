import datetime
from decimal import Decimal
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from returnrequest.models import Transaction

def get_date_range_for_period(period_string: str = None, month_string: str = None):
    """
    Calculates the start and end dates for the current and previous period.
    """
    today = timezone.now().date()

    if period_string == 'this_month':
        current_start = today.replace(day=1)
        # Go to the next month and then subtract a day to get the end of the current month
        next_month_date = (current_start + datetime.timedelta(days=32)).replace(day=1)
        current_end = next_month_date - datetime.timedelta(days=1)
        
        # Previous Period
        prev_end = current_start - datetime.timedelta(days=1)
        prev_start = prev_end.replace(day=1)

    elif period_string == 'this_year':
        current_start = today.replace(month=1, day=1)
        current_end = today.replace(month=12, day=31)

        # Previous Period
        prev_start = current_start.replace(year=current_start.year - 1)
        prev_end = current_end.replace(year=current_end.year - 1)

    elif period_string == 'this_day':
        current_start = today
        current_end = today
        
        # Previous Period (yesterday)
        prev_start = today - datetime.timedelta(days=1)
        prev_end = prev_start

    elif month_string:
        year, month = map(int, month_string.split('-'))
        current_start = datetime.date(year, month, 1)
        
        # Go to the next month and then subtract a day to get the end of the current month
        next_month_date = (current_start + datetime.timedelta(days=32)).replace(day=1)
        current_end = next_month_date - datetime.timedelta(days=1)

        # Previous Period
        prev_end = current_start - datetime.timedelta(days=1)
        prev_start = prev_end.replace(day=1)

    else: # Default to 'this_month'
        return get_date_range_for_period(period_string='this_month')

    return current_start, current_end, prev_start, prev_end


class ReportService:

    @staticmethod
    def get_earning_report(supplier_user, period: str = None, month: str = None):
        income_types = [
            Transaction.TransactionType.PURCHASED_PRODUCTS,
            Transaction.TransactionType.RETURN_CREDIT,
            Transaction.TransactionType.CASH_BACK,
            Transaction.TransactionType.SUPPLIER_TRANSFORM,
            Transaction.TransactionType.REFUND_FAILED,
            Transaction.TransactionType.PURCHASED_COURSE
        ]
        outcome_types = [
            Transaction.TransactionType.WITHDRAWAL_REQUEST,
            Transaction.TransactionType.RETURN_DEBIT,
            Transaction.TransactionType.RETURNED_CASH_BACK,
            Transaction.TransactionType.RETURNED_PRODUCT
        ]

        current_start, current_end, prev_start, prev_end = get_date_range_for_period(period_string=period, month_string=month)

        transactions = Transaction.objects.filter(
            user=supplier_user,
            created_at__date__gte=current_start,
            created_at__date__lte=current_end
        )

        graph_data = transactions.annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            income=Sum('amount', filter=Q(transaction_type__in=income_types)),
            outcome=Sum('amount', filter=Q(transaction_type__in=outcome_types))
        ).order_by('month')

        formatted_graph_data = [
            {
                "month": item['month'].strftime("%b"),
                "income": item['income'] or 0,
                "outcome": abs(item['outcome'] or 0)
            }
            for item in graph_data
        ]

        current_totals = transactions.aggregate(
            total_income=Sum('amount', filter=Q(transaction_type__in=income_types)),
            total_outcome=Sum('amount', filter=Q(transaction_type__in=outcome_types))
        )
        current_total_income = current_totals.get('total_income') or Decimal('0.0')
        current_total_outcome = current_totals.get('total_outcome') or Decimal('0.0')
        current_earning = current_total_income + current_total_outcome

        prev_totals = Transaction.objects.filter(
            user=supplier_user,
            created_at__date__gte=prev_start,
            created_at__date__lte=prev_end
        ).aggregate(
            total_income=Sum('amount', filter=Q(transaction_type__in=income_types)),
            total_outcome=Sum('amount', filter=Q(transaction_type__in=outcome_types))
        )
        prev_total_income = prev_totals.get('total_income') or Decimal('0.0')
        prev_total_outcome = prev_totals.get('total_outcome') or Decimal('0.0')
        previous_earning = prev_total_income + prev_total_outcome

        percentage_change = 0
        if previous_earning > 0:
            percentage_change = ((current_earning - previous_earning) / previous_earning) * 100
        elif current_earning > 0:
            percentage_change = 100.0

        report_period = period
        if month:
            report_period = current_start.strftime('%B %Y')

        return {
            "period": report_period,
            "date_range": f"{current_start.strftime('%d %b')} - {current_end.strftime('%d %b, %Y')}",
            "graph_data": formatted_graph_data,
            "total_income": current_total_income,
            "total_outcome": abs(current_total_outcome),
            "total_earning": current_earning,
            "percentage_change": round(percentage_change, 2)
        }