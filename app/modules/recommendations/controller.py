import logging
from flask import request, jsonify,Blueprint
from ...extensions import mongo
from ..products.responses.productListResponse import ProductListResponseSchema
from .strategies.product_similarity import ProductSimilarityRecommendor
from ..products.model import ProductModel

recommendations_bp = Blueprint("recommendations", __name__)
product_list_schema = ProductListResponseSchema(many=True)
recommender = ProductSimilarityRecommendor()
productModel = ProductModel()

@recommendations_bp.route("/product/<product_id>", methods=["GET"])
def recommend_for_product(product_id):
    try:
        product = productModel.get_by_id(product_id=product_id)
        n = int(request.args.get("n", 8))
        price_tolerance = float(request.args.get("price_tolerance", 0.25))
        category = request.args.get("category")
        extra_filters = {}
        if category:
            extra_filters["category"] = category.capitalize()

        results = recommender.recommend_for_product(
            product_id=product_id,
            top_n=n,
            price_tolerance=price_tolerance,
            boost_ratings=True,
            extra_filters=extra_filters
        )

        product_cards = [
            {
                "product_id": p.get("product_id"),
                "product_slug": p.get("product_slug"),
                "product_name": p.get("product_name"),
                "price": p.get("price"),
                "sale_price": p.get("sale_price"),
                "discount_percentage": p.get("discount_percentage"),
                "thumbnail": p.get("images", [None])[0],
                "stock": p.get("stock", 0),
                "rating": p.get("rating", 0.0),
                "rating_count": p.get("rating_count", 0),
                "category": p.get("category"),
                "brand_id": p.get("brand_id")
            } for p in results
        ]

        return jsonify({
            "product": product,
            "count": len(product_cards),
            "products": product_list_schema.dump(product_cards)
        }), 200

    except Exception as e:
        logging.error("Failed to get recommendations for %s: %s", product_id, e, exc_info=True)
        return jsonify({"error": "Failed to get recommendations"}), 500