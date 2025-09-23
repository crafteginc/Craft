from rest_framework import serializers

class EarningGraphPointSerializer(serializers.Serializer):
    month = serializers.CharField()
    income = serializers.DecimalField(max_digits=12, decimal_places=2)
    outcome = serializers.DecimalField(max_digits=12, decimal_places=2)

class EarningReportSerializer(serializers.Serializer):
    period = serializers.CharField()
    date_range = serializers.CharField()
    total_income = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_outcome = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_earning = serializers.DecimalField(max_digits=12, decimal_places=2)
    percentage_change = serializers.FloatField()
    graph_data = EarningGraphPointSerializer(many=True)