import os
import random
import logging
import json
import re
import time
from datetime import datetime, timedelta, timezone

import openai
import discord
import boto3

ssm_client = boto3.client("ssm")
ssm_response = ssm_client.get_parameters(
    Names=["/sekimiya-ai/discord-token", "/sekimiya-ai/openai-secret"],
    WithDecryption=True,
)

DISCORD_TOKEN = ssm_response["Parameters"][0]["Value"]
OPENAI_API_KEY = ssm_response["Parameters"][1]["Value"]
CHARACTER_SETTING = os.environ["CHARACTER_SETTING"].strip()
SPOILER_CATEGORY_NAME = "SPOILERS"
LOG_GROUP_NAME = os.environ["LOG_GROUP_NAME"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
openai.api_key = OPENAI_API_KEY
intents = discord.Intents.default()
intents.typing = False
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)


@client.event
async def on_ready():
    await tree.sync()


def modify_output(text: str) -> str:
    # (笑)とか使わない
    text = text.replace("(笑)", "ｗ").replace("（笑）", "ｗ")

    # ！とか？を重ねて使ってオタク感を出す
    exclamation_marks = ["！", "！！"]
    question_marks = ["？", "？？", "！？"]
    laugh_marks = ["ｗ", "ｗｗ", "ｗｗｗ"]
    text = "".join(
        [
            random.choice(exclamation_marks)
            if char == "！"
            else random.choice(question_marks)
            if char == "？"
            else random.choice(laugh_marks)
            if char == "ｗ"
            else char
            for char in text
        ]
    )

    text.replace("ｗ。", "ｗ ")
    return text


def calc_message_tokens(messages: list) -> int:
    return sum(len(message["content"]) for message in messages) + len(CHARACTER_SETTING)


def get_completion(messages: list, max_retry: int = 3, max_tokens: int = 3072) -> str:
    messages.insert(0, {"role": "system", "content": CHARACTER_SETTING})

    total_tokens = calc_message_tokens(messages)
    while total_tokens > max_tokens:
        messages.pop(1)
        total_tokens = calc_message_tokens(messages)

    for i in range(max_retry):
        try:
            res = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
            res_context = res["choices"][0]["message"]["content"]
            logger.info("OpenAI response: " + json.dumps(res, ensure_ascii=False))

            return res_context
        except openai.error.OpenAIError as e:
            logger.error("Error on retry " + str(i) + ": " + str(e))
            if i < max_retry - 1:
                logger.info("Retrying after 5 seconds...")
                time.sleep(5)
            else:
                return str(e)


def get_role(author) -> str:
    if author == client.user:
        return "assistant"
    else:
        return "user"


def clean_message(message: str) -> str:
    return re.sub(r"<@\d+>", "", message).strip()


@client.event
async def on_message(message):
    if not (client.user.mentioned_in(message) and message.author != client.user):
        return

    if message.reference:
        referenced_message = await message.channel.fetch_message(
            message.reference.message_id
        )
        messages = [
            {
                "role": get_role(referenced_message.author),
                "content": clean_message(referenced_message.content),
            }
        ]

        referenced_message = referenced_message.reference
        while referenced_message is not None:
            referenced_message = await message.channel.fetch_message(
                referenced_message.message_id
            )
            messages.append(
                {
                    "role": get_role(referenced_message.author),
                    "content": clean_message(referenced_message.content),
                }
            )
            referenced_message = referenced_message.reference
        messages.reverse()
        messages.append(
            {
                "role": get_role(message.author),
                "content": clean_message(message.content),
            }
        )
        messages.append({"role": "user", "content": message.content})
        res = get_completion(messages)
        await message.channel.send(modify_output(res), reference=message)

    else:
        res = get_completion([{"role": "user", "content": message.content}])
        await message.channel.send(modify_output(res), reference=message)


@tree.command(name="list-spoiler-channels", description="ネタバレ部屋の一覧を表示します。")
async def list_spoiler_channels(interaction: discord.Interaction):
    guild = interaction.guild
    spoiler_category = None

    for category in guild.categories:
        if category.name.upper() == SPOILER_CATEGORY_NAME:
            spoiler_category = category
            break

    channels = spoiler_category.channels
    channel_list = "\n".join([f"- {channel.name}" for channel in channels])
    response_message = f"```\n{channel_list}```"
    await interaction.response.send_message(response_message, ephemeral=True)


@tree.command(name="join-spoiler-channel", description="ネタバレ部屋に参加します。")
async def join_spoiler_channels(interaction: discord.Interaction, channel_name: str):
    guild = interaction.guild
    spoiler_category = None

    for category in guild.categories:
        if category.name.upper() == SPOILER_CATEGORY_NAME:
            spoiler_category = category
            break

    target_channel = None
    for channel in spoiler_category.channels:
        if channel.name.lower() == channel_name.lower():
            target_channel = channel
            break

    if target_channel is None:
        await interaction.response.send_message("該当のチャンネルが見つかりません。", ephemeral=True)

    member = interaction.user
    overwrites = target_channel.overwrites_for(member)
    overwrites.read_messages = True
    await target_channel.set_permissions(member, overwrite=overwrites)
    await interaction.response.send_message(
        f"{channel_name} チャンネルに参加しました。", ephemeral=True
    )


@tree.command(name="logs", description="関宮AIのログを直近n件表示します。")
async def fetch_bot_logs(interaction: discord.Interaction, n: int = 10):
    if n > 20:
        n = 20

    logs_client = boto3.client("logs", region_name="us-west-2")

    log_streams_response = logs_client.describe_log_streams(
        logGroupName=LOG_GROUP_NAME, orderBy="LastEventTime", descending=True, limit=1
    )

    log_stream_name = log_streams_response["logStreams"][0]["logStreamName"]

    # Get the latest log events from the log stream
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=1)
    log_events_response = logs_client.get_log_events(
        logGroupName=LOG_GROUP_NAME,
        logStreamName=log_stream_name,
        startTime=int(start_time.timestamp() * 1000),
        endTime=int(end_time.timestamp() * 1000),
        limit=n,
        startFromHead=False,
    )

    jst_offset = timedelta(hours=9)
    messages = []

    for event in log_events_response["events"]:
        log_message = event["message"]
        if "OpenAI response" in log_message:
            log_message = "INFO:__main__:OpenAI response: (...)"
        utc_timestamp = datetime.fromtimestamp(event["timestamp"] / 1000, timezone.utc)
        jst_timestamp = str(utc_timestamp + jst_offset).split(".")[0]
        messages.append(f"[{jst_timestamp}] {log_message}")

    response_message = "\n".join(messages)
    await interaction.response.send_message(f"```\n{response_message}```")


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
