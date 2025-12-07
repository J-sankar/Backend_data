import numpy as np
import logging

logger = logging.getLogger(__name__)

def normalize_scores(score_dict: dict) -> dict:
    if not score_dict:
        logger.info("normalize_scores: empty score_dict, returning {}")
        return {}

    values = np.array(list(score_dict.values()), dtype=float)
    min_v = values.min()
    max_v = values.max()

    logger.info(
        f"Normalizing {len(score_dict)} scores -> min={min_v:.4f}, max={max_v:.4f}"
    )

    denom = (max_v - min_v) + 1e-9

    normalized = {pid: (score - min_v) / denom for pid, score in score_dict.items()}
    return normalized


def build_hybrid_output(similar_products, brand_products, category_products):
    logger.info(
        f"Hybrid Aggregation Started | similar={len(similar_products)}, "
        f"brand={len(brand_products)}, category={len(category_products)}"
    )

    # Extract raw scores
    sim_scores = {p["product_id"]: p.get("similarity_score", 0.0) for p in similar_products}
    brand_scores = {p["product_id"]: p.get("brand_score", 0.0) for p in brand_products}
    category_scores = {p["product_id"]: p.get("category_score", 0.0) for p in category_products}

    logger.info(
        f"Raw Score Sizes | similarity={len(sim_scores)}, "
        f"brand={len(brand_scores)}, category={len(category_scores)}"
    )

    # Normalize score groups
    sim_norm = normalize_scores(sim_scores)
    brand_norm = normalize_scores(brand_scores)
    category_norm = normalize_scores(category_scores)

    # Weights
    SIM_W = 0.5
    BRAND_W = 0.2
    CAT_W = 0.3

    logger.info(
        f"Hybrid Weights | similarity={SIM_W}, brand={BRAND_W}, category={CAT_W}"
    )

    weighted_final = {}

    # Add similarity scores
    for pid, score in sim_norm.items():
        weighted_final[pid] = weighted_final.get(pid, 0.0) + score * SIM_W

    # Add brand scores
    for pid, score in brand_norm.items():
        weighted_final[pid] = weighted_final.get(pid, 0.0) + score * BRAND_W

    # Add category scores
    for pid, score in category_norm.items():
        weighted_final[pid] = weighted_final.get(pid, 0.0) + score * CAT_W

    logger.info(f"Weighted score count: {len(weighted_final)}")

    # Sort by weighted score descending
    sorted_ids = sorted(weighted_final, key=lambda pid: weighted_final[pid], reverse=True)

    logger.info(
        f"Top weighted scores (first 5): "
        f"{[(pid, round(weighted_final[pid],4)) for pid in sorted_ids[:5]]}"
    )

    # Merge product dictionaries
    product_map = {}

    for p in similar_products:
        product_map[p["product_id"]] = p
    for p in brand_products:
        product_map[p["product_id"]] = p
    for p in category_products:
        product_map[p["product_id"]] = p

    logger.info(f"Merged product map size: {len(product_map)}")

    final_list = [product_map[pid] for pid in sorted_ids if pid in product_map]

    logger.info(f"Hybrid final list size: {len(final_list)}")

    return final_list
