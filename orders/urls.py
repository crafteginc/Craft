from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register('whishlists', views.WishlistViewSet, basename='whishlist')
router.register('whishlistitems', views.WishlistItemViewSet, basename='whishlistitem')
router.register('carts', views.CartViewSet, basename='cart')
router.register('cartitems', views.CartItemViewSet, basename='cartitem')
router.register('orders', views.OrderViewSet, basename="order")
router.register('coupons', views.CouponViewSet, basename='coupon')
router.register('shipments', views.ShipmentViewSet, basename='shipment')
router.register('return-orders-products', views.ReturnOrdersProductsViewSet, basename='return-orders-products')

urlpatterns = [
    path('', include(router.urls)),
    path('warehouses/', views.WarehouseListView.as_view(), name='warehouse-list'),
    
    # Supplier-specific endpoints remain.
    path('orders/supplier-orders/<uuid:pk>/', views.OrderViewSet.as_view({'get': 'retrieve_supplier_order'}), name='supplier-order-detail'),
    path('orders/supplier-orders/<uuid:pk>/ready-to-ship/', views.OrderViewSet.as_view({'post': 'ready_to_ship'}), name='ready-to-ship'),
    path('orders/completed-supplier-orders/', views.OrderViewSet.as_view({'get': 'list_completed_supplier_orders'}), name='completed-supplier-orders'),
    path('orders/uncompleted-supplier-orders/', views.OrderViewSet.as_view({'get': 'list_uncompleted_supplier_orders'}), name='uncompleted-supplier-orders'),
    # You could also add a list view for supplier's sales orders here if needed.
]