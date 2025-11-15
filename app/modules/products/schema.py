from marshmallow import Schema, fields, validate, pre_load
from uuid import uuid4
from datetime import datetime


class ProductSchema(Schema):
    _id = fields.Str(dump_only=True)

    # ✅ Use `dump_default` (not default)
    product_id = fields.Str(dump_only=True)
    brand_id = fields.Str(required=True)

    product_name = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=100)
    )

    description = fields.Str(required=True)
    price = fields.Float(required=True)

    category = fields.Str(
        required=True,
        validate=validate.OneOf([
            "Fashion",
            "Electronics",
            "Grocery",
            "Beauty",
            "Sports",
            "Other"
        ])
    )

    images = fields.List(
        fields.Url(),
        required=True,
        validate=validate.Length(min=1)
    )

    stock = fields.Int(required=True)

    # Optional extras — use `load_default` for missing input
    featured = fields.Bool(load_default=False)
    rating = fields.Float(load_default=0.0)
    tags = fields.List(fields.Str(), load_default=[])

    # ✅ Use `dump_default` for generated timestamps
    created_at = fields.DateTime(dump_only=True, dump_default=lambda: datetime.utcnow())
    updated_at = fields.DateTime(dump_only=True, dump_default=lambda: datetime.utcnow())

    @pre_load
    def normalize_category(self, data, **kwargs):
        """Normalize category capitalization"""
        if "category" in data and isinstance(data["category"], str):
            data["category"] = data["category"].capitalize()
        return data
