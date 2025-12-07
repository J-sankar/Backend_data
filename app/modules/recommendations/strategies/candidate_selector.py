from ....extensions import mongo

def fetch_candidates(prod:dict , price_tolerance = 0.25, in_stock = True, extra_filters = None , limit = 2000) ->list  :
        q ={"product_id" :{"$ne": prod["product_id"]}}

        if in_stock :
            q["stock"] = {"$gt": 0}
        
        if prod["price"] is not None and price_tolerance is not None:
            low = prod["price"] * (1 - float(price_tolerance))
            high = prod["price"] * (1 + float(price_tolerance))
            q["price"] = {"$gte": low, "$lte": high}
        if extra_filters:
            q.update(extra_filters)
        return list(
        mongo.db.products.find(
            q, {"product_id": 1, "product_name": 1, "tfidf_vector": 1, "price": 1, "rating": 1}
        ).limit(limit)
    )