import os
import re
from datetime import datetime, timedelta

import boto3
from bs4 import BeautifulSoup
import requests
import pytz


ssm_client = boto3.client("ssm")
ssm_response = ssm_client.get_parameters(
    Names=["/sekimiya-ai/discord-token"],
    WithDecryption=True,
)


DISCORD_TOKEN = ssm_response["Parameters"][0]["Value"]
TARGET_CHANNEL_ID = os.environ["CHANNEL_ID"]
IMPORTANCE_LEVEL = int(os.environ["IMPORTANCE_LEVEL"])

API_ENDPOINT = f"https://discord.com/api/v10/channels/{TARGET_CHANNEL_ID}/messages"

headers = {
    "Authorization": f"Bot {DISCORD_TOKEN}",
    "Content-Type": "application/json",
}


def get_indicators():
    url = "https://www.gaikaex.com/gaikaex/mark/calendar/"

    r = requests.get(url)

    soup = BeautifulSoup(r.content, "html.parser")
    table = soup.find("table")
    rows = table.find_all("tr")

    indicators = []
    day = None

    for row in rows:
        data = row.find_all("td")

        if len(data) > 0:
            if "/" in data[0].get_text():
                day = data[0].get_text()
                time_ = data[1].get_text()
                country = data[2].get_text()
                indicator = data[3].get_text()
                importance = data[4].get_text()

            else:
                time_ = data[0].get_text()
                country = data[1].get_text()
                indicator = data[2].get_text()
                importance = data[3].get_text()

            if "" not in time_ or importance.count("★") < IMPORTANCE_LEVEL:
                continue

            indicators.append(
                {
                    "day": day,
                    "time": time_,
                    "country": country,
                    "indicator": indicator,
                    "importance": re.sub(r"[^★]", "", importance),
                }
            )
    return indicators


def generate_message(indicators: list):
    lines = ["今日と明日の経済指標カレンダーをお知らせします！", "```"]

    jst = pytz.timezone("Asia/Tokyo")
    now = datetime.now(jst)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    day_after_tomorrow = tomorrow + timedelta(days=1)
    current_year = now.year

    # インジケータを整形
    formatted_indicators = {}
    for indicator in indicators:
        day = indicator["day"]
        time = indicator["time"]
        day_str = f"{current_year}/{day.split('(')[0]}"
        dt = datetime.strptime(day_str, "%Y/%m/%d")
        dt_jst = jst.localize(dt)

        if today <= dt_jst < day_after_tomorrow:
            if day not in formatted_indicators:
                formatted_indicators[day] = []

            formatted_indicators[day].append(
                f"{time} {indicator['country']} {indicator['indicator']} {indicator['importance']}"
            )

    for day, events in formatted_indicators.items():
        lines.append(f"■ {day}")
        for event in events:
            lines.append(event)
        lines.append("")
    lines.pop()
    lines.append("```")

    return "\n".join(lines)


def send_message(text):
    payload = {
        "content": text,
    }
    requests.post(API_ENDPOINT, json=payload, headers=headers)


def handler(event, context):
    text = generate_message(get_indicators())
    send_message(text)


if __name__ == "__main__":
    handler(None, None)
