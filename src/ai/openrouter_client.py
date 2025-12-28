import json
import os
from typing import Dict, Any, List
from openai import AsyncOpenAI
from .prompts import REMOTE_MARKET_ANALYSIS_PROMPT

class OpenRouterClient:
    def __init__(self, api_key: str, model: str):
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        self.model = model

    async def analyze_market(self, 
                           portfolio_summary: str, 
                           timestamp: str, 
                           market_status: str,
                           news_summary: str = "No news available.") -> Dict[str, Any]:
        
        prompt = REMOTE_MARKET_ANALYSIS_PROMPT.format(
            portfolio_summary=portfolio_summary,
            timestamp=timestamp,
            market_status=market_status,
            news_summary=news_summary
        )
        
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            content = completion.choices[0].message.content
            return json.loads(content)
            
        except Exception as e:
            return {
                "analysis_summary": f"Error: {str(e)}",
                "recommendations": []
            }
