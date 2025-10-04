from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from products.models import Product
from .models import FrequentlyBoughtTogether, UserProductView
from collections import Counter

def get_collaborative_filtering_recommendations(product):
    """
    Finds users who viewed the given product and recommends other products
    they also viewed. This is for the "Customers Who Viewed This Also Viewed" feature.
    """
    # Find all users who viewed the target product
    users_who_viewed_product = UserProductView.objects.filter(product=product).values_list('user_id', flat=True)

    # Find all other products these users have viewed
    other_viewed_products = UserProductView.objects.filter(
        user_id__in=users_who_viewed_product
    ).exclude(
        product=product
    ).values_list('product_id', flat=True)

    # Count the occurrences of each product
    product_counts = Counter(other_viewed_products)

    # Get the most common products, ordered by frequency
    recommended_product_ids = [pid for pid, _ in product_counts.most_common(10)]
    
    # Fetch the actual product instances
    recommended_products = Product.objects.filter(id__in=recommended_product_ids)

    return recommended_products

def update_content_based_recommendations():
    """
    Calculates product similarity based on their text description and name.
    This is for the "Frequently Bought Together" feature and is run by your periodic Celery task.
    """
    products = Product.objects.all()
    if products.count() < 2:
        return

    # Create a corpus of text for each product
    product_texts = [f"{p.ProductName} {p.ProductDescription}" for p in products]

    # Vectorize the text using TF-IDF
    vectorizer = TfidfVectorizer(stop_words='english', min_df=2)
    tfidf_matrix = vectorizer.fit_transform(product_texts)

    # Calculate cosine similarity between all products
    cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

    # Clear old recommendations to avoid stale data
    FrequentlyBoughtTogether.objects.all().delete()

    # Populate the recommendation model
    for idx, product in enumerate(products):
        # Get similarity scores for the current product, excluding itself
        sim_scores = list(enumerate(cosine_sim[idx]))
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)[1:6]  # Get top 5 similar items

        for score_idx, score in sim_scores:
            if score > 0.1:  # Only save recommendations with a meaningful similarity
                FrequentlyBoughtTogether.objects.create(
                    product=product,
                    recommended_product=products[score_idx],
                    score=score
                )