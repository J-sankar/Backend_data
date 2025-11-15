from marshmallow import Schema, fields, validate

class BrandSchema(Schema):
    _id = fields.Str(dump_only=True)
    brand_id = fields.Str(dump_only=True)  # auto-generated in model

    brand_name = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    email = fields.Email(required=True)
    phone_number = fields.Str(required=True, validate=validate.Length(min=10, max=15))

    brand_logo = fields.URL(required=False)
    brand_description = fields.Str(required=False, validate=validate.Length(max=2000))

    documents = fields.List(fields.URL(), required=False)
    verification_status = fields.Str(
        validate=validate.OneOf(["Pending", "Verified", "Rejected"]),
        dump_default="Pending"
    )

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
