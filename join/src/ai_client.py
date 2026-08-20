import asyncio
import json
import sys
import os
from pathlib import Path
from openai import AsyncOpenAI
import google.generativeai as genai

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))
from config import settings

class AIClient:
    def __init__(self):
        self.provider = settings.AI_PROVIDER.lower()
        
        if self.provider == "openrouter":
            self.api_key = settings.OPENROUTER_API_KEY
            if not self.api_key:
                raise ValueError("OPENROUTER_API_KEY not found in settings/.env")
                
            self.client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
                default_headers={
                    "HTTP-Referer": "https://github.com/fathibel/job-automation",
                    "X-Title": "Join.com Job Automation Pipeline",
                }
            )
            self.model = settings.OPENROUTER_MODEL
        elif self.provider == "gemini":
            self.api_key = settings.GOOGLE_API_KEY
            if not self.api_key:
                raise ValueError("GOOGLE_API_KEY not found in settings/.env")
            
            genai.configure(api_key=self.api_key)
            self.model_name = settings.GEMINI_MODEL
            self.client = genai.GenerativeModel(self.model_name)
        else:
            raise ValueError(f"Unknown AI_PROVIDER: {self.provider}")

    async def generate_content(self, prompt, json_mode=False, retries=3):
        """
        Generic wrapper supporting multiple providers.
        """
        if self.provider == "openrouter":
            return await self._generate_openrouter(prompt, json_mode, retries)
        elif self.provider == "gemini":
            return await self._generate_gemini(prompt, json_mode, retries)

    async def _generate_openrouter(self, prompt, json_mode, retries):
        messages = [
            {"role": "system", "content": "You are a professional job application assistant. " + ("Output ONLY valid JSON." if json_mode else "")},
            {"role": "user", "content": prompt}
        ]

        for attempt in range(retries):
            try:
                print(f"   [AI-OR] Requesting {self.model} (Attempt {attempt+1}/{retries})...")
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        response_format={"type": "json_object"} if json_mode else None,
                    ),
                    timeout=120 
                )
                
                if response and response.choices:
                    return response.choices[0].message.content
            except Exception as e:
                print(f"   [AI-OR Error] {e}")
                await asyncio.sleep(2)
        return None

    async def _generate_gemini(self, prompt, json_mode, retries):
        for attempt in range(retries):
            try:
                print(f"   [AI-Gemini] Requesting {self.model_name} (Attempt {attempt+1}/{retries})...")
                
                # Gemini 1.5+ supports schema or just plain text instruction
                generation_config = {}
                if json_mode:
                    generation_config["response_mime_type"] = "application/json"

                # Run in executor since genai is synchronous (mostly) or use async version if available
                # Actually genai has async support
                response = await self.client.generate_content_async(
                    prompt,
                    generation_config=generation_config
                )
                
                if response and response.text:
                    return response.text
            except Exception as e:
                print(f"   [AI-Gemini Error] {e}")
                await asyncio.sleep(2)
        return None

ai_client = AIClient()
