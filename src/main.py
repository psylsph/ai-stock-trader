"""Main entry point for the AI Stock Trader application."""

import asyncio
import logging
import argparse
from src.config import settings
from src.database import init_db
from src.orchestration.workflows import TradingWorkflow

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main function to run the AI Stock Trader bot."""
    parser = argparse.ArgumentParser(description="AI Stock Trader Bot")
    parser.add_argument("--restart", action="store_true", help="Reset the database before starting")
    parser.add_argument("--web", action="store_true", help="Start web server")
    args = parser.parse_args()

    logger.info("Starting AI Stock Trader Bot...")
    logger.info(f"[DEBUG] Web server flag: {args.web}")
    logger.info(f"[DEBUG] LM Studio URL: {settings.LM_STUDIO_API_URL}")

    # Initialize Database
    if args.restart:
        logger.info("RESTART FLAG DETECTED: Resetting database...")

    logger.info("Initializing database at %s", settings.DATABASE_URL)
    repo = await init_db(settings.DATABASE_URL, reset=args.restart)
    
    # Initialize Workflow
    workflow = TradingWorkflow(settings, repo)
    
    try:
        # Run Startup Analysis
        if settings.TRADING_MODE == "paper":
            logger.info("Running in PAPER TRADING mode.")
        
        await workflow.run_startup_analysis()
        
        # Start Monitoring Loop
        await workflow.run_monitoring_loop()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Fatal error: %s", e, exc_info=True)

    logger.info("[DEBUG] Trading workflow completed. Web server was NOT started.")
    logger.info("[DEBUG] To start web server, you need to add uvicorn startup code")

if __name__ == "__main__":
    asyncio.run(main())
