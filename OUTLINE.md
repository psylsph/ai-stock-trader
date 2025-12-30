# AI TRading Bot

I'd like to build a stock trading bot that uses AI to make trading decisions.

The bot will trade on the stock market, buying and selling stocks based on AI predictions.

The bot should be able to trade on the UK stock market (London Stock Exchange).

The bot should at start up analyze the current state of the stock market and make a decision on whether to buy or sell.

The bot should then continue to monitor the stock market and make decisions on whether to buy or sell.

The bot should be able to handle different types of stocks, including both individual stocks and ETFs.

The bot should use an AI from OpenRouter to make decisions on whether to buy or sell. (defaulting to x-ai/grok-4). This model will have internet access and be able to perform is own searches etc.

The bot should use a local database to store information about the stock market.

The bot should be a local AI (via Ollama, defaulting to llama3.2:3b) for in day trading checks, if the local AI suggests a sell then the bot should escalate to the OpenRouter AI to confirm the decision. This bot will NOT have internet access and will NOT be able to perform is own searches etc. and so must be provided with the information it requires to make a decision.

The bot should be written in Python.

The bot should be able to run on a CPU only device if no GPU is available.

I would suggest the bot could use AutoGen to communicate with the AI models, the database and to orchestrate the trading process.
