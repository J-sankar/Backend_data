import logging
from ....extensions import mongo
from ..strategies.product_similarity import ProductSimilarityRecommendor
from app import create_app

def build_index():
    app = create_app()
    recommender = ProductSimilarityRecommendor()
    count = recommender.fit_and_store_vectors()
    logging.info(f"Indexed {count} products.")
    print(f"Indexed {count} products.")
    return count

if __name__ == '__main__':
    build_index()
