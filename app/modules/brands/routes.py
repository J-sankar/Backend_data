from flask import Blueprint
from .controller import add_brand, get_brands,get_brand_by_id,update_brand

brands_bp = Blueprint("brands_bp", __name__)

from flask import Blueprint

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

@brands_bp.route("/<id>/update", methods=["POST"])
def update_details(id):
    return update_brand(id)
