from marshmallow import Schema, fields

class ProductDetailResponseSchema(Schema):
    product_id = fields.Str()
    product_slug = fields.Str()

    product_name = fields.Str()
    description = fields.Str()

    price = fields.Float()
    sale_price = fields.Float(allow_none=True)
    discount_percentage = fields.Float()

    images = fields.List(fields.Str())
    stock = fields.Int()

    category = fields.Str()
    tags = fields.List(fields.Str())

    brand_id = fields.Str()
    brand_name = fields.Str()

    rating = fields.Float()
    rating_count = fields.Int()

    created_at = fields.DateTime()
    updated_at = fields.DateTime()
