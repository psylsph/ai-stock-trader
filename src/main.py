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
    parser = argparse.ArgumentParser(description="AI Stock Trader Bot")
    parser.add_argument("--restart", action="store_true", help="Reset the database before starting")
    args = parser.parse_args()

    logger.info("Starting AI Stock Trader Bot...")
    
    # Initialize Database
    if args.restart:
        logger.info("RESTART FLAG DETECTED: Resetting database...")
    
    logger.info(f"Initializing database at {settings.DATABASE_URL}")
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
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
