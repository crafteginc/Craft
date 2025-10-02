from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from orders.permissions import IsSupplier
from .services import ReportService
from .serializers import EarningReportSerializer

class EarningReportView(APIView):
    """
    Provides an aggregated earning report for the authenticated supplier.
    Accepts a 'period' query parameter ('this_month', 'this_year', 'this_day').
    Also accepts a 'month' (in YYYY-MM format) for specific month reports.
    """
    permission_classes = [IsAuthenticated, IsSupplier]

    def get(self, request, *args, **kwargs):
        supplier_user = request.user

        period = request.query_params.get('period')
        month = request.query_params.get('month')  # Expects YYYY-MM

        if period and month:
            return Response(
                {"detail": "Provide either 'period' or 'month', not both."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if period:
            if period not in ['this_month', 'this_year', 'this_day']:
                return Response(
                    {"detail": "Invalid period. Choose 'this_month', 'this_year', or 'this_day'."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            report_data = ReportService.get_earning_report(supplier_user, period=period)
        elif month:
            try:
                # You can add further validation of the month format here if needed
                report_data = ReportService.get_earning_report(supplier_user, month=month)
            except ValueError:
                return Response(
                    {"detail": "Invalid month format. Use YYYY-MM."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Default to 'this_month' if no parameters are provided
            report_data = ReportService.get_earning_report(supplier_user, period='this_month')

        serializer = EarningReportSerializer(report_data)

        return Response(serializer.data, status=status.HTTP_200_OK)