from flask import Blueprint, request, jsonify

from marshmallow import ValidationError
from .controller import create_product,get_all_products,get_product_by_id,update_product,delete_product, get_recent_products,search_products,get_products_by_category,get_products_by_brand

products_bp = Blueprint("products", __name__)



# ✅ 1. Create new product
@products_bp.route("/new", methods=["POST"])
def add_product():
    return create_product()


# ✅ 2. Get all products (with filters & pagination)
@products_bp.route("", methods=["GET"])
def get_products():
    return get_all_products()


# ✅ 3. Get product by ID
@products_bp.route("/<product_id>", methods=["GET"])
def get_product(product_id):
    return get_product_by_id(product_id)


# ✅ 4. Update product
@products_bp.route("/<product_id>", methods=["PUT", "PATCH"])
def update_details_of_product(product_id):
    return update_product(product_id)

# ✅ 5. Delete product
@products_bp.route("/<product_id>", methods=["DELETE"])
def delete(product_id):
    return delete_product(product_id)


# ✅ 6. Get products by brand
@products_bp.route("/brand/<brand_id>", methods=["GET"])
def brand_products(brand_id):
    return get_products_by_brand(brand_id)



# ✅ 7. Get products by category
@products_bp.route("/category/<category>", methods=["GET"])
def product_by_category(category):
    return get_products_by_category(category)



# ✅ 8. Search products (keyword, filters, pagination, sort)
@products_bp.route("/search", methods=["GET"])
def search():
    return search_products()


# ✅ 9. Get recent products
@products_bp.route("/recent", methods=["GET"])
def get_recent():
    return get_recent_products()

