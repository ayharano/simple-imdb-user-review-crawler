"""
Provide a dataclass to store a IMDb user review and
a crawler to retrieve all the available public reviews for a title.
"""
from ._imdb_user_review_crawler import (
    IMDbUserReview,
    crawl_imdb_user_reviews_by_title_id,
)

__version__ = "0.1.0"
