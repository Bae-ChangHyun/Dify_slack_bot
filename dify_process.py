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
                        "response_mode": "blocking",  # blocking 모드
                        "user": user_id,
                        "conversation_id":dify_conversation_id,
                    }
            )
    response_json = response.json()
    debug_print(f"LLM BOT: {response_json}")  
    logger.log_llm_response(response_json)
    error =response_json.get('code','') + response_json.get('message','')
    logger.log_api_status("POST", f"/{end_point}", response, error)
    
    return response, response_json

def chat_messages_stream(user_query, user_id='', conversation_id=''):
    
    end_point = "v1/chat-messages"
    api_url = f"{dify_base_url}/{end_point}"
    
    headers = get_headers(dify_api_key)
    headers['Accept'] = 'text/event-stream'  # SSE를 위한 헤더 추가
    
    data = {
        "inputs": {},
        "query": user_query,
        "user": user_id,
        "response_mode": "streaming",  # 스트리밍 모드로 설정
    }
    
    if conversation_id:
        data["conversation_id"] = conversation_id
        
    try:
        response = requests.post(api_url, headers=headers, json=data, stream=True)
        return response
        
    except Exception as e:
        debug_print(f"Error in chat_messages_stream: {e}")
        raise e

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
    
    #TODO - request에서 error나는 경우 정의하기
    #error =response_json.get('code','') + response_json.get('message','')
    #logger.log_api_status("GET", f"/{end_point}", response, error)
    logger.log_api_status("GET", f"/{end_point}", response)
    
    return response, response_json