from django.db import models
from products.models import Product
from django.contrib.auth import get_user_model

User = get_user_model()

class FrequentlyBoughtTogether(models.Model):
    """
    Stores pre-calculated recommendations for products that are often bought together.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='frequently_bought_with')
    recommended_product = models.ForeignKey(Product, on_delete=models.CASCADE)
    score = models.FloatField(default=0)  # Ranks the recommendations

    class Meta:
        unique_together = ('product', 'recommended_product')

    def __str__(self):
        return f"{self.product.ProductName} -> {self.recommended_product.ProductName}"

class UserProductView(models.Model):
    """
    Tracks products that a user has viewed.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} viewed {self.product.ProductName}"