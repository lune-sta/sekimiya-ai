from datetime import datetime

import boto3
import pytz
from geopy import distance


def get_current_time():
    jst = pytz.timezone("Asia/Tokyo")
    now = datetime.now(jst)
    date_time_str = now.strftime("%Y年%m月%d日 %H:%M:%S")
    weekday_dict = {
        "Monday": "月曜日",
        "Tuesday": "火曜日",
        "Wednesday": "水曜日",
        "Thursday": "木曜日",
        "Friday": "金曜日",
        "Saturday": "土曜日",
        "Sunday": "日曜日",
    }
    weekday_str = weekday_dict[now.strftime("%A")]

    return f"{date_time_str} {weekday_str}"


def get_closest_point(reference_lng_lat: list, results: list) -> list:
    # Amazon Location Service のレスポンスは同名の地名を複数返すことがある
    # 都内が正解なことが多いので一番新宿に近い [lng, lat] を返す
    closest_point = None
    closest_distance = None

    for result in results:
        point_lng_lat = result["Place"]["Geometry"]["Point"][::-1]
        dist = distance.distance(reference_lng_lat, point_lng_lat).km

        if closest_distance is None or dist < closest_distance:
            closest_distance = dist
            closest_point = point_lng_lat

    return closest_point


def search_lat_lng(address: str):
    client = boto3.client("location")

    response = client.search_place_index_for_text(
        FilterCountries=[
            "JPN",
        ],
        IndexName="sekimiya-ai-index",
        MaxResults=10,
        Text=address,
    )

    reference_lng_lat = [35.6905, 139.6995]  # 新宿駅の座標
    point = get_closest_point(reference_lng_lat, response["Results"])
    return point
