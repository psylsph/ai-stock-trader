#!/usr/bin/env python3
"""Debug script to test the web application directly."""

import asyncio
from src.web.app import app
from src.database import init_db
from src.config.settings import settings

async def test_web_app():
    print("Initializing database...")
    repo = await init_db(settings.DATABASE_URL, reset=False)
    
    print("Setting repository in app...")
    app.state.repo = repo
    
    print("Testing API endpoint...")
    from fastapi.testclient import TestClient
    client = TestClient(app)
    
    try:
        response = client.get("/")
        print(f"Response status: {response.status_code}")
        if response.status_code != 200:
            print(f"Response text: {response.text}")
            print(f"Response headers: {response.headers}")
    except Exception as e:
        print(f"Error accessing root: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        response = client.get("/api/status")
        print(f"API status response: {response.status_code}")
        if response.status_code != 200:
            print(f"API response text: {response.text}")
    except Exception as e:
        print(f"Error accessing API: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_web_app())