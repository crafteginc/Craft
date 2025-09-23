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
    Accepts a 'period' query parameter ('this_month' or 'this_year').
    """
    permission_classes = [IsAuthenticated, IsSupplier]

    def get(self, request, *args, **kwargs):
        supplier_user = request.user
        
        # Get the period from query params, default to 'this_month'
        period = request.query_params.get('period', 'this_month')
        if period not in ['this_month', 'this_year']:
            return Response(
                {"detail": "Invalid period. Choose 'this_month' or 'this_year'."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Delegate all logic to the service
        report_data = ReportService.get_earning_report(supplier_user, period)

        # Serialize the data for a consistent response structure
        serializer = EarningReportSerializer(report_data)
        
        return Response(serializer.data, status=status.HTTP_200_OK)