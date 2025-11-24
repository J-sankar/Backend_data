from marshmallow import Schema, fields

class ProductListResponseSchema(Schema):
    product_id = fields.Str()
    product_slug = fields.Str()
    product_name = fields.Str()
    price = fields.Float()
    sale_price = fields.Float(allow_none=True)
    discount_percentage = fields.Float()
    images = fields.List(fields.Str())
    stock = fields.Int()
    rating = fields.Float()
    rating_count = fields.Int()
    category = fields.Str()
    brand_id = fields.Str()
