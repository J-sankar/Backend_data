from ...extensions import mongo
from datetime import datetime
from uuid import uuid4


class ProductModel:
    @staticmethod
    def get_collection():
        return mongo.db.products

    #  Create product
    @staticmethod
    def create(data):
        data["product_id"] = str(uuid4())
        data["created_at"] = datetime.utcnow()
        data["updated_at"] = datetime.utcnow()
        coll = ProductModel.get_collection()
        coll.insert_one(data)
        return ProductModel.get_by_id(data["product_id"])

    # Get all products
    @staticmethod
    def get_all(filters=None, skip=0, limit=10, sort=None):
        coll = ProductModel.get_collection()
        filters = filters or {}
        cursor = coll.find(filters)
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    # Get product by ID
    @staticmethod
    def get_by_id(product_id):
        return ProductModel.get_collection().find_one({"product_id": product_id})

    # Update product
    @staticmethod
    def update(product_id, update_data):
        update_data["updated_at"] = datetime.utcnow()
        result = ProductModel.get_collection().update_one(
            {"product_id": product_id},
            {"$set": update_data}
        )
        return result.modified_count

    # Delete product
    @staticmethod
    def delete(product_id):
        res = ProductModel.get_collection().delete_one({"product_id": product_id})
        return res.deleted_count

    # Get by brand
    @staticmethod
    def brand_products(brand_id):
        return list(ProductModel.get_collection().find({"brand_id": brand_id}))

    # Get by category
    @staticmethod
    def category_products(category):
        return list(ProductModel.get_collection().find({"category": category}))

    # Search products with filters, pagination, sorting
    @staticmethod
    def search(
        query=None,
        page=1,
        limit=10,
        sort="newest",
        category=None,
        brand_id=None,
        min_price=None,
        max_price=None,
        in_stock=None
    ):
        coll = ProductModel.get_collection()
        filters = {}

        # Keyword search
        if query:
            filters["$or"] = [
                {"product_name": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}},
                {"category": {"$regex": query, "$options": "i"}},
            ]

        # Optional filters
        if category:
            filters["category"] = category
        if brand_id:
            filters["brand_id"] = brand_id
        if in_stock:
            filters["stock"] = {"$gt": 0}
        if min_price is not None or max_price is not None:
            price_filter = {}
            if min_price is not None:
                price_filter["$gte"] = float(min_price)
            if max_price is not None:
                price_filter["$lte"] = float(max_price)
            filters["price"] = price_filter

        # Pagination
        page = max(1, int(page))
        limit = min(100, int(limit))
        skip = (page - 1) * limit

        # Sorting
        sort_map = {
            "price_asc": [("price", 1)],
            "price_desc": [("price", -1)],
            "newest": [("created_at", -1)],
            "oldest": [("created_at", 1)],
            "name_asc": [("product_name", 1)],
            "name_desc": [("product_name", -1)]
        }

        sort_spec = []
        for s in str(sort).split(","):
            s = s.strip()
            if s in sort_map:
                sort_spec.extend(sort_map[s])
        if not sort_spec:
            sort_spec = [("created_at", -1)]  # ✅ Fixed

        total = coll.count_documents(filters)
        cursor = coll.find(filters).sort(sort_spec).skip(skip).limit(limit)
        results = list(cursor)

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit,
            "products": results
        }

    # Get recent products
    @staticmethod
    def get_recent(limit=5):
        coll = ProductModel.get_collection()
        cursor = coll.find().sort("created_at", -1).limit(limit)
        return list(cursor)
