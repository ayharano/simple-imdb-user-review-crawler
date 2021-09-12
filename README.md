# simple-imdb-user-review-crawler

> **simple-imdb-user-review-crawler** - a simple IMDb User Review Crawler

---

![License: MIT](https://img.shields.io/badge/license-MIT-purple)
![Python Versions: 3.7 | 3.8 | 3.9](https://img.shields.io/badge/python-3.7%20%7C%203.8%20%7C%203.9-blue)
![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)

---

## Features

_simple-imdb-user-review-crawler_ provides a simple IMDb user review crawler
by providing the following `dataclass`:

```python
@dataclass(frozen=True)
class IMDbUserReview:
    review_id: str
    review_date: str
    review_title: str
    title_id: str
    title_name: str
    title_relative_url: str
    total_feedback: int
    helpful_feedback: int
    maximum_rating: Optional[int]
    user_rating: Optional[int]
    has_spoilers: bool
    user_name: str
    user_relative_url: str
    content: str
```

## Installation and usage

### Installation

_simple-imdb-user-review-crawler_ can be installed by
running:

```shell
$ python -m pip install 'git+https://github.com/ayharano/simple-imdb-user-review-crawler'
```

It requires Python 3.7+ to run.

### Usage

After installation, you may use it in your Python code by doing

```python
from simple_imdb_user_review_crawler import crawl_imdb_user_reviews_by_title_id
```

## Example

If this repository has been cloned, the following example can be run:

- `example_save_title_user_reviews_as_csv.py`

A CLI script to save the data of user reviews from one or more titles in IMDb
and store them into a single csv file.

Usage example:

```shell
$ python example_save_title_user_reviews_as_csv.py tampopo.csv tt0092048
```
