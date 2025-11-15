import os

class BaseConfig:
    MONGO_URI = os.getenv("MONGO_URI")
    CORS_HEADERS = "Content-Type"

class DevelopmentConfig(BaseConfig):
    DEBUG = True

class ProductionConfig(BaseConfig):
    DEBUG = False

config_by_name = {
    "development": DevelopmentConfig,
    "production" : ProductionConfig
}