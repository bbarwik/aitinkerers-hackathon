import google.genai as genai

from gamesight.config import get_settings


def create_client() -> genai.Client:
    settings = get_settings()
    api_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key is not None else None
    if api_key:
        return genai.Client(api_key=api_key)
    return genai.Client()


async def close_client(client: genai.Client) -> None:
    await client.aio.aclose()
    client.close()


__all__ = ["close_client", "create_client"]
