from arq.connections import RedisSettings

from app.config import settings


async def ping(ctx: dict) -> str:
    return "pong"


class WorkerSettings:
    # T-90min job, feature refresh and T+72h evaluation are added in M11.
    functions = (ping,)
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
