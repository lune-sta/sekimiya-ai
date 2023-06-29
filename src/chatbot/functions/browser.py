import json
import logging
import os

import requests
import tiktoken
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from sumy.nlp.tokenizers import Tokenizer
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.lex_rank import LexRankSummarizer

encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
logger = logging.getLogger(__name__)


def fetch_search_result(
    query: str, start_index: int = 1, token_limit: int = 1024 * 8
) -> str:
    result = []
    service = build(
        "customsearch",
        "v1",
        cache_discovery=False,
        developerKey=os.environ["GCP_API_KEY"],
    )
    search_result = (
        service.cse()
        .list(q=query, cx=os.environ["GOOGLE_CSE_KEY"], num=10, start=start_index)
        .execute()
    )

    for item in search_result["items"]:
        res_item = {
            "title": item["title"],
            "link": item["link"],
        }
        try:
            res_item["description"] = item["pagemap"]["metatags"][0]["og:description"]
        except KeyError:
            pass

        try:
            res_item["summary"] = fetch_website_summary(item["link"])
        except Exception as e:
            logger.error(e)
            pass

        result.append(res_item)

        if len(encoding.encode(json.dumps(result, ensure_ascii=False))) > token_limit:
            result.pop()
            break

    return json.dumps(result, ensure_ascii=False)


def fetch_website_summary(url: str, sentences_count: int = 100) -> str:
    if url.endswith(".pdf"):
        return ""

    logger.info("Fetch: " + url)
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")

    paragraphs = []
    for p in soup.find_all("p"):
        paragraphs.append(p.get_text())

    paragraphs = list(filter(None, paragraphs))
    text = "\n".join(paragraphs)

    if len(encoding.encode(text)) < 1024 * 4:
        return text

    parser = PlaintextParser.from_string(text, Tokenizer("japanese"))
    summarizer = LexRankSummarizer()

    res = summarizer(document=parser.document, sentences_count=sentences_count)
    res = "".join([s.__str__() for s in res])
    return res
