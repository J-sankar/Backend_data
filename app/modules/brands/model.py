from ...extensions import mongo
from datetime import datetime
from uuid import uuid4

class BrandModel:
    collection = lambda: mongo.db.brands

    @staticmethod
    def get_all():
        brands = list(BrandModel.collection().find())
        for b in brands:
            b["_id"] = str(b["_id"])
        return brands

    @staticmethod
    def get_by_id(brand_id):
        brand = BrandModel.collection().find_one({"brand_id": brand_id})
        if brand:
            brand["_id"] = str(brand["_id"])
        return brand

    @staticmethod
    def create(data):
        # Add default fields
        data["brand_id"] = str(uuid4())
        data["created_at"] = datetime.utcnow()
        data["updated_at"] = datetime.utcnow()
        data.setdefault("verification_status", "Pending")

        res = BrandModel.collection().insert_one(data)
        return data

    @staticmethod
    def update(brand_id, update_data):
        update_data["updated_at"] = datetime.utcnow()
        BrandModel.collection().update_one(
            {"brand_id": brand_id},
            {"$set": update_data}
        )
        return BrandModel.get_by_id(brand_id)

    @staticmethod
    def delete(brand_id):
        result = BrandModel.collection().delete_one({"brand_id": brand_id})
        return result.deleted_count > 0
