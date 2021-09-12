"""
Provide the implementation of a crawler that retrieves
all the available public reviews for a title in IMDb.
"""

import json
import locale
import re
from dataclasses import dataclass, asdict, astuple, fields
from datetime import date, datetime
from os import PathLike
from pathlib import Path
from time import sleep
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
import yarl
from lxml import html


WAIT_TIME_IN_SECONDS = 0.5
BASE_IMDB_URL = yarl.URL("https://www.imdb.com")
RELATIVE_IMDB_USER_REVIEWS_URL = "/title/{title_id}/reviews"
FOUND_HELPFUL_REGEX = re.compile(
    r"\D*(?P<helpful>\d{1,3}(,\d{3})*)"
    r"\s+out\s+of\s+"
    r"(?P<total>\d{1,3}(,\d{3})*)"
    r"\s+found\s+this\s+helpful.*",
    flags=re.IGNORECASE,
)
MAXIMUM_RATING_REGEX = re.compile(r"\D*/(?P<maximum_rating>\d+)\D*")
BROKEN_UNICODE_REGEX = re.compile(r"\\x")


@dataclass(frozen=True)
class IMDbUserReview:
    """IMDb user review for a title data representation."""

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

    def fields(self) -> List[str]:
        return [field.name for field in fields(self)]

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def as_tuple(self) -> Tuple[Any, ...]:
        return astuple(self)

    def as_json_str(self) -> str:
        return json.dumps(asdict(self))


def xpath_descendant_contains_target_attribute_builder(
    node_type: str,
    attribute: str,
    target: str,
    is_relative: bool = True,
    retrieve_texts: bool = False,
) -> str:
    return (
        "{relative}"
        "//descendant::{node_type}["
        "    contains("
        "        concat("
        '            " ",'
        "            normalize-space(@{attribute}),"
        '            " "'
        "        ),"
        '        " {target} "'
        "    )"
        "]{texts}"
    ).format(
        relative="." if is_relative else "",
        node_type=node_type,
        attribute=attribute,
        target=target,
        texts="//text()" if retrieve_texts else "",
    )


def normalize_text(raw_str_list: List[str]) -> str:
    clean_lines = [
        clean_line
        for raw_line in raw_str_list
        for clean_line in (raw_line.strip(),)
        if clean_line
    ]
    clean_text = "\n".join(clean_lines)
    return clean_text


def build_queryless_url_str_from_str(input_str: str) -> str:
    as_url = yarl.URL(input_str).with_query(None)
    return str(as_url)


def valid_value_from_dict(
    target_dict: Dict[Any, Any],
    key: Any,
) -> Optional[Any]:
    value = key in target_dict and target_dict[key]
    return value if value else None


def parse_raw_item_to_imdb_user_review(
    title_id: str,
    title_name: str,
    title_relative_url: str,
    review_content_as_single_line: bool,
    raw_item_data: html.HtmlElement,
) -> IMDbUserReview:
    review_id = None
    review_date = None
    review_title = None
    total_feedback = None
    helpful_feedback = None
    maximum_rating = None
    user_rating = None
    has_spoilers = None
    user_name = None
    user_relative_url = None
    content = None

    review_id_data = valid_value_from_dict(
        raw_item_data.attrib,
        "data-review-id",
    )
    if review_id_data:
        review_id = review_id_data.strip()

    review_date_results = raw_item_data.xpath(
        xpath_descendant_contains_target_attribute_builder(
            node_type="span",
            attribute="class",
            target="review-date",
            retrieve_texts=True,
        )
    )
    if review_date_results:
        locale.setlocale(locale.LC_TIME, "C")
        as_datetime = datetime.strptime(
            review_date_results[0].strip(), "%d %B %Y"
        )
        review_date = date(
            year=as_datetime.year,
            month=as_datetime.month,
            day=as_datetime.day,
        ).isoformat()

    review_title_text_results = raw_item_data.xpath(
        xpath_descendant_contains_target_attribute_builder(
            node_type="a",
            attribute="class",
            target="title",
            retrieve_texts=True,
        )
    )
    if review_title_text_results:
        review_title = normalize_text(review_title_text_results)

    found_helpful_results = raw_item_data.xpath(
        xpath_descendant_contains_target_attribute_builder(
            node_type="div",
            attribute="class",
            target="actions",
            retrieve_texts=True,
        )
    )
    if found_helpful_results:
        joined_text = "".join(found_helpful_results)
        helpful_match_result = FOUND_HELPFUL_REGEX.match(joined_text)
        if helpful_match_result:
            helpful_variable_dict = helpful_match_result.groupdict()
            total_feedback = int(
                valid_value_from_dict(helpful_variable_dict, "total").replace(
                    ",",
                    "",
                )
            )
            helpful_feedback = int(
                valid_value_from_dict(
                    helpful_variable_dict, "helpful"
                ).replace(",", "")
            )

    spoiler_results = raw_item_data.xpath(
        xpath_descendant_contains_target_attribute_builder(
            node_type="span",
            attribute="class",
            target="spoiler-warning",
        )
    )
    has_spoilers = bool(spoiler_results)

    rating_results = raw_item_data.xpath(
        xpath_descendant_contains_target_attribute_builder(
            node_type="span",
            attribute="class",
            target="point-scale",
        )
    )
    if rating_results:
        maximum_rating_node = rating_results[0]
        user_rating_node = maximum_rating_node.getprevious()

        user_rating = int(user_rating_node.text.strip())

        maximum_rating_match_result = MAXIMUM_RATING_REGEX.match(
            maximum_rating_node.text
        )
        if maximum_rating_match_result:
            rating_variable_dict = maximum_rating_match_result.groupdict()
            maximum_rating = int(
                valid_value_from_dict(rating_variable_dict, "maximum_rating")
            )

        # if one of the values is missing, we will clear both
        if not all([user_rating, maximum_rating]):
            user_rating = None
            maximum_rating = None

    user_data_results = raw_item_data.xpath(
        "/".join(
            [
                xpath_descendant_contains_target_attribute_builder(
                    node_type="div",
                    attribute="class",
                    target="display-name-date",
                ),
                ".//a[string(@href)]",
            ]
        )
    )
    if user_data_results:
        user_data_node = user_data_results[0]
        user_name = normalize_text([user_data_node.text])
        raw_user_relative_url = valid_value_from_dict(
            user_data_node.attrib,
            "href",
        ).strip()
        user_relative_url = build_queryless_url_str_from_str(
            raw_user_relative_url
        )

    content_text_results = raw_item_data.xpath(
        xpath_descendant_contains_target_attribute_builder(
            node_type="div",
            attribute="class",
            target="text",
            retrieve_texts=True,
        )
    )
    if content_text_results:
        content = normalize_text(content_text_results)
        if review_content_as_single_line:
            content = " ".join(content.split("\n"))

    return IMDbUserReview(
        review_id=review_id,
        review_date=review_date,
        review_title=review_title,
        title_id=title_id,
        title_name=title_name,
        title_relative_url=title_relative_url,
        total_feedback=total_feedback,
        helpful_feedback=helpful_feedback,
        maximum_rating=maximum_rating,
        user_rating=user_rating,
        has_spoilers=has_spoilers,
        user_name=user_name,
        user_relative_url=user_relative_url,
        content=content,
    )


def parse_raw_html_to_imdb_user_review_set_and_more_data(
    title_id: str,
    title_name: Optional[str],
    title_relative_url: Optional[str],
    review_content_as_single_line: bool,
    raw_html: bytes,
    original_encoding: str,
) -> Tuple[Set[IMDbUserReview], Dict[str, str], Dict[str, str]]:
    valid_user_review_set = set()
    title_data = {}
    more_data = {}

    html_parser = html.HTMLParser(encoding=original_encoding)
    root = html.fromstring(raw_html, parser=html_parser)

    if not title_name and not title_relative_url:
        title_results = root.xpath(
            xpath_descendant_contains_target_attribute_builder(
                node_type="a",
                attribute="itemprop",
                target="url",
                is_relative=False,
            )
        )
        if title_results:
            title_node = title_results[0]
            title_name = normalize_text([title_node.text])
            raw_title_relative_url = valid_value_from_dict(
                title_node.attrib,
                "href",
            ).strip()
            title_relative_url = build_queryless_url_str_from_str(
                raw_title_relative_url,
            )
            title_data["title_name"] = title_name
            title_data["title_relative_url"] = title_relative_url

    review_results = root.xpath(
        xpath_descendant_contains_target_attribute_builder(
            node_type="div",
            attribute="class",
            target="imdb-user-review",
            is_relative=False,
        )
    )
    for raw_review in review_results:
        item = parse_raw_item_to_imdb_user_review(
            title_id=title_id,
            title_name=title_name,
            title_relative_url=title_relative_url,
            review_content_as_single_line=review_content_as_single_line,
            raw_item_data=raw_review,
        )
        if item:
            valid_user_review_set.add(item)

    load_more_data_results = root.xpath(
        xpath_descendant_contains_target_attribute_builder(
            node_type="div",
            attribute="class",
            target="load-more-data",
        )
    )
    if load_more_data_results:
        load_more_data_node = load_more_data_results[0]
        for key in ("data-key", "data-ajaxurl"):
            retrieved_value = valid_value_from_dict(
                load_more_data_node.attrib,
                key,
            )
            if retrieved_value:
                more_data[key] = retrieved_value

    return valid_user_review_set, title_data, more_data


def crawl_imdb_user_reviews_by_title_id(
    title_id: str,
    review_content_as_single_line: bool = False,
    save_path: Optional["PathLike[Any]"] = None,
) -> Set[IMDbUserReview]:
    """

    :param title_id: IMDb title id such as 'tt9876543'
    :param review_content_as_single_line: Optional boolean to handle
        user review content as a single line. Useful for handling csv.
        False by default.
    :param save_path: Optional path to save retrieved HTML pages.
        It will create a directory structure as
        <save_path> / <title_id> / <YYYYMMDD_HHMMSS> and
        store pages as 0000000.html,  0000001.html, etc
    :return: set of IMDbUserReview instances
    """
    user_review_set = set()
    current_save_dir_path = None
    if save_path:
        current_save_dir_path = (
            Path(save_path)
            / title_id
            / datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        )
        current_save_dir_path.mkdir(mode=0o755, parents=True, exist_ok=True)

    title_name = None
    title_relative_url = None

    initial_url = BASE_IMDB_URL.with_path(
        RELATIVE_IMDB_USER_REVIEWS_URL.format(title_id=title_id)
    )
    load_more_data_base_url = None

    current_url = initial_url
    load_more_data = True
    page_count = 0
    last_get = None

    with httpx.Client() as client:
        while load_more_data:
            while (
                last_get
                and (datetime.utcnow() - last_get).total_seconds()
                < WAIT_TIME_IN_SECONDS
            ):
                sleep(WAIT_TIME_IN_SECONDS)

            response = client.get(url=str(current_url), timeout=2.0)
            last_get = datetime.utcnow()

            raw_html = response.content
            original_encoding = response.encoding

            if 400 <= response.status_code < 600:
                load_more_data = False
                continue

            if current_save_dir_path:
                current_page_name = f"{page_count:07d}.html"
                page_path = current_save_dir_path / current_page_name
                with open(page_path, "wb") as page_file:
                    page_file.write(raw_html)
                    page_file.flush()
                page_count += 1

            (
                current_user_review_set,
                new_title_data,
                more_data,
            ) = parse_raw_html_to_imdb_user_review_set_and_more_data(
                title_id=title_id,
                title_name=title_name,
                title_relative_url=title_relative_url,
                review_content_as_single_line=review_content_as_single_line,
                raw_html=raw_html,
                original_encoding=original_encoding,
            )

            if current_user_review_set:
                user_review_set.update(current_user_review_set)

            new_title_name = valid_value_from_dict(
                new_title_data, "title_name"
            )
            if not title_name and new_title_name:
                title_name = new_title_name

            new_title_relative_url = valid_value_from_dict(
                new_title_data, "title_relative_url"
            )
            if not title_relative_url and new_title_relative_url:
                title_relative_url = new_title_relative_url

            if not more_data:
                load_more_data = False
                continue

            data_key = valid_value_from_dict(more_data, "data-key")
            if not data_key:
                load_more_data = False
                continue

            new_data_ajaxurl = valid_value_from_dict(more_data, "data-ajaxurl")
            if not load_more_data_base_url and new_data_ajaxurl:
                load_more_data_base_url = BASE_IMDB_URL.with_path(
                    new_data_ajaxurl
                )

            if not load_more_data_base_url:
                load_more_data = False
                continue

            current_url = load_more_data_base_url.with_query(
                {
                    "ref_": "undefined",
                    "paginationKey": data_key,
                }
            )

    return user_review_set
