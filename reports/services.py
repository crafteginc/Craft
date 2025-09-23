import datetime
from decimal import Decimal
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from returnrequest.models import Transaction

def get_date_range_for_period(period_string: str):
    """
    Calculates the start and end dates for the current and previous period.
    """
    today = timezone.now().date()
    
    if period_string == 'this_month':
        # Current Period
        current_start = today.replace(day=1)
        next_month = (current_start + datetime.timedelta(days=32)).replace(day=1)
        current_end = next_month - datetime.timedelta(days=1)
        
        # Previous Period
        prev_end = current_start - datetime.timedelta(days=1)
        prev_start = prev_end.replace(day=1)

    elif period_string == 'this_year':
        # Current Period
        current_start = today.replace(month=1, day=1)
        current_end = today.replace(month=12, day=31)

        # Previous Period
        prev_start = current_start.replace(year=current_start.year - 1)
        prev_end = current_end.replace(year=current_end.year - 1)

    else: # Default to this_month
        return get_date_range_for_period('this_month')

    return current_start, current_end, prev_start, prev_end


class ReportService:

    @staticmethod
    def get_earning_report(supplier_user, period: str):
        # Define what constitutes income and outcome for a supplier
        income_types = [Transaction.TransactionType.PURCHASED_PRODUCTS]
        outcome_types = [Transaction.TransactionType.RETURN_DEBIT]

        current_start, current_end, prev_start, prev_end = get_date_range_for_period(period)

        # 1. Get graph data for the current period, aggregated by month
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

        # Format graph data for the frontend
        formatted_graph_data = [
            {
                "month": item['month'].strftime("%b"), # e.g., "Nov"
                "income": item['income'] or 0,
                "outcome": abs(item['outcome'] or 0) # Outcome is stored negative, so take absolute
            }
            for item in graph_data
        ]
        
        # 2. Calculate totals for the current period
        current_totals = transactions.aggregate(
            total_income=Sum('amount', filter=Q(transaction_type__in=income_types)),
            total_outcome=Sum('amount', filter=Q(transaction_type__in=outcome_types))
        )
        current_total_income = current_totals.get('total_income') or Decimal('0.0')
        current_total_outcome = current_totals.get('total_outcome') or Decimal('0.0')
        current_earning = current_total_income + current_total_outcome # Outcome is negative, so we add

        # 3. Calculate totals for the previous period to find the percentage change
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

        # 4. Calculate percentage change
        percentage_change = 0
        if previous_earning > 0:
            percentage_change = ((current_earning - previous_earning) / previous_earning) * 100
        elif current_earning > 0:
            percentage_change = 100.0 # From zero to positive is a 100% gain for simplicity

        return {
            "period": period,
            "date_range": f"{current_start.strftime('%d %b')} - {current_end.strftime('%d %b, %Y')}",
            "graph_data": formatted_graph_data,
            "total_income": current_total_income,
            "total_outcome": abs(current_total_outcome),
            "total_earning": current_earning,
            "percentage_change": round(percentage_change, 2)
        }