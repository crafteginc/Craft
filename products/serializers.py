from rest_framework import serializers
from . models  import  *
from rest_framework.exceptions import AuthenticationFailed

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProImage
        fields = ["id","image"]

class ProductColorserializer(serializers.ModelSerializer):
    class Meta:
        model = ProColors
        fields = ["id", "Color"]

class ProductSizeserializer(serializers.ModelSerializer):
    class Meta:
        model = ProSizes
        fields = ["id", "Size"]

class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(max_length=100000, allow_empty_file=False, use_url=False),
        write_only=True
    )

    Colors = ProductColorserializer(many=True, read_only=True)
    uploaded_Colors = serializers.ListField(
        child=serializers.CharField(max_length=20),
        write_only=True
    )

    Sizes = ProductSizeserializer(many=True, read_only=True)
    uploaded_Sizes = serializers.ListField(
        child=serializers.CharField(max_length=20),
        write_only=True
    )

    class Meta:
        model = Product
        fields = ["id", 
                  "ProductName", 
                  "ProductDescription", 
                  "QuantityPerUnit", 
                  "Supplier", 
                  "UnitPrice", 
                  "UnitWeight", 
                  "Stock",
                  "OutOfStock", 
                  "DiscountAvailable", 
                  "Discount", 
                  "DiscountPercentage",
                  "Category",
                  "images", 
                  "uploaded_images", 
                  "Colors", 
                  "uploaded_Colors",
                  "Sizes",
                  "uploaded_Sizes",  
                  "Rating",]
        
        read_only_fields = ['Supplier']


    def create(self, validated_data):
        user = self.context['request'].user
        if not user.is_authenticated or not user.is_supplier:
            raise AuthenticationFailed("User is not a supplier.")
        validated_data['Supplier'] = user.supplier 
        uploaded_images = validated_data.pop('uploaded_images', [])
        uploaded_Colors = validated_data.pop('uploaded_Colors', [])
        uploaded_Sizes = validated_data.pop('uploaded_Sizes',[]) 
        

    # Create the product instance
        product = Product.objects.create(**validated_data)

        # Create product images
        for image in uploaded_images:
            ProImage.objects.create(product=product, image=image)

        # Create product colors
        for color in uploaded_Colors:
            colors = color.split(',')  # Split sizes by comma
            for color in colors:
                ProColors.objects.create(product=product, Color=color.strip())

        # Create product sizes
        for size in uploaded_Sizes:
            sizes = size.split(',')  # Split sizes by comma
            for size in sizes:
                ProSizes.objects.create(product=product, Size=size.strip())

        return product

class TrendingProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    supplier_full_name = serializers.CharField(source='Supplier.user.get_full_name', read_only=True)
    supplier_photo = serializers.ImageField(source='Supplier.SupplierPhoto', read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'images', 'ProductName', 'UnitPrice', 'supplier_full_name', 'supplier_photo']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data['images']:
            data['images'] = [data['images'][0]]  # Include only the first image
        return data

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['CategoryID','Title','Picture']

class CatProSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['CatPro']

class MatCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MatCategory
        fields = ['MatID','Title','Picture']

class MatCatProSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['MatCatPro']

class CollectionProductSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='pk')
    image = serializers.SerializerMethodField()
    price = serializers.DecimalField(source='UnitPrice', max_digits=10, decimal_places=2)
    name = serializers.CharField(source='ProductName') 

    class Meta:
        model = Product
        fields = ['id', 'name', 'image', 'price']  

    def get_image(self, obj):
        first_image = obj.images.first()
        if first_image and first_image.image:
            return first_image.image.url
        return None
    
class CollectionSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()  # For the first 4 images, if needed
    products = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        fields = ['id', 'name', 'images', 'products'] 
        
    def get_products(self, obj):
        items = obj.items.all()
        products = [item.product for item in items if item.product is not None]
        return CollectionProductSerializer(products, many=True, context=self.context).data

    def get_images(self, obj):
        first_items = obj.items.all()[:4]  
        image_urls = []
        for item in first_items:
            if item.product and item.product.images.exists():
                first_image = item.product.images.first()
                if first_image.image:
                    image_urls.append(first_image.image.url)
        return image_urls if image_urls else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        view = self.context.get('view')

        # Check if we are in the 'list' action (GET /product/collections/)
        if view and view.action == 'list':  # 'list' is the action for listing all collections
            data.pop('products', None)  # Remove products field for list view
        
        # Check if we are in the 'retrieve' action (GET /product/collections/{id}/)
        if view and view.action == 'retrieve':  # 'retrieve' is for a specific collection
            data.pop('images', None)  # Remove images field for specific collection view

        return data
    
class CollectionCreateUpdateSerializer(serializers.ModelSerializer):
    items = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), many=True)

    class Meta:
        model = Collection
        fields = ['id', 'name', 'items']

    def validate_items(self, value):
        """
        Ensure the products belong to the authenticated supplier and 
        check for duplicate products in the same collection.
        """
        supplier = self.context['request'].user.supplier  # Get the supplier from the request context
        invalid_products = [Product.id for Product in value if Product.Supplier != supplier]

        if invalid_products:
            raise serializers.ValidationError(
                f"You can only add your own products. Invalid product IDs: {invalid_products}"
            )

        # Check for duplicate products within the same collection
        collection = self.instance  # This will be set when updating a collection
        product_ids = [Product.id for Product in value]
        if collection:
            existing_product_ids = collection.items.values_list('product', flat=True)
            duplicate_products = set(product_ids) & set(existing_product_ids)

            if duplicate_products:
                raise serializers.ValidationError(
                    f"These products have already been added to the collection: {list(duplicate_products)}"
                )

        return value

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        collection = Collection.objects.create(**validated_data)
        for item in items_data:
            CollectionItem.objects.create(collection=collection, product=item)
        return collection

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)

        # Check if the user is adding products to the existing collection
        if items_data:
            # Check for duplicates in the current collection
            product_ids = [item.id for item in items_data]
            existing_product_ids = instance.items.values_list('product', flat=True)

            duplicate_products = set(product_ids) & set(existing_product_ids)
            if duplicate_products:
                raise serializers.ValidationError(
                    f"These products have already been added to the collection: {list(duplicate_products)}"
                )

            # Add new items to the collection
            for item in items_data:
                CollectionItem.objects.create(collection=instance, product=item)

        # Update collection name if provided
        instance.name = validated_data.get('name', instance.name)
        instance.save()

        return instance

class LatestCollectionSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    supplier_full_name = serializers.SerializerMethodField()
    supplier_photo = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        fields = ['id', 'image', 'name', 'supplier_full_name', 'supplier_photo']

    def get_image(self, obj):
        # Get the first image of the first product in the collection
        first_item = obj.items.first()
        if first_item and first_item.product.images.exists():
            first_image = first_item.product.images.first()
            if first_image.image:  # Ensure the image exists
                return first_image.image.url  # Return the URL of the image
        return None  # Return None if no image is available
    def get_supplier_full_name(self, obj):
        # Get the full name of the supplier who owns the collection
        supplier = obj.supplier
        if supplier and supplier.user:
            return f"{supplier.user.first_name} {supplier.user.last_name}"
        return None

    def get_supplier_photo(self, obj):
    # Ensure the supplier exists and has a SupplierPhoto
        supplier = obj.supplier
        if supplier and supplier.SupplierPhoto:
            # Access the actual file's URL
            return supplier.SupplierPhoto.url if supplier.SupplierPhoto else None
        return None
