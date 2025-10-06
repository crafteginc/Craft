from celery import shared_task
from .models import Product, Supplier
from orders.models import WishlistItem
from accounts.models import Follow
from notifications.services import create_notification_for_user


@shared_task
def send_product_creation_notifications_task(supplier_id, product_id):
    """
    Asynchronously sends notifications to all followers of a supplier
    when a new product is created.
    """
    try:
        supplier = Supplier.objects.get(id=supplier_id)
        product = Product.objects.get(id=product_id)
        
        # This can be slow if a supplier has many followers
        followers = Follow.objects.filter(supplier=supplier)
        
        for follow in followers:
            if hasattr(follow.follower, 'user'):
                user = follow.follower.user
                message = (
                    f"Your followed supplier {supplier.user.get_full_name} "
                    f"has a new product: {product.ProductName}"
                )
                create_notification_for_user(
                    user=user, 
                    message=message, 
                    related_object=product
                )
    except (Supplier.DoesNotExist, Product.DoesNotExist):
        pass # Handle cases where objects might be deleted before the task runs


@shared_task
def send_back_in_stock_notifications_task(product_id):
    """
    Asynchronously notifies all users who have a product on their wishlist
    when it comes back in stock.
    """
    try:
        product = Product.objects.get(id=product_id)
        
        # This query can be slow if a product is on many wishlists
        wishlist_items = WishlistItem.objects.filter(product=product).select_related('wishlist__user')
        
        for item in wishlist_items:
            user = item.wishlist.user
            message = f"Good news! '{product.ProductName}' is back in stock."
            create_notification_for_user(
                user=user, 
                message=message, 
                related_object=product
            )
    except Product.DoesNotExist:
        pass


@shared_task
def update_product_rating_task(product_id):
    """
    Asynchronously updates the average rating of a product.
    """
    try:
        product = Product.objects.get(id=product_id)
        product.update_rating()
    except Product.DoesNotExist:
        pass