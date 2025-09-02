from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register('whishlists',views.WishlistViewSet, basename='whishlist')
router.register('whishlistitems', views.WishlistItemViewSet, basename='whishlistitem')
router.register('carts',views.CartViewSet, basename='cart')
router.register('cartitems', views.CartItemViewSet, basename='cartitem')
router.register('orders-history', views.OrdersHistoryViewSet, basename="orders-history")
router.register('return-orders-products', views.ReturnOrdersProductsViewSet, basename='return-orders-products')
router.register('orders', views.OrderViewSet, basename="order")
router.register('coupons', views.CouponViewSet, basename='coupon')


urlpatterns = [
    path('', include(router.urls)),
    path('warehouses/', views.WarehouseListView.as_view(), name='warehouse-list'),
]
