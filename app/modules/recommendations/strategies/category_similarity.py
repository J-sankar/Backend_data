from ....extensions import mongo

def category_products(base_product: dict, limit=8) -> list:
    """
    Recommend top products from the same category.
    Ranked using a simple popularity score:
        popularity = 0.5*views + 0.3*sale_count + 0.2*rating
    Falls back to rating if no views/sale_count exist.
    """

    category = base_product.get("category")
    if not category:
        return []

    q = {
        "category": category,
        "product_id": {"$ne": base_product.get("product_id")},
        "stock": {"$gt": 0}
    }

    cursor = mongo.db.products.find(
        q,
        {
            "product_id": 1,
            "product_name": 1,
            "category": 1,
            "brand_id": 1,
            "price": 1,
            "images": 1,
            "rating": 1,
            "views": 1,
            "sale_count": 1
        }
    ).limit(50)  # fetch more, then rank

    products = list(cursor)
    if not products:
        return []

    # Compute popularity score
    for p in products:
        views = p.get("views", 0) or 0
        sales = p.get("sale_count", 0) or 0
        rating = p.get("rating", 0) or 0

        popularity = (0.5 * views) + (0.3 * sales) + (0.2 * rating)
        p["category_score"] = popularity

    # Sort in descending order
    products.sort(key=lambda x: x["category_score"], reverse=True)

    return products[:limit]
