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
    

    def _candidate_query(self, prod:dict , price_tolerance = 0.25, in_stock = True, extra_filters = None ) ->dict  :
        q ={"product_id" :{"$ne": prod["product_id"]}}

        if in_stock :
            q["stock"] = {"$gt": 0}
        
        if prod["price"] is not None and price_tolerance is not None:
            low = prod["price"] * (1 - float(price_tolerance))
            high = prod["price"] * (1 + float(price_tolerance))
            q["price"] = {"$gte": low, "$lte": high}
        if extra_filters:
            q.update(extra_filters)
        return q

    def recommend_for_product(self, product_id:str, top_n:int = 10 , price_tolerance : float = 0.25, boost_ratings: bool = True , candidates_no : int = 2000, extra_filters:dict = None):
        logging.info("Starting to find recommendations...")
        base = mongo.db.products.find_one({"product_id": product_id})

        if not base:
            logging.warning(f"Product {product_id} not found.")
            return []

        #tfidf vector  for the base product
        base_vec = base.get("tfidf_vector")
        if not base_vec:
            if self._is_fitted:
                try:
                    self.update_single_product_vector(base)
                    base = mongo.db.products.find_one({"product_id": product_id}) 
                    base_vec = base["tfidf_vector"]
                except Exception as e:
                    logging.error(f"Failed to fit product: {str(e)}")
                    return []
            if not base_vec:
                return []
            
        q = self._candidate_query(base, price_tolerance=price_tolerance, extra_filters=extra_filters)
        q["tfidf_vector"] = {"$exists":True}

        candidates = list(mongo.db.products.find(q,{"product_id":1,"product_name":1, "tfidf_vector":1, "price":1, "rating":1}).limit(candidates_no))

        if not candidates:
            return []
        

        base_array = np.array(base_vec,dtype=float)
        candidates_array = np.array([c.get("tfidf_vector",[]) for c in candidates], dtype=float)

        cose_sim = candidates_array.dot(base_array)

        if boost_ratings:
            ratings = np.array([c.get("rating",0.0) for c in candidates],dtype=float)
            cose_sim = cose_sim + (ratings/10.0)
        

        idx_sorted = np.argsort(-cose_sim)[:top_n]

        top_candidates = [candidates[i] for i in idx_sorted]

        product_ids = [c["product_id"] for c in top_candidates]

        docs = list(mongo.db.products.find({"product_id":{"$in":product_ids}}))
        id_to_doc = {d["product_id"]: d for d in docs}
        ordered = [id_to_doc[pid] for pid in product_ids if pid in id_to_doc ]
        logging.info("Obtained top candidates")
        return ordered
        
