import google.genai as genai
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

class GeminiModel():
    

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client()
    
    def get_model(self):
        def generate(prompt: str) -> str:
            response = self.client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt
            )
            return response.text
        
        return generate

    




gemini = GeminiModel()
gemini_model = gemini.get_model()  # Raw model object