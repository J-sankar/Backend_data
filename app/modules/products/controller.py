import logging
from flask import request, jsonify
from marshmallow import ValidationError
from datetime import datetime
from .schema import ProductSchema
from .model import ProductModel

product_schema = ProductSchema()


# ➕ Create new product
def create_product():
    try:
        data = request.get_json()
        if not data:
            logging.warning("Create Product: No input data received.")
            return jsonify({"error": "No details entered"}), 400

        validated_data = product_schema.load(data)
        product = ProductModel.create(validated_data)

        logging.info(f"Product created successfully: {product.get('product_name')} (ID: {product.get('product_id')})")
        return jsonify({
            "message": "Product created successfully",
            "product": product_schema.dump(product)
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
        sort = request.args.get("sort")
        skip = (page - 1) * limit

        products = ProductModel.get_all(skip=skip, limit=limit, sort=sort)

        if not products:
            logging.info(f"No products found (page={page}, limit={limit})")
            return jsonify({"total": 0, "products": []}), 200

        logging.info(f"Fetched {len(products)} products (page={page}, limit={limit})")

        simplified_products = [
            {
                "product_id": p["product_id"],
                "product_name": p["product_name"],
                "product_image": p.get("images", [None])[0],
                "stock": p.get("stock", 0)
            }
            for p in products
        ]
        return jsonify(simplified_products), 200

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
        return jsonify(product_schema.dump(product)), 200

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
        return jsonify(product_schema.dump(products, many=True)), 200
    except Exception as e:
        logging.error(f"Error fetching recent products: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch recent products"}), 500


# 🔎 Search products
def search_products():
    try:
        query = request.args.get("q", "").strip()
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 10))
        sort = request.args.get("sort", "newest")
        category = request.args.get("category")
        brand_id = request.args.get("brand_id")
        min_price = request.args.get("min_price")
        max_price = request.args.get("max_price")
        in_stock = request.args.get("in_stock")

        in_stock = in_stock.lower() == "true" if in_stock else None

        data = ProductModel.search(
            query=query,
            page=page,
            limit=limit,
            sort=sort,
            category=category,
            brand_id=brand_id,
            min_price=min_price,
            max_price=max_price,
            in_stock=in_stock
        )

        logging.info(f"Search query executed (q='{query}', total={data['total']})")
        return jsonify({
            "total": data["total"],
            "page": data["page"],
            "limit": data["limit"],
            "total_pages": data["total_pages"],
            "products": product_schema.dump(data["products"], many=True)
        }), 200

    except Exception as e:
        logging.error(f"Error searching products (q='{request.args.get('q', '')}'): {e}", exc_info=True)
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
        return jsonify(product_schema.dump(products, many=True)), 200
    except Exception as e:
        logging.error(f"Error fetching brand products (brand_id={brand_id}): {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch brand products"}), 500
