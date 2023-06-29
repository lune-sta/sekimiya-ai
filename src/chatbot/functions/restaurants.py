import json
import logging
import os

import requests
from functions import helpers

logger = logging.getLogger(__name__)


def optimize_response(response: dict) -> list:
    # レスポンスから使いたいフィールドだけ抜き出す
    shops = response["results"]["shop"]
    optimized_shops = []

    for shop in shops:
        optimized_shop = {
            "name": shop["name"],
            "address": shop["address"],
            "budget": shop["budget"]["average"],
            "genre": shop["genre"]["name"],
            "open": shop["open"],
            "url": shop["urls"]["pc"],
            "catch": shop["catch"],
        }
        optimized_shops.append(optimized_shop)

    return optimized_shops


def search_restaurants(keyword: str, address: str, is_point: bool) -> str:
    if is_point:
        lat, lng = helpers.search_lat_lng(address)
        query = {
            "key": os.environ["RECRUIT_API_KEY"],
            "keyword": keyword,
            "lat": lat,
            "lng": lng,
            "format": "json",
            "count": "10",
            "range": 5,
        }
    else:
        query = {
            "key": os.environ["RECRUIT_API_KEY"],
            "keyword": " ".join([keyword, address]),
            "format": "json",
            "count": "10",
        }

    logger.info("Restaurant search request: " + json.dumps(query, ensure_ascii=False))

    response = requests.get(
        "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/", query
    )

    logger.info(json.dumps(response.json(), indent=4, ensure_ascii=True))

    return json.dumps(optimize_response(response.json()), ensure_ascii=False)
