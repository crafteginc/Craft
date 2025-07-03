from django.urls import path
from rest_framework import routers
from django.conf.urls import include
from .views import *

router=routers.DefaultRouter()
router.register('products',ProductsViewSet)
router.register('supplierproducts', SupplierProductsViewSet, basename='SupplierProducts') 
router.register('collections', CollectionViewSet, basename='collection')

urlpatterns = [
    
    path('',include(router.urls)),
    path('productsByFollowedSuppliers/',FollowedSuppliersProducts.as_view(),name='productsByFollowedSuppliers'),
    path('latest-collections/', LatestFollowedSuppliersCollections.as_view(), name='latest_followed_suppliers_collections'),
    path('latest-collections/<int:collection_id>/', CollectionDetailView.as_view(), name='collection-detail'),
    path('products-by-category/<slug:Slug>/',ProductsByCategory.as_view()),
    path('categories/',Categories.as_view()),
    path('materials/',Mataterials.as_view()),
    path('products-by-materials/<slug:Slug>/',ProductsByMaterials.as_view()),

]
