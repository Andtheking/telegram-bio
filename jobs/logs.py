import asyncio
from telegram.ext import ExtBot

SEND_LOGS = True
LOG_QUEUE = asyncio.Queue()

async def logEnqueue(to_log, log_type="INFO"):
    formatted = f"#TelegramBio LOG\n\n#{log_type.upper()}\n{to_log}"
    await LOG_QUEUE.put(formatted)
    print(formatted)

async def send_logs(bot: ExtBot, log_channel: int):
    while True:
        if SEND_LOGS:
            while not LOG_QUEUE.empty():
                mex = LOG_QUEUE.get(block=False)  # Blocca finchè non ce n'è almeno uno disponibile
                await bot.send_message(
                    chat_id = log_channel,
                    message=mex
                )
                await asyncio.sleep(10) # Per evitare di esplodere :)
        await asyncio.sleep(5) # Per evitare che le altre coroutine non vengano mai fatte (essendo velocissima prende tutte le risorse lei)
    