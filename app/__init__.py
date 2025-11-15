import logging
from flask import Flask, jsonify
from .extensions import mongo, cors
from dotenv import load_dotenv
from .modules.brands.routes import brands_bp
from .modules.products.routes import products_bp

def create_app(config_name="development"):
    
    load_dotenv()
    from .config import config_by_name

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])
    
    logging.basicConfig(
        level=logging.INFO,  # or DEBUG for more detail
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler("app.log"),   # logs to file
            logging.StreamHandler()           # prints to console
        ]
    )
    try:
        cors.init_app(app)
        mongo.init_app(app)
        logging.info("Db intialised")
        
    except Exception as e:
        logging.error("Connection Failed: %s",e)

    app.register_blueprint(brands_bp, url_prefix="/api/brands")
    app.register_blueprint(products_bp, url_prefix="/api/products")
    

    @app.route("/")
    def home():
        return {"message": "Flask is running successfully"}
    
     # --- Health Check Route ---
    @app.route("/health")
    def health():
        try:
            mongo.cx.server_info()  # Test connection only here
            return jsonify({"db_status": "connected"}), 200
        except Exception as e:
            logging.error("❌ Database connection failed during health check: %s", e)
            return jsonify({"db_status": "failed", "error": str(e)}), 500
    
    return app