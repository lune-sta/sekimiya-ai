import json
import logging
import os
import random
import re
import time
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Literal, TypedDict

import boto3
import discord
import openai
import tiktoken  # type: ignore[import]
from functions import available_functions, function_info, helpers

ssm_client = boto3.client("ssm")
ssm_response = ssm_client.get_parameters(
    Names=[
        "/sekimiya-ai/discord-token",
        "/sekimiya-ai/openai-secret",
        "/sekimiya-ai/recruit-api-key",
        "/sekimiya-ai/gcp-api-key",
        "/sekimiya-ai/google-cse-id",
    ],
    WithDecryption=True,
)

parameters = {param["Name"]: param["Value"] for param in ssm_response["Parameters"]}

DISCORD_TOKEN = parameters["/sekimiya-ai/discord-token"]
OPENAI_API_KEY = parameters["/sekimiya-ai/openai-secret"]
os.environ["RECRUIT_API_KEY"] = parameters["/sekimiya-ai/recruit-api-key"]
os.environ["GCP_API_KEY"] = parameters["/sekimiya-ai/gcp-api-key"]
os.environ["GOOGLE_CSE_KEY"] = parameters["/sekimiya-ai/google-cse-id"]

CHARACTER_SETTING = os.environ["CHARACTER_SETTING"].strip()
SPOILER_CATEGORY_NAME = "SPOILERS"
LOG_GROUP_NAME = os.environ["LOG_GROUP_NAME"]
TOKENS_PER_MESSAGE = 4
TOKENS_PER_NAME = -1
SMALL_MODEL_NAME = "gpt-3.5-turbo-0613"
SMALL_MODEL_TOKEN_LIMIT = 1024 * 4 * 0.9
LARGE_MODEL_NAME = "gpt-3.5-turbo-16k"
LARGE_TOKEN_LIMIT = 1024 * 16 * 0.9

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
openai.api_key = OPENAI_API_KEY
discord_intents = discord.Intents.default()
discord_intents.typing = False
discord_client = discord.Client(intents=discord_intents)
discord_tree = discord.app_commands.CommandTree(discord_client)
encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")


class MessageCore(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class Message(MessageCore, total=False):
    name: str


@discord_client.event
async def on_ready():
    await discord_tree.sync()


def get_role(author) -> str:
    if author == discord_client.user:
        return "assistant"
    else:
        return "user"


def modify_text_style(text: str) -> str:
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r" \2 ", text)

    text = text.replace("(笑)", "ｗ").replace("（笑）", "ｗ")
    text = text.replace("♪", "！")

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


def num_tokens_from_messages(messages: Iterable[Message]) -> int:
    num_tokens = 0
    for message in messages:  # type: Message
        num_tokens += TOKENS_PER_MESSAGE
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += TOKENS_PER_NAME
    # every reply is primed with <|start|>assistant<|message|>
    num_tokens += 3
    return num_tokens


def get_completion(messages: list, max_retry: int = 3) -> str:
    system_content = CHARACTER_SETTING.replace(
        "<current_datetime>", helpers.get_current_time()
    )
    messages.insert(0, {"role": "system", "content": system_content})

    while num_tokens_from_messages(messages) > SMALL_MODEL_TOKEN_LIMIT:
        messages.pop(1)

    for i in range(max_retry):
        try:
            logger.info(
                "OpenAI input messages: " + json.dumps(messages, ensure_ascii=False)
            )
            response = openai.ChatCompletion.create(
                model=SMALL_MODEL_NAME, messages=messages, functions=function_info
            )
            logger.info("OpenAI response: " + json.dumps(response, ensure_ascii=False))
            response_message = response["choices"][0]["message"]

            if "function_call" in response_message:
                function_name = response_message["function_call"]["name"]
                function_to_call = available_functions[function_name]
                function_args = json.loads(
                    response_message["function_call"]["arguments"]
                )
                function_res = function_to_call(**function_args)

                # messages.append(response_message)
                messages.append(
                    {"role": "function", "name": function_name, "content": function_res}
                )

                model_name = SMALL_MODEL_NAME
                if num_tokens_from_messages(messages) > SMALL_MODEL_TOKEN_LIMIT:
                    model_name = LARGE_MODEL_NAME
                    while num_tokens_from_messages(messages) > LARGE_TOKEN_LIMIT:
                        messages.pop(1)

                logger.info(
                    "OpenAI input messages: " + json.dumps(messages, ensure_ascii=False)
                )
                response = openai.ChatCompletion.create(
                    model=model_name, messages=messages
                )
                logger.info(
                    "OpenAI response: " + json.dumps(response, ensure_ascii=False)
                )
                response_message = response["choices"][0]["message"]

            return response_message["content"]

        except openai.error.OpenAIError as e:
            logger.error("Error on retry " + str(i) + ": " + str(e))
            if i < max_retry - 1:
                logger.info("Retrying after 5 seconds...")
                time.sleep(5)
            else:
                return str(e)


def clean_message(message: str) -> str:
    return re.sub(r"<@\d+>", "", message).strip()


@discord_client.event
async def on_message(message):
    if not (
        discord_client.user.mentioned_in(message)
        and message.author != discord_client.user
    ):
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
        await message.channel.send(modify_text_style(res), reference=message)

    else:
        res = get_completion([{"role": "user", "content": message.content}])
        await message.channel.send(modify_text_style(res), reference=message)


@discord_tree.command(name="list-spoiler-channels", description="ネタバレ部屋の一覧を表示します。")
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


@discord_tree.command(name="join-spoiler-channel", description="ネタバレ部屋に参加します。")
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


@discord_tree.command(name="logs", description="関宮AIのログを直近n件表示します。")
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
    discord_client.run(DISCORD_TOKEN)
