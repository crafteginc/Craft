from django import forms
from django.contrib import admin, messages
from django.shortcuts import render
from django.utils.html import format_html

from .models import BalanceWithdrawRequest, ReturnRequest, Transaction
from .services import BalanceService

@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'reason', 'status', 'amount', 'created_at')
    list_filter = ('status', 'reason', 'created_at')
    search_fields = ('user__username', 'order__order_number', 'product__name', 'supplier__user__username')
    readonly_fields = ('id', 'image_thumbnail', 'created_at', 'updated_at', 'amount')
    autocomplete_fields = ['user', 'order', 'product', 'supplier']
    
    fieldsets = (
        ('Core Info', {
            'fields': ('user', 'order', 'product', 'supplier', 'quantity', 'status', 'reason', 'amount')
        }),
        ('User Evidence', {
            'fields': ('image', 'image_thumbnail')
        }),
    )

    def image_thumbnail(self, obj):
        if obj.image:
            return format_html('<a href="{0}"><img src="{0}" style="max-width: 150px; max-height: 150px;" /></a>', obj.image.url)
        return "No Image"
    image_thumbnail.short_description = 'Image Thumbnail'

class RejectForm(forms.Form):
    admin_notes = forms.CharField(widget=forms.Textarea, required=True)

@admin.register(BalanceWithdrawRequest)
class BalanceWithdrawRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'transfer_status', 'risk_score', 'created_at')
    list_filter = ('transfer_status', 'transfer_type', 'created_at')
    search_fields = ('user__username', 'transfer_number')
    readonly_fields = ('id', 'user', 'related_transaction', 'risk_score', 'created_at', 'updated_at')
    list_select_related = ['user']
    
    fieldsets = (
        ('Request Details', {
            'fields': ('user', 'amount', 'transfer_status', 'transfer_type', 'transfer_number', 'notes')
        }),
        ('Fraud & Admin Section', {
            'fields': ('risk_score', 'admin_notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )

    actions = ['approve_selected_requests', 'reject_selected_requests', 'process_approved_requests']

    @admin.action(description="Manually Approve selected requests")
    def approve_selected_requests(self, request, queryset):
        for req in queryset.filter(transfer_status=BalanceWithdrawRequest.TransferStatus.AWAITING_APPROVAL):
            BalanceService.approve_withdrawal(req, request.user)
        self.message_user(request, "Selected requests approved.", messages.SUCCESS)

    @admin.action(description="Reject selected requests")
    def reject_selected_requests(self, request, queryset):
        # This action now uses the intermediate page
        if 'apply' in request.POST:
            form = RejectForm(request.POST)
            if form.is_valid():
                admin_notes = form.cleaned_data['admin_notes']
                for req in queryset:
                    BalanceService.reject_withdrawal(req, request.user, admin_notes)
                self.message_user(request, "Selected requests have been rejected.", messages.SUCCESS)
                return
        
        form = RejectForm()
        return render(request, 'admin/reject_intermediate.html', context={'requests': queryset, 'form': form})

    @admin.action(description="Process approved requests (Send to Gateway)")
    def process_approved_requests(self, request, queryset):
        for req in queryset.filter(transfer_status=BalanceWithdrawRequest.TransferStatus.APPROVED):
            BalanceService.process_approved_request(req)
        self.message_user(request, "Approved requests sent for processing.", messages.SUCCESS)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'transaction_type', 'amount', 'created_at', 'related_object')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('user__username',)
    readonly_fields = ('id', 'created_at')
    autocomplete_fields = ['user']