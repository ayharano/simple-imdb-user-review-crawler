import csv
from argparse import ArgumentParser
from pathlib import Path

from simple_imdb_user_review_crawler import crawl_imdb_user_reviews_by_title_id


def retrieve_user_review_and_save_as_csv_file(
    title_id_set,
    destination_csv_filename,
):
    user_review_set = set()
    for title_id in title_id_set:
        current_title_user_review_set = crawl_imdb_user_reviews_by_title_id(
            title_id=title_id,
            review_content_as_single_line=True,
        )
        if current_title_user_review_set:
            user_review_set.update(current_title_user_review_set)

    a_user_review = None
    for a_user_review in user_review_set:
        break

    if a_user_review:
        fields = a_user_review.fields()
        with open(destination_csv_filename, "wt") as target_csv_file:
            csv_writer = csv.DictWriter(
                target_csv_file,
                fieldnames=fields,
            )

            csv_writer.writeheader()

            for review in user_review_set:
                csv_writer.writerow(review.as_dict())


if __name__ == "__main__":
    parser = ArgumentParser(
        description=(
            "Retrieve IMDb user reviews for a title and save as a csv file."
        ),
    )
    parser.add_argument(
        "destination_csv_filename",
        type=Path,
        help="CSV file to store data",
    )
    parser.add_argument(
        "title_ids",
        type=str,
        nargs="+",
        help="IMDb title ids",
    )

    args = parser.parse_args()

    retrieve_user_review_and_save_as_csv_file(
        destination_csv_filename=args.destination_csv_filename,
        title_id_set=set(args.title_ids),
    )
