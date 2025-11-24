import logging
from flask import request, jsonify
from marshmallow import ValidationError
from ...extensions import mongo
from datetime import datetime
from .schema import ProductSchema
from .model import ProductModel
from .responses.productListResponse import ProductListResponseSchema
from .responses.productDetailsResponse import ProductDetailResponseSchema

product_schema = ProductSchema()
product_list_schema = ProductListResponseSchema(many=True)
product_details_schema = ProductDetailResponseSchema()



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

            set_payload["updated_at"] = datetime.utcnow()

            mongo.db.products.update_one(
                {"_id": existing["_id"]},
                {"$set": set_payload}
            )

            updated_product = mongo.db.products.find_one({"_id": existing["_id"]})
            logging.info(f"Product updated: {product_name} (Brand: {brand_id})")

            return jsonify({
                "message": "Product already existed → updated successfully",
                "product": product_details_schema.dump(updated_product)
            }), 200

        product = ProductModel.create(validated_data)
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

        logging.info(f"Product updated successfully (ID: {product_id})")
        return jsonify({"message": "Product updated successfully"}), 200

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
