"""Main entry point for the AI Stock Trader application."""

import asyncio
import logging
import argparse
import os
import uvicorn
from src.config.settings import settings
from src.database import init_db
from src.orchestration.workflows import TradingWorkflow
from src.web.app import app, set_repo

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main function to run the AI Stock Trader bot."""
    parser = argparse.ArgumentParser(description="AI Stock Trader Bot")
    parser.add_argument("--restart", action="store_true", help="Reset the database and remove portfolio.json before starting")
    parser.add_argument("--web", action="store_true", help="Start web server for monitoring and control")
    parser.add_argument("--test-mode", action="store_true", help="Ignore market hours for testing buy/sell logic")
    args = parser.parse_args()

    if args.test_mode:
        settings.IGNORE_MARKET_HOURS = True
        logger.info("TEST MODE ENABLED: Ignoring market hours")

    logger.info("Starting AI Stock Trader Bot...")
    logger.info("[DEBUG] Web server flag: %s", args.web)
    logger.info("[DEBUG] Trading mode: %s", settings.TRADING_MODE)
    logger.info("[DEBUG] LM Studio URL: %s", settings.LM_STUDIO_API_URL)

    # Initialize Database
    if args.restart:
        logger.info("RESTART FLAG DETECTED: Resetting database and removing portfolio.json...")

        # Remove portfolio.json if it exists
        portfolio_file = os.getenv("PORTFOLIO_FILE", "portfolio.json")
        if os.path.exists(portfolio_file):
            try:
                os.remove(portfolio_file)
                logger.info("Removed %s", portfolio_file)
            except OSError as e:
                logger.warning("Failed to remove %s: %s", portfolio_file, e)

    logger.info("Initializing database at %s", settings.DATABASE_URL)
    repo = await init_db(settings.DATABASE_URL, reset=args.restart)

    workflow = TradingWorkflow(settings, repo)

    if args.web:
        logger.info("Starting in WEB SERVER mode...")
        set_repo(repo)
        logger.info("Web server running on http://0.0.0.0:8000")
        logger.info("Use web dashboard to monitor and control trades")

        # Start bot logic in background tasks
        asyncio.create_task(workflow.run_startup_analysis())
        asyncio.create_task(workflow.run_monitoring_loop())

        # Create uvicorn config and server to run in the same event loop
        config = uvicorn.Config(app, host="0.0.0.0", port=8000, loop="asyncio", log_level="warning")
        server = uvicorn.Server(config)

        # Run the server and wait for it to finish
        await server.serve()
    else:
        logger.info("Starting in BOT MODE...")
        logger.info("Trades will execute automatically based on mode:")
        logger.info("  - Paper mode: Auto-execute all validated trades")
        logger.info("  - Live mode: Require manual approval via web dashboard")

        try:
            await workflow.run_startup_analysis()
            await workflow.run_monitoring_loop()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Fatal error: %s", e, exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
