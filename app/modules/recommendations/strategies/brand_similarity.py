from ....extensions import mongo

def brand_products(base_product:dict , limit = 8) ->list :
    brand_id = base_product.get("brand_id")

    if not brand_id:
        return []
    
    q = {
        "brand_id": brand_id,
        "product_id": {"$ne": base_product.get("product_id")},
        "stock": {"$gt" :0},
        "rating": {"$gte": 3.0}
    }

    sort =[("rating", -1)]

    product_list = list(mongo.db.products.find(q,
                    {
                        "product_id":1,
                        "product_name":1,
                        "brand_id": 1,
                        "rating": 1,
                        "price": 1,
                        "images" : 1,
                        "category":1
                    }    ).sort(sort).limit(limit))
    for p in product_list:
        p["brand_score"] = 1.0
    return product_list
    



