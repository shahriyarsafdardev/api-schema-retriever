import openai
import time
import random
from dotenv import load_dotenv
from services.helpers.config import settings
from services.helpers.logger import getLogger

load_dotenv()
logger = getLogger()
openai.api_key = settings.openai_api_key


def create_embedding(text, max_retries=5):
    for i in range(max_retries):
        try:
            return openai.Embedding.create(input=[text], model="text-embedding-ada-002")['data'][0]['embedding']
        except Exception:
            time.sleep(2 ** i)
    return []

def context_based_completion(context, query, model="gpt-3.5-turbo", verbose=False, max_retries=5):
    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "user", "content": f"First check if the user question can be answered using only the information included in the context below. If it can be, then answer. If not, then return: \"None\" \n\n Context:{context} \n\n User question:{query}"},
                ]
            )
            return response['choices'][0]['message']['content']

        except openai.error.RateLimitError:
            # exponential backoff with jitter
            wait_time = (2 ** attempt) + random.random()
            logger.error(
                f"Request exceeded rate limit. Waiting {wait_time} seconds before retrying.")
            time.sleep(wait_time)

    raise Exception(f"Maximum number of retries ({max_retries}) exceeded.")

def completion(query, model="gpt-4", max_retries=5):
    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "user", "content": query},
                ]
            )
            return response['choices'][0]['message']['content']

        except openai.error.RateLimitError:
            # exponential backoff with jitter
            wait_time = (2 ** attempt) + random.random()
            logger.error(
                f"Request exceeded rate limit. Waiting {wait_time} seconds before retrying.")
            time.sleep(wait_time)

    raise Exception(f"Maximum number of retries ({max_retries}) exceeded.")

# print(completion("What is the capital of France?"))