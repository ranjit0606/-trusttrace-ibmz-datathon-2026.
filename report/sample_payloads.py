"""
sample_payloads.py - made-up test data for the report generator.
Shape follows the team contract:
  risk     = Member 3's scorer output
  evidence = Member 2's build_evidence() output
All links use example.com. Missing data is None (never 0).
"""

FULL = {
    "risk": {
        "score": 8,
        "risk_level": "High",
        "confidence": "High",
        "top_reasons": [
            {"signal": "price", "points": 3, "text": "Listed price is below 40% of the market median"},
            {"signal": "image_match", "points": 3, "text": "Product photo found on 14 other listings"},
            {"signal": "account_age", "points": 2, "text": "Account is younger than 30 days"},
        ],
    },
    "evidence": {
        "seller_id": "glow_bazaar",
        "listing_url": "https://example.com/listing/glow-bazaar-1",
        "profile": {
            "account_age_days": 12, "followers": 3400, "following": 40, "posts": 18,
            "engagement_ratio": 0.004, "has_contact_info": False,
        },
        "image_match": {
            "match_count": 14, "unique_domains": 6,
            "sources": ["https://example.com/image-match/abc123"],
        },
        "price": {
            "listed_price": 499.0, "market_median": 1800.0, "comparable_count": 7,
            "sources": ["https://example.com/price-compare/xyz789"],
        },
    },
}

# Some data could not be collected -> None
WITH_NULLS = {
    "risk": {
        "score": 4,
        "risk_level": "Medium",
        "confidence": "Low",
        "top_reasons": [
            {"signal": "image_match", "points": 3, "text": "Product photo found on 11 other listings"},
            {"signal": "contact", "points": 1, "text": "No contact information found"},
        ],
    },
    "evidence": {
        "seller_id": "daily_deals",
        "listing_url": "https://example.com/listing/daily-deals-9",
        "profile": {
            "account_age_days": None, "followers": 150, "following": None, "posts": 25,
            "engagement_ratio": None, "has_contact_info": False,
        },
        "image_match": {
            "match_count": 11, "unique_domains": 5,
            "sources": ["https://example.com/image-match/def456"],
        },
        "price": {
            "listed_price": 999.0, "market_median": None, "comparable_count": 0, "sources": [],
        },
    },
}

LOW_RISK = {
    "risk": {
        "score": 1,
        "risk_level": "Low",
        "confidence": "High",
        "top_reasons": [
            {"signal": "contact", "points": 1, "text": "No contact information found"},
        ],
    },
    "evidence": {
        "seller_id": "old_trusted_shop",
        "listing_url": "https://example.com/listing/old-shop-3",
        "profile": {
            "account_age_days": 900, "followers": 12000, "following": 300, "posts": 640,
            "engagement_ratio": 0.05, "has_contact_info": True,
        },
        "image_match": {"match_count": None, "unique_domains": None, "sources": []},
        "price": {
            "listed_price": 1650.0, "market_median": 1800.0, "comparable_count": 9,
            "sources": ["https://example.com/price-compare/lmn321"],
        },
    },
}

ALL_SAMPLES = [FULL, WITH_NULLS, LOW_RISK]
