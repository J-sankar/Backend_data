from flask import request, jsonify
from marshmallow import ValidationError
from .schema import BrandSchema
from .model import BrandModel
from datetime import datetime
import logging
from ..utils.identifiers import slugify, get_brand_id
from pymongo import InsertOne
from pymongo.errors import BulkWriteError

logger = logging.getLogger(__name__)

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
        slug = slugify(data["brand_name"])
        existingSlug = BrandModel.collection().find_one({"slug":slug})
        if existingSlug:
            logger.error("Name exists already")
            return jsonify({"error": "Brand name already exists"}),400

        # Create new brand
        brand = BrandModel.create(validated)
        logger.info("Brand created: %s", brand.get("brand_id"))
        return jsonify({
            "message": "Brand created successfully",
            "brand": brand
        }), 201

    except ValidationError as err:
        logger.debug("Validation error while creating brand: %s", err.messages)
        return jsonify({"error": err.messages}), 400
    except Exception:
        logger.exception("Unexpected error while creating brand")
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
                "logo": b.get("brand_logo"),
                "slug": b.get("slug")
            }
            for b in brands
        ]
        return jsonify(simplified_brands), 200
    except Exception:
        logger.exception("Failed to fetch brands")
        return jsonify({"error": "Failed to fetch brands"}), 500

BATCH_SIZE = 50

def bulk_create_brands():
    start_time = datetime.utcnow()
    results = []
    
    try:
        data = request.get_json()

        if not isinstance(data, list) or len(data) == 0:
            logger.warning("Bulk brand create received empty or invalid list.")
            return jsonify({"error": "Input must be a non-empty list"}), 400

        total_items = len(data)
        logger.info(f"Starting bulk create for {total_items} brands.")

        # --- PROCESS IN BATCHES ---
        for i in range(0, total_items, BATCH_SIZE):
            batch = data[i : i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            
            logger.info(f"Processing Batch {batch_num} (Items {i} to {i + len(batch)})")

            valid_items_map = {} # Map to store valid items keyed by slug/email for easy lookup
            batch_slugs = set()
            batch_emails = set()
            
            # 1. Validation & Preparation Phase
            for item in batch:
                try:
                    # Validate Schema
                    validated = brand_schema.load(item)
                    
                    # Generate Slug
                    slug = slugify(validated["brand_name"])
                    email = validated["email"]
                    
                    # Check for duplicates WITHIN the current upload batch
                    if slug in batch_slugs:
                        raise ValidationError({"brand_name": ["Duplicate brand name in this batch"]})
                    if email in batch_emails:
                        raise ValidationError({"email": ["Duplicate email in this batch"]})

                    # Prepare final object
                    validated["slug"] = slug
                    if "brand_id" not in validated:
                         # Assuming your BrandModel has a generate_id() or similar
                         # If using ObjectId, you can leave it to Mongo or generate here
                        validated["brand_id"] = get_brand_id() 
                    
                    validated["created_at"] = datetime.utcnow()
                    validated["updated_at"] = datetime.utcnow()

                    # Add to tracking sets
                    batch_slugs.add(slug)
                    batch_emails.add(email)
                    
                    # Store for next step (Processing)
                    # We store list in case of edge case, but slug should be unique
                    valid_items_map[slug] = validated

                except ValidationError as ve:
                    results.append({
                        "input": item.get("brand_name", "Unknown"),
                        "error": ve.messages,
                        "status": "validation_error"
                    })

            # 2. Database Duplicate Check (The Optimization)
            # Instead of 50 queries, we do 1 query to find ANY existing duplicates
            if batch_slugs:
                existing_docs = BrandModel.collection().find({
                    "$or": [
                        {"slug": {"$in": list(batch_slugs)}},
                        {"email": {"$in": list(batch_emails)}}
                    ]
                }, {"slug": 1, "email": 1, "_id": 0})
                
                # Create a blocklist of existing credentials
                existing_slugs = set()
                existing_emails = set()
                
                for doc in existing_docs:
                    if "slug" in doc: existing_slugs.add(doc["slug"])
                    if "email" in doc: existing_emails.add(doc["email"])
                
                # Remove duplicates from our valid list and log errors
                keys_to_remove = []
                for slug, val_item in valid_items_map.items():
                    if slug in existing_slugs:
                        results.append({"status": "error", "message": "Brand name already exists", "brand": val_item["brand_name"]})
                        keys_to_remove.append(slug)
                    elif val_item["email"] in existing_emails:
                        results.append({"status": "error", "message": "Email already exists", "email": val_item["email"]})
                        keys_to_remove.append(slug)
                
                for k in keys_to_remove:
                    del valid_items_map[k]

            # 3. Bulk Write Phase
            operations = []
            for validated_item in valid_items_map.values():
                operations.append(InsertOne(validated_item))

            if operations:
                try:
                    # Using InsertOne because we filtered duplicates manually
                    BrandModel.collection().bulk_write(operations, ordered=False)
                    
                    # Success logging
                    for op in operations:
                        doc = op._doc
                        results.append({
                            "status": "created",
                            "brand_id": doc.get("brand_id"),
                            "brand_name": doc.get("brand_name")
                        })
                    logger.info(f"Batch {batch_num}: Successfully created {len(operations)} brands.")

                except BulkWriteError as bwe:
                    logger.error(f"Batch {batch_num}: Bulk write error: {bwe.details}")
                    results.append({"status": "batch_write_error", "details": str(bwe)})
                except Exception as e:
                    logger.critical(f"Batch {batch_num}: Critical DB failure: {e}")
                    continue

        # Final Summary
        duration = (datetime.utcnow() - start_time).total_seconds()
        success_count = sum(1 for r in results if r['status'] == 'created')
        
        return jsonify({
            "message": "Bulk brand creation completed",
            "count": len(results),
            "success_count": success_count,
            "results": results
        }), 207 if success_count < total_items else 201

    except Exception as e:
        logger.error(f"Global Brand Bulk Error: {e}", exc_info=True)
        return jsonify({"error": "Critical server error"}), 500

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

    except Exception:
        logger.exception("Update failed for brand: %s", brand_id)
        return jsonify({"error": "Update failed"}), 500


def delete_brand(brand_id):
    try:
        success = BrandModel.delete(brand_id)
        if not success:
            return jsonify({"error": "Brand not found"}), 404
        return jsonify({"message": "Brand deleted successfully"}), 200
    except Exception:
        logger.exception("Failed to delete brand: %s", brand_id)
        return jsonify({"error": "Deletion failed"}), 500
