import logging
from flask import Blueprint, jsonify, request, current_app
from ...extensions import mongo
from ..products.responses.productListResponse import ProductListResponseSchema
from ..recommendations.strategies.product_similarity import ProductSimilarityRecommendor
from ..recommendations.strategies.candidate_selector import fetch_candidates
from ..recommendations.strategies.brand_similarity import brand_products
from ..recommendations.strategies.category_similarity import category_products
from ..recommendations.hybrid.hybrid_aggregrator import build_hybrid_output

# 1. Setup Logging
logger = logging.getLogger(__name__)

recommendations_bp = Blueprint("recommendations", __name__)
product_list_schema = ProductListResponseSchema(many=True)
# Ideally, have a schema for single objects if the above is strictly for lists
# single_product_schema = ProductListResponseSchema(many=False) 
similarity_engine = ProductSimilarityRecommendor()

@recommendations_bp.route("/product/<product_id>", methods=["GET"])
def recommend_for_product(product_id):
    # Context for logs to easily trace requests
    log_ctx = f"[Product: {product_id}]"
    logger.info(f"{log_ctx} Processing recommendation request")

    try:
        # 2. Input Validation (Query Params)
        try:
            top_n = int(request.args.get("n", 8))
            price_tolerance = float(request.args.get("price_tolerance", 0.25))
        except ValueError as e:
            logger.warning(f"{log_ctx} Invalid query parameters: {e}")
            return jsonify({"error": "Invalid parameters for 'n' or 'price_tolerance'"}), 400

        # 3. Fetch Base Product
        try:
            base_product = mongo.db.products.find_one({"product_id": product_id})
        except Exception as e:
            logger.error(f"{log_ctx} Database connection failed: {str(e)}")
            return jsonify({"error": "Database service unavailable"}), 503

        if not base_product:
            logger.warning(f"{log_ctx} Product not found in database")
            return jsonify({"error": "Product not found"}), 404

        # 4. Fetch Candidates
        logger.debug(f"{log_ctx} Fetching candidates with tolerance {price_tolerance}")
        candidates = fetch_candidates(base_product, price_tolerance)
        
        similar_products = []
        
        # 5. Similarity Calculation (Defensive Check)
        if not candidates:
            logger.info(f"{log_ctx} No candidates found within constraints. Skipping TF-IDF.")
        else:
            try:
                # Ensure candidates actually have vectors before computing
                candidate_vecs = [c.get("tfidf_vector") for c in candidates if "tfidf_vector" in c]
                
                if len(candidate_vecs) != len(candidates):
                    logger.warning(f"{log_ctx} Size mismatch: Some candidates missing 'tfidf_vector'")
                    # You might want to filter candidates here to match vecs
                
                if candidate_vecs:
                    similarity_scores = similarity_engine.compute_cosine_scores(
                        base_product.get("tfidf_vector", []), candidate_vecs
                    )

                    # Sort and pick top N
                    ranked_idx = similarity_scores.argsort()[::-1][:top_n]

                    for idx in ranked_idx:
                        # Safety check for index out of bounds
                        if idx < len(candidates):
                            candidate = candidates[idx]
                            candidate["similarity_score"] = float(similarity_scores[idx])
                            similar_products.append(candidate)
            except Exception as e:
                # If math/numpy fails, log it but don't crash the whole request. 
                # We can still return brand/category recommendations.
                logger.error(f"{log_ctx} TF-IDF computation failed: {str(e)}", exc_info=True)

        logger.info(f"{log_ctx} Identified {len(similar_products)} content-based matches")

        # 6. Fallback/Auxiliary Strategies
        try:
            brand_recommendations = brand_products(base_product, limit=top_n)
            category_recommendations = category_products(base_product, limit=top_n)
        except Exception as e:
            logger.error(f"{log_ctx} Auxiliary strategy failed: {str(e)}")
            brand_recommendations = []
            category_recommendations = []

        # 7. Hybrid Aggregation
        try:
            final_list = build_hybrid_output(similar_products, brand_recommendations, category_recommendations)
        except Exception as e:
            logger.error(f"{log_ctx} Hybrid aggregation failed: {str(e)}")
            # Fallback to just returning what we have
            final_list = similar_products

        # 8. Response Construction
        response_payload = {
            "product": product_list_schema.dump([base_product])[0], # Dump as list, grab first item to satisfy many=True
            "products": {
                "similar_products": product_list_schema.dump(final_list),
                "same_brand": product_list_schema.dump(brand_recommendations),
                "same_category": product_list_schema.dump(category_recommendations),
                "final": product_list_schema.dump(final_list)
            }
        }

        logger.info(f"{log_ctx} Successfully generated recommendations")
        return jsonify(response_payload), 200

    except Exception as e:
        # 9. Global Safety Net
        logger.critical(f"{log_ctx} Unhandled internal error: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred processing recommendations"}), 500