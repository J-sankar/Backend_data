import random
import logging
import sys
import os
from datetime import datetime
from faker import Faker
from pymongo import MongoClient


# --- PATH SETUP (CRITICAL) ---
# Add the project root (BACKEND) to Python path so we can see 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# -----------------------------

# FIX: Use Absolute Import (Requires the path setup above)
try:
    from app.modules.utils.identifiers import slugify, get_brand_id, get_product_id
    from app import create_app
    app = create_app()
except ImportError as e:
    print("Error importing utils. Make sure you run this from the project root or check the path.")
    print(f"Details: {e}")
    sys.exit(1)

# --- CONFIGURATION ---
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "TruBharat"
NUM_BRANDS = 50
NUM_PRODUCTS = 2000
# ---------------------

fake = Faker()
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# VOCABULARY FOR SEARCHABLE DESCRIPTIONS
TAG_POOLS = {
    "Electronics": ["wireless", "bluetooth", "battery", "smart", "digital", "screen", "charging", "usb", "wifi", "4k"],
    "Fashion": ["cotton", "comfortable", "summer", "winter", "casual", "denim", "leather", "fit", "style", "wear"],
    "Grocery": ["organic", "fresh", "tasty", "snack", "healthy", "vegan", "gluten-free", "natural", "sweet", "spicy"],
    "Beauty": ["skin", "care", "smooth", "glow", "scent", "fragrance", "natural", "face", "body", "serum"],
    "Sports": ["fitness", "gym", "outdoor", "training", "gear", "muscle", "run", "sport", "active", "durable"]
}

def generate_data():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    # --- SAFETY CLEAR (Recommended) ---
    # Uncomment these to prevent ID collisions with old data
    logging.info("Clearing existing data...")
    db.brands.delete_many({})
    db.products.delete_many({})
    # ----------------------------------

    # ==========================================
    # 1. GENERATE BRANDS
    # ==========================================
    logging.info(f"Generating {NUM_BRANDS} Brands...")
    
    brand_cache = [] 
    new_brands = []

    for i in range(NUM_BRANDS):
        b_id = get_brand_id() 
        b_name = fake.company()
        
        brand = {
            "brand_id": b_id,
            "brand_name": b_name,
            "slug": slugify(b_name), # Using your custom slugify
            "email": fake.company_email(),
            "phone_number": str(fake.random_number(digits=10, fix_len=True)),
            "brand_logo": fake.image_url(width=100, height=100),
            "verification_status": "Verified",
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        new_brands.append(brand)
        brand_cache.append({"id": b_id, "name": b_name})

    if new_brands:
        db.brands.insert_many(new_brands)
        logging.info("Brands inserted successfully.")

    # ==========================================
    # 2. GENERATE PRODUCTS
    # ==========================================
    logging.info(f"Generating {NUM_PRODUCTS} Products...")
    
    new_products = []
    
    for i in range(NUM_PRODUCTS):
        category = random.choice(list(TAG_POOLS.keys()))
        tags = random.sample(TAG_POOLS[category], k=random.randint(3, 5))
        chosen_brand = random.choice(brand_cache)

        keywords_str = ", ".join(tags)
        description = f"A premium {category} product from {chosen_brand['name']}. Features include {keywords_str}. {fake.sentence()}"

        p_id = get_product_id()
        p_name = f"{fake.color_name().title()} {fake.word().title()} {category}"
        
        product = {
            "product_id": p_id,
            "product_slug": slugify(p_name),
            
            "brand_id": chosen_brand["id"],
            "brand_name": chosen_brand["name"],
            
            "product_name": p_name,
            "category": category,
            "description": description,
            "tags": tags,
            
            "price": round(random.uniform(10, 500), 2),
            "stock": random.randint(0, 100),
            "rating": round(random.uniform(3.0, 5.0), 1),
            "status": "Active",
            "images": [fake.image_url()],
            "created_at": datetime.now()
        }
        new_products.append(product)

        if len(new_products) >= 1000:
            db.products.insert_many(new_products)
            new_products = []
            logging.info(f"Inserted batch... Last ID: {p_id}")

    if new_products:
        db.products.insert_many(new_products)
    
    logging.info("Data Generation Complete.")
    logging.info("NEXT STEP: Run your TF-IDF indexer to make these recommendable!")

if __name__ == "__main__":
    generate_data()