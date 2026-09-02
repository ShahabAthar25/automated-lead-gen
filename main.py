import asyncio
import logging
import signal
import sys

from reddit_lead_gen.core.listener import MultiSubredditAdaptiveListener
from reddit_lead_gen.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


async def main():
    # Everything (Pipeline, DB, Subreddits, Trackers) defaults to settings
    listener = MultiSubredditAdaptiveListener()

    # Graceful shutdown handler
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: listener.stop())
        except NotImplementedError:
            pass  # Windows compatibility

    # Just start the listener ticker loop directly
    await listener.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt, SystemExit:
        logging.info("👋 Engine shut down successfully.")
