<<<<<<< HEAD
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("Available Models:\n")

for model in client.models.list():
    print(model.name)
=======
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("Available Models:\n")

for model in client.models.list():
    print(model.name)
>>>>>>> 6ed5a0610661de02d4c9fa8781a0f9e0d1287d6c
