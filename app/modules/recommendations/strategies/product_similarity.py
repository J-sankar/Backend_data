import logging
import numpy as np
from sklearn.feature_extraction.text  import TfidfVectorizer
from ....extensions import mongo
from pymongo import UpdateOne

#TF-IDF params tuned product text
TFIDF_PARAMS = {
    "ngram_range": (1, 2),
    "max_df": 0.8,
    "min_df": 2,
    "max_features": 20000,
    "stop_words": "english",
    "norm": "l2",
}

class ProductSimilarityRecommendor:
    def  __init__(self, vectorizer: TfidfVectorizer = None):
        self.vectorizer = vectorizer or TfidfVectorizer(**TFIDF_PARAMS)
        self._is_fitted = False

    def get_brand_map(self):
        """
        Fetches brand_id -> brand_name mapping safely.
        """
        try:
            cursor = mongo.db.brands.find({}, {"brand_id": 1, "brand_name": 1, "_id": 0})
        except Exception as e:
            logging.error(f"MongoDB not initialized yet: {e}")
            return {}   # Safe fallback

        brand_map = {}

        for doc in cursor:
            brand_id = doc.get("brand_id")
            brand_name = doc.get("brand_name")

            if brand_id and brand_name:
                brand_map[brand_id] = brand_name

        logging.info(f"Brand map loaded: {len(brand_map)} brands.")
        return brand_map

    
    def _build_text(self, p:dict,brand_map: dict = None)-> str:
        parts = []
        parts.append(p.get("product_name", "") or "")
        parts.append(p.get("category", "") or "")
        parts.append(p.get("description", "") or "")
        p_brand_id = p.get("brand_id") # Get "BR-001"
        
        if brand_map and p_brand_id in brand_map:
            # If we found the ID in our map, grab the real name ("Nike")
            real_name = brand_map[p_brand_id]
            parts.append(real_name)
        if (p.get("tags")):
            parts.append(" ".join(p.get("tags")))
        return " ".join(str(x) for x in parts if x)
    

    def fit_and_store_vectors(self):
        """
        Fit TF-IDF on the provided products (iterable) and store dense vectors in MongoDB.
        Use this once initially or run as a periodic reindex.
        Returns number indexed.
        """
        logging.info("Step 1: Loading Brand Map...")
        # FIX: Actually call the function and store the result
        brand_map = self.get_brand_map()
        logging.info(f"Loaded {len(brand_map)} brands.")

        logging.info("Started tf-idf training...")
        products_cursor = mongo.db.products.find({},{"product_name":1, "description":1, "tags":1, "category":1,"brand_id":1 }).sort("_id",1)

        try:
            # Peek at the first item to see if it exists
            first_item = products_cursor[0] 
            products_cursor.rewind() # Reset cursor for the generator
        except IndexError:
             logging.warning("No products found to train on.")
             return 0

        docs = (self._build_text(p,brand_map = brand_map) for p in products_cursor)

        X = self.vectorizer.fit_transform(docs)  # sparse matrix
        self._is_fitted = True
        logging.info("Training complete. Vocabulary size: %d", len(self.vectorizer.vocabulary_))



        logging.info("Updating database...")

        cursor = mongo.db.products.find({}, {"product_id": 1}).sort("_id",1) # Only need ID now
    
        operations = []
        batch_size = 1000
        total_updated = 0
        for i, p in enumerate(cursor):
            vec = X[i].toarray().ravel().astype(float).tolist()
            action = UpdateOne({"product_id":p["product_id"]} ,{"$set": {"tfidf_vector": vec}})
            operations.append(action)

            if len(operations) >= batch_size:
                mongo.db.products.bulk_write(operations)
                total_updated += len(operations)
                operations = [] # Clear memory
                logging.info(f"Updated {total_updated} products...")

        if operations:
            total_updated += len(operations)
            result = mongo.db.products.bulk_write(operations)
            logging.info(f"Final batch updated. Total: {total_updated}")
        
        return total_updated
        

    def transform_text(self, text: str):
        """Return dense numpy vector for a raw text. Vectorizer must be fitted."""
        if not self._is_fitted:
            raise RuntimeError("Vectorizer not fitted. Run fit_and_store_vectors() first.")
        X = self.vectorizer.transform([text])
        return X.toarray().ravel().astype(float)
    
    def update_single_product_vector(self, product_doc: dict):
        """
        Compute and store TF-IDF vector for a single product using current vocabulary.
        Call this after create/update. If vectorizer not fitted, raise to signal indexing first.
        """
        if not self._is_fitted:
            raise RuntimeError("Vectorizer not fitted. Run full indexing before update_single_product_vector.")
        text = self._build_text(product_doc)
        vec = self.transform_text(text)
        mongo.db.products.update_one(
            {"product_id": product_doc["product_id"]},
            {"$set": {"tfidf_vector": vec.tolist()}}
        )
        return True
    

    

     # ---------------------------------------------------------
    # COSINE SIMILARITY (PURE MATH)
    # ---------------------------------------------------------
    def compute_cosine_scores(self, base_vec, candidate_vecs):
        base = np.array(base_vec, dtype=float)
        mat = np.array(candidate_vecs, dtype=float)
        return mat.dot(base)
        
