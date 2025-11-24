from marshmallow import Schema, fields, validate, pre_load
from uuid import uuid4
from datetime import datetime


class ProductSchema(Schema):
    _id = fields.Str(dump_only=True)
    product_id = fields.Str(dump_only=True)
    product_slug = fields.Str(dump_only=True)

    brand_id = fields.Str(required=True)
    brand_name = fields.Str(dump_only=True)

    product_name = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    description = fields.Str(required=True)

    price = fields.Float(required=True)
    sale_price = fields.Float(load_default=None)
    discount_percentage = fields.Float(load_default=0.0)

    category = fields.Str(required=True, validate=validate.OneOf(
        ["Fashion", "Electronics", "Grocery", "Beauty", "Sports", "Other"]
    ))

    images = fields.List(fields.Url(), required=True, validate=validate.Length(min=1))

    stock = fields.Int(required=True)
    availability = fields.Str(
        load_default="In Stock",
        validate=validate.OneOf(["In Stock", "Out of Stock", "Limited Stock"])
    )

    sku = fields.Str(load_default=None)
    tags = fields.List(fields.Str(), load_default=[])

    variants = fields.List(fields.Dict(), load_default=[])

    weight = fields.Float(load_default=None)
    dimensions = fields.Dict(load_default=None)

    status = fields.Str(load_default="Active", validate=validate.OneOf(["Active", "Inactive"]))
    product_type = fields.Str(load_default="simple", validate=validate.OneOf(["simple", "variant"]))

    rating = fields.Float(load_default=0.0)
    rating_count = fields.Int(load_default=0)

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @pre_load
    def normalize_category(self, data, **kwargs):
        if "category" in data and isinstance(data["category"], str):
            data["category"] = data["category"].capitalize()
        return data
