from flask import request, jsonify
from marshmallow import ValidationError
from .schema import BrandSchema
from .model import BrandModel

brand_schema = BrandSchema()

def add_brand():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Missing request body"}), 400

        # Validate input using Marshmallow
        validated = brand_schema.load(data)
    
        # Optional: check duplicate email
        existing = BrandModel.collection().find_one({"email": validated["email"]})
        if existing:
            return jsonify({"error": "Email already registered"}), 400

        # Create new brand
        brand = BrandModel.create(validated)
        print(brand)
        return jsonify({
            "message": "Brand created successfully",
            "brand": brand_schema.dump(brand)
        }), 201

    except ValidationError as err:
        return jsonify({"error": err.messages}), 400
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Something went wrong"}), 500


def get_brands():
    try:
        brands = BrandModel.get_all()
        if not brands:
            return jsonify({"error":"No brands available yet"}), 404    
        # ✅ build a new filtered list
        simplified_brands = [
            {
                "brand_id": b.get("brand_id"),
                "name": b.get("brand_name"),
                "logo": b.get("brand_logo")
            }
            for b in brands
        ]
        return jsonify(simplified_brands), 200
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Failed to fetch brands"}), 500


def get_brand_by_id(brand_id):
    brand = BrandModel.get_by_id(brand_id)
    if not brand:
        return jsonify({"error": "Brand not found"}), 404
    return jsonify(brand_schema.dump(brand)), 200


def update_brand(brand_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing request body"}), 400

        updated = BrandModel.update(brand_id, data)
        if not updated:
            return jsonify({"error": "Brand not found"}), 404

        return jsonify({
            "message": "Brand updated successfully",
            "brand": brand_schema.dump(updated)
        }), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Update failed"}), 500


def delete_brand(brand_id):
    success = BrandModel.delete(brand_id)
    if not success:
        return jsonify({"error": "Brand not found"}), 404
    return jsonify({"message": "Brand deleted successfully"}), 200
