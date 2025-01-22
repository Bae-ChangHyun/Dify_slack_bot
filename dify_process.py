from config import *
import requests
from utils import get_headers, debug_print

# api docs = {dify_base_url}/app/e7882139-3377-41e3-968b-866d89702c1d/develop

def chat_messages(user_query, user_id, dify_conversation_id=''):
    '''Send Chat Message'''
    
    end_point = "v1/chat-messages" 
    api_url = f"{dify_base_url}/{end_point}"
    
    response = requests.post(api_url, 
                    headers=get_headers(dify_api_key),
                    json={
                        "inputs": {},
                        "query": user_query,
                        "response_mode": "blockingsss",  # blocking 모드
                        "user": user_id,
                        "conversation_id":dify_conversation_id,
                    }
            )
    
    debug_print(f"LLM BOT: {response.json}")  
    logger.log_llm_response(response.json)
    
    return response, response.json()

def get_messages(user_id):
    '''Get Conversation History Messages api'''
    
    end_point = "v1/messages"
    params = {"user": user_id, "conversation_id": ""}
    api_url = f"{dify_base_url}/{end_point}"
    
    response = requests.get(api_url, 
                    headers=get_headers(dify_api_key), 
                    params=params
                )
    response_json = response.json()
