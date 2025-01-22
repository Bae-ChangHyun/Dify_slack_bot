from config import *
import requests
from utils import get_headers, debug_print

# api docs = {dify_base_url}/app/e7882139-3377-41e3-968b-866d89702c1d/develop

def chat_messages(user_query, user_id, dify_conversation_id=''):
    '''Send Chat Message'''
    api_url = f"{dify_base_url}/v1/chat-messages" 
    
    response = requests.post(api_url, 
                headers=get_headers(dify_api_key),
                json={
                    "inputs": {},
                    "query": user_query,
                    "response_mode": "blocking",  # blocking 모드
                    "user": user_id,
                    "conversation_id":dify_conversation_id,
                }
            )
    
    debug_print(f"LLM BOT: {response.json}")  
    logger.log_llm_response(response.json)
    
    return response, response.json()

def get_messages(user_id):
    '''Get Conversation History Messages api'''
    api_url = f"{dify_base_url}/v1/messages?user={user_id}&conversation_id="
    
    response = requests.get(api_url, headers=get_headers(dify_api_key))
    
    return response, response.json()