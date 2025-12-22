import os
from groq import Groq


class LlamaModel:

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("LLAMA_API_KEY")
        self.client = Groq(api_key=self.api_key)

    def get_model(self, model_name: str = "llama-3.1-8b-instruct"):
        class GroqWrapper:
            def __init__(self, client, model_name):
                self.client = client
                self.model_name = model_name
            
            def generate_content(self, prompt):
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.choices[0].message.content
        
        return GroqWrapper(self.client, model_name)


llama = LlamaModel()
llama_model = llama.get_model()