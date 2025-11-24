from flask import Blueprint
from .controller import (
    add_brand,
    get_brands,
    get_brand_by_id,
    update_brand,
    delete_brand,
)
from ..products.controller import get_products_by_brand

brands_bp = Blueprint("brands_bp", __name__)


# POST: Add new brand
@brands_bp.route("/", methods=["POST"])
def new_brand():
    return add_brand()


# GET: List all brands
@brands_bp.route("/", methods=["GET"])
def list_brands():
    return get_brands()


# GET: Details of a brand by id
@brands_bp.route("/<id>", methods=["GET"])
def get_by_id(id):
    return get_brand_by_id(id)


# UPDATE: Update brand by id (PUT/PATCH)
@brands_bp.route("/<id>", methods=["PUT", "PATCH"])
def update_details(id):
    return update_brand(id)


# DELETE: Delete a brand by id
@brands_bp.route("/<id>", methods=["DELETE"])
def delete_details(id):
    return delete_brand(id)


@brands_bp.route("/<brand_id>/products", methods=["GET"])
def brand_products(brand_id):
    return get_products_by_brand(brand_id)