import logging
from typing import List

from openai import OpenAI

from config import settings

logger = logging.getLogger(__name__)

_openai_client = OpenAI(api_key=settings.openai_api_key)


def embed_texts(texts: List[str]) -> List[List[float]]:
    response = _openai_client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def embed_text(text: str) -> List[float]:
    return embed_texts([text])[0]

