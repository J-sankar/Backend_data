import logging
from flask import request, jsonify
from marshmallow import ValidationError
from ...extensions import mongo
from datetime import datetime
from .schema import ProductSchema
from .model import ProductModel
from .responses.productListResponse import ProductListResponseSchema
from .responses.productDetailsResponse import ProductDetailResponseSchema
from ..recommendations.strategies.product_similarity import ProductSimilarityRecommendor
from ..utils.identifiers import slugify, get_product_id
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError

product_schema = ProductSchema()
product_list_schema = ProductListResponseSchema(many=True)
product_details_schema = ProductDetailResponseSchema()
rec = ProductSimilarityRecommendor()
logger = logging.getLogger(__name__)

# ➕ Create new product
def create_product():
    try:
        data = request.get_json()
        if not data:
            logging.warning("Create Product: No input data received.")
            return jsonify({"error": "No details entered"}), 400

        validated_data = product_schema.load(data)
        product_name = validated_data["product_name"]
        brand_id = validated_data["brand_id"]
        existing = mongo.db.products.find_one({
            "brand_id": brand_id,
            "product_name": {"$regex": f"^{product_name}$", "$options": "i"}
        })

    
        if existing:
            set_payload = {}
            for k, v in validated_data.items():
                if k in ("_id", "product_id", "created_at"):
                    continue
                set_payload[k] = v

            updated = ProductModel.update(existing["product_id"], set_payload)
            updated_product = ProductModel.get_by_id(existing["product_id"])
            
            if updated != 0:
                try:
                    rec.update_single_product_vector(updated_product)
                except RuntimeError:
                    pass

                logging.info(f"Product updated: {product_name} (Brand: {brand_id})")
                return jsonify({
                "message": "Product already existed → updated successfully",
                "product": product_details_schema.dump(updated_product)
                }), 200
        
        product = ProductModel.create(validated_data)

        
        try:
            rec.update_single_product_vector(product)
        except RuntimeError:
            pass
        
        logging.info(f"Product created successfully: {product.get('product_name')} (ID: {product.get('product_id')})")
        
        return jsonify({
            "message": "Product created successfully",
            "product": product_details_schema.dump(product)
        }), 201

    except ValidationError as err:
        logging.warning(f"Validation error while creating product: {err.messages}")
        return jsonify({"errors": err.messages}), 400
    except Exception as e:
        logging.error(f"Error creating product: {e}", exc_info=True)
        return jsonify({"error": "Failed to create product"}), 500

#Bulk creating (Testing purpose)
BATCH_SIZE = 50

def bulk_create_products():
    start_time = datetime.utcnow()
    results = []

    try:
        data = request.get_json()

        if not isinstance(data, list) or len(data) == 0:
            logger.warning("Bulk create received empty or invalid list.")
            return jsonify({"error": "Input must be a non-empty list"}), 400

        total_items = len(data)
        logger.info(f"Starting bulk create for {total_items} items. Batch size: {BATCH_SIZE}")

        # --- PROCESS IN BATCHES ---
        for i in range(0, total_items, BATCH_SIZE):
            batch = data[i : i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1

            logger.info(f"Processing Batch {batch_num} (Items {i} to {i + len(batch)})")

            operations = []
            batch_validated_docs = []

            # ------------ VALIDATION & PREP PHASE ------------
            for item in batch:
                try:
                    validated = product_schema.load(item)

                    # ---- Generate required fields manually (because dump_only removes them) ----
                    if "product_id" not in validated:
                        validated["product_id"] = get_product_id()

                    validated["product_slug"] = slugify(validated["product_name"])
                    validated["updated_at"] = datetime.utcnow()
                    validated["created_at"] = validated.get("created_at", datetime.utcnow())

                    # ---- Remove immutable fields from update block ----
                    update_fields = validated.copy()
                    update_fields.pop("created_at", None)
                    update_fields.pop("product_id", None)

                    # ---- UPSERT Operation ----
                    operations.append(
                        UpdateOne(
                            {
                                "brand_id": validated["brand_id"],
                                "product_name": {
                                    "$regex": f"^{validated['product_name']}$",
                                    "$options": "i"
                                }
                            },
                            {
                                "$set": update_fields,
                                "$setOnInsert": {
                                    "created_at": validated["created_at"],
                                    "product_id": validated["product_id"]
                                }
                            },
                            upsert=True
                        )
                    )

                    batch_validated_docs.append(validated)

                except ValidationError as ve:
                    results.append({
                        "input": item,
                        "error": ve.messages,
                        "status": "validation_error"
                    })
                    logger.error(f"Validation error in batch {batch_num}: {ve.messages}")

            # Debug operations count
            logger.warning(f"Batch {batch_num}: OPERATIONS BUILT = {len(operations)}")

            # ------------ DATABASE WRITE PHASE ------------
            if operations:
                try:
                    write_result = mongo.db.products.bulk_write(operations, ordered=False)

                    logger.info(
                        f"Batch {batch_num}: Bulk write OK. "
                        f"Inserted={write_result.inserted_count}, "
                        f"Upserted={len(write_result.upserted_ids)}, "
                        f"Modified={write_result.modified_count}"
                    )

                    # Add success entries
                    for doc in batch_validated_docs:
                        results.append({
                            "status": "created_or_updated",
                            "product_id": doc["product_id"],
                            "name": doc["product_name"]
                        })

                except BulkWriteError as bwe:
                    logger.error(f"Batch {batch_num}: BulkWriteError DETAILS: {bwe.details}", exc_info=True)

                except Exception as e:
                    logger.critical(f"Batch {batch_num}: Critical DB failure: {e}", exc_info=True)
                    continue

        # ------------ SUMMARY ------------
        duration = (datetime.utcnow() - start_time).total_seconds()
        success_count = sum(1 for r in results if r.get('status') == 'created_or_updated')

        logger.info(f"Bulk Create Completed in {duration}s. Success: {success_count}/{total_items}")

        return jsonify({
            "message": "Bulk write completed",
            "count": len(results),
            "success_count": success_count,
            "results": results
        }), 207

    except Exception as e:
        logger.error(f"Global Bulk Write Error: {e}", exc_info=True)
        return jsonify({"error": "Critical server error during bulk operation"}), 500


# def bulk_create_products():
#     start_time = datetime.utcnow()
#     results = []
    
#     try:
#         data = request.get_json()

#         if not isinstance(data, list) or len(data) == 0:
#             logger.warning("Bulk create received empty or invalid list.")
#             return jsonify({"error": "Input must be a non-empty list"}), 400

#         total_items = len(data)
#         logger.info(f"Starting bulk create for {total_items} items. Batch size: {BATCH_SIZE}")

#         # --- PROCESS IN BATCHES ---
#         for i in range(0, total_items, BATCH_SIZE):
#             batch = data[i : i + BATCH_SIZE]
#             batch_num = (i // BATCH_SIZE) + 1
            
#             logger.info(f"Processing Batch {batch_num} (Items {i} to {i + len(batch)})")

#             operations = []
#             batch_validated_docs = [] # Temporary holder for this batch only
            
#             # 1. Validation & Operation Build Phase
#             for item in batch:
#                 try:
#                     validated = product_schema.load(item)

#                     # Ensure product_id & timestamps
#                     if "product_id" not in validated:
#                         validated["product_id"] = get_product_id()
#                         validated["slug"] = slugify(validated["product_name"])

#                     validated["updated_at"] = datetime.utcnow()

#                     if "created_at" not in validated:
#                         validated["created_at"] = datetime.utcnow()

#                     # Build Upsert Operation
#                     operations.append(
#                         UpdateOne(
#                             {
#                                 "brand_id": validated["brand_id"],
#                                 "product_name": {
#                                     "$regex": f"^{validated['product_name']}$",
#                                     "$options": "i"
#                                 }
#                             },
#                             {
#                                 "$set": validated,
#                                 "$setOnInsert": {
#                                     "created_at": validated["created_at"],
#                                     "product_id": validated["product_id"],
#                                 }
#                             },
#                             upsert=True
#                         )
#                     )
#                     batch_validated_docs.append(validated)

#                 except ValidationError as ve:
#                     error_entry = {
#                         "input": item,
#                         "error": ve.messages,
#                         "status": "validation_error"
#                     }
#                     results.append(error_entry)
#                     logger.error(f"Validation failed in batch {batch_num}: {ve.messages}")

#             # 2. Database Write Phase (Only if operations exist)
#             if operations:
#                 try:
#                     # Execute DB write for this batch only
#                     mongo.db.products.bulk_write(operations, ordered=False)
#                     logger.info(f"Batch {batch_num}: Successfully wrote {len(operations)} operations to DB.")
                    
#                 except BulkWriteError as bwe:
#                     # Handle partial failures within the bulk write
#                     logger.error(f"Batch {batch_num}: Bulk write error. {bwe.details['nInserted']} inserted, {bwe.details['nUpserted']} upserted.")
#                     # In a real scenario, you might want to map these errors back to specific items
#                 except Exception as e:
#                     logger.critical(f"Batch {batch_num}: Critical DB failure: {e}", exc_info=True)
#                     # Decide here: 'continue' to next batch, or 'break' to stop everything?
#                     # We will continue to try saving the rest of the data.
#                     continue

#             # 3. Post-Write Processing (Recommender & Result Building)
#             # Optimization: Try to avoid re-fetching from DB if possible. 
#             # If you trust the 'validated' object, use it directly.
#             for doc in batch_validated_docs:
#                 try:
#                     # OPTIMIZATION NOTE: 
#                     # If rec.update_single_product_vector() is slow, this loop will block the API.
#                     # Consider moving this to a Celery/Background task.
                    
#                     # Passing 'doc' directly saves a DB read (N+1 problem). 
#                     # Only fetch from DB if you absolutely need generated fields (like default values set by Mongo).
#                     rec.update_single_product_vector(doc)
                    
#                     results.append({
#                         "status": "created_or_updated",
#                         "product_id": doc.get("product_id"), # Return minimal info to keep response light
#                         "name": doc.get("product_name")
#                     })
#                 except Exception as e:
#                     logger.error(f"Recommender update failed for {doc.get('product_id')}: {e}")
#                     # We still count this as a success for the DB operation
#                     results.append({
#                         "status": "db_saved_recommender_failed", 
#                         "product_id": doc.get("product_id")
#                     })

        # Final Summary
        duration = (datetime.utcnow() - start_time).total_seconds()
        success_count = sum(1 for r in results if r['status'] == 'created_or_updated')
        logger.info(f"Bulk Create Completed. Duration: {duration}s. Success: {success_count}/{total_items}")

        return jsonify({
            "message": "Bulk write completed",
            "count": len(results),
            "success_count": success_count,
            "results": results
        }), 207

    except Exception as e:
        logger.error(f"Global Bulk Write Error: {e}", exc_info=True)
        return jsonify({"error": "Critical server error during bulk operation"}), 500


# 📜 Get all products
def get_all_products():
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 10))
        sort = (request.args.get("sort"))
        skip = (page - 1) * limit

        products = ProductModel.get_all(skip=skip, limit=limit, sort=sort)

        if not products:
            logging.info(f"No products found (page={page}, limit={limit})")
            return jsonify({"total": 0, "products": []}), 200

        logging.info(f"Fetched {len(products)} products (page={page}, limit={limit})")

        simplified_products = product_list_schema.dump(products)
        return jsonify({"total": len(products), "products":simplified_products}), 200

    except Exception as e:
        logging.error(f"Error fetching all products: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch products"}), 500


# 🔍 Get product by ID
def get_product_by_id(product_id):
    try:
        product = ProductModel.get_by_id(product_id)
        if not product:
            logging.warning(f"Product not found (ID: {product_id})")
            return jsonify({"error": "Product not found"}), 404

        logging.info(f"Fetched product successfully (ID: {product_id})")
        return jsonify(product_details_schema.dump(product)), 200

    except Exception as e:
        logging.error(f"Error fetching product by ID ({product_id}): {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch product"}), 500


# ✏️ Update product
def update_product(product_id):
    try:
        data = request.get_json()
        if not data:
            logging.warning(f"No data provided for update (product_id={product_id})")
            return jsonify({"error": "No data provided"}), 400

        validated_data = product_schema.load(data, partial=True)
        validated_data["updated_at"] = datetime.utcnow()
       


        updated = ProductModel.update(product_id, validated_data)
        if updated == 0:
            logging.warning(f"Attempted to update non-existent product (ID: {product_id})")
            return jsonify({"error": "Product not found"}), 404
        updated_prod = ProductModel.get_by_id(product_id=product_id)
        try:
                rec.update_single_product_vector(updated_prod)
        except RuntimeError:
                # Vectorizer not ready (indexing not run yet)
                pass
        logging.info(f"Product updated successfully (ID: {product_id})")
        return jsonify({"message": "Product updated successfully", "product": product_details_schema.dump(updated_prod)}), 200

    except ValidationError as err:
        logging.warning(f"Validation error while updating product {product_id}: {err.messages}")
        return jsonify({"errors": err.messages}), 400
    except Exception as e:
        logging.error(f"Error updating product (ID: {product_id}): {e}", exc_info=True)
        return jsonify({"error": "Failed to update product"}), 500


# ❌ Delete product
def delete_product(product_id):
    try:
        deleted = ProductModel.delete(product_id)
        if deleted == 0:
            logging.warning(f"Attempted to delete non-existent product (ID: {product_id})")
            return jsonify({"error": "Product not found"}), 404

        logging.info(f"Product deleted successfully (ID: {product_id})")
        return jsonify({"message": "Product deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error deleting product (ID: {product_id}): {e}", exc_info=True)
        return jsonify({"error": "Failed to delete product"}), 500


# 🕒 Get recent products
def get_recent_products():
    try:
        limit = int(request.args.get("limit", 5))
        products = ProductModel.get_recent(limit=limit)
        if not products:
            logging.info("No recent products found.")
            return jsonify({"total": 0, "products": []}), 200

        logging.info(f"Fetched {len(products)} recent products (limit={limit})")
        return jsonify({"Total": len(products), "products": product_list_schema.dump(products)}), 200
    except Exception as e:
        logging.error(f"Error fetching recent products: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch recent products"}), 500


# 🔎 Search products
def search_products():
    try:
        # -----------------------------
        # 1️⃣ Parse query parameters safely
        # -----------------------------
        query = (request.args.get("q") or "").strip()
        page = max(int(request.args.get("page", 1)), 1)
        limit = min(max(int(request.args.get("limit", 10)), 1), 50)

        category = request.args.get("category")
        brand_id = request.args.get("brand_id")
        sort = request.args.get("sort", "newest")

        min_price = request.args.get("min_price")
        max_price = request.args.get("max_price")
        in_stock = request.args.get("in_stock")

        if in_stock is not None:
            in_stock = in_stock.lower() == "true"

        # -----------------------------
        # 2️⃣ Build filter query
        # -----------------------------
        filters = {}

        if category:
            filters["category"] = category.capitalize()

        if brand_id:
            filters["brand_id"] = brand_id

        if min_price:
            filters.setdefault("price", {})
            filters["price"]["$gte"] = float(min_price)

        if max_price:
            filters.setdefault("price", {})
            filters["price"]["$lte"] = float(max_price)

        if in_stock:
            filters["stock"] = {"$gt": 0}

        # -----------------------------
        # 3️⃣ Text Search logic
        # -----------------------------
        text_query = {}
        if query:
            text_query = {
                "$or": [
                    {"product_name": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                    {"tags": {"$in": [query]}}
                ]
            }

        # Merge filter + text search
        final_query = {}
        if filters and text_query:
            final_query = {"$and": [filters, text_query]}
        elif filters:
            final_query = filters
        elif text_query:
            final_query = text_query

        # -----------------------------
        # 4️⃣ Sorting options
        # -----------------------------
        if sort == "newest":
            sort_spec = [("created_at", -1)]
        elif sort == "oldest":
            sort_spec = [("created_at", 1)]
        elif sort == "price_asc":
            sort_spec = [("price", 1)]
        elif sort == "price_desc":
            sort_spec = [("price", -1)]
        else:
            sort_spec = [("created_at", -1)]

        # -----------------------------
        # 5️⃣ Query DB with pagination
        # -----------------------------
        skip = (page - 1) * limit
        cursor = mongo.db.products.find(final_query).sort(sort_spec).skip(skip).limit(limit)
        products = list(cursor)

        total = mongo.db.products.count_documents(final_query)
        total_pages = (total + limit - 1) // limit

        # -----------------------------
        # 6️⃣ Convert products → product card format
        # -----------------------------
        product_list = [
            {
                "product_id": p["product_id"],
                "product_slug": p.get("product_slug"),
                "product_name": p.get("product_name"),
                "price": p.get("price"),
                "sale_price": p.get("sale_price"),
                "discount_percentage": p.get("discount_percentage"),
                "thumbnail": p.get("images", [None])[0],
                "stock": p.get("stock", 0),
                "rating": p.get("rating", 0),
                "rating_count": p.get("rating_count", 0),
                "category": p.get("category"),
                "brand_id": p.get("brand_id"),
            }
            for p in products
        ]

        serialized = product_list_schema.dump(product_list)

        # -----------------------------
        # 7️⃣ Final response
        # -----------------------------
        return jsonify({
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "products": serialized
        }), 200

    except Exception as e:
        logging.error(f"Error searching products: {e}", exc_info=True)
        return jsonify({"error": "Failed to search products"}), 500



# 🗂️ Get products by category
def get_products_by_category(category):
    try:
        products = ProductModel.category_products(category)
        if not products:
            logging.info(f"No products found for category '{category}'")
            return jsonify({"total": 0, "products": []}), 200

        logging.info(f"Fetched {len(products)} products for category '{category}'")
        return jsonify(product_schema.dump(products, many=True)), 200
    except Exception as e:
        logging.error(f"Error fetching category products ('{category}'): {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch category products"}), 500


# 🏷️ Get products by brand
def get_products_by_brand(brand_id):
    try:
        products = ProductModel.brand_products(brand_id)
        if not products:
            logging.info(f"No products found for brand '{brand_id}'")
            return jsonify({"total": 0, "products": []}), 200

        logging.info(f"Fetched {len(products)} products for brand '{brand_id}'")
        return jsonify({"total":len(products), "products": product_list_schema.dump(products)}), 200
    except Exception as e:
        logging.error(f"Error fetching brand products (brand_id={brand_id}): {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch brand products"}), 500
