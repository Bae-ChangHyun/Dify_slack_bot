from config import *
import requests
import json
from utils import get_headers, debug_print

# api docs = {dify_base_url}/app/e7882139-3377-41e3-968b-866d89702c1d/develop

class DifyClient:
    def __init__(self, api_key=dify_api_key, base_url=dify_base_url):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = get_headers(api_key)
        self.conversation_id = ""  # 초기화 시점에는 conversation_id 없음
        
    def set_conversation_id(self, conversation_id):
        """conversation_id 설정"""
        self.conversation_id = conversation_id
        
    def create_conversation(self, user_id):
        """새로운 conversation 생성"""
        response, response_json = self.chat_messages(
            user_query = "Initialize conversation",
            user_id =user_id,
            conversation_id = ""
        )
        conversation_id = response_json.get('conversation_id')
        self.conversation_id = conversation_id
        
        return conversation_id
    
    def chat_messages(self, user_query, user_id, conversation_id=''):
        '''Send Chat Message'''
        
        end_point = "v1/chat-messages"
        api_url = f"{self.base_url}/{end_point}"
        
        response = requests.post(
            api_url,
            headers=self.headers,
            json={
                "inputs": {},
                "query": user_query,
                "response_mode": "blocking",
                "user": user_id,
                "conversation_id": conversation_id,
            }
        )
        response_json = response.json()
        debug_print(f"LLM BOT: {response_json}")
        logger.log_llm_response(response_json)
        
        error = response_json.get('code','') + response_json.get('message','')
        logger.log_api_status("POST", f"/{end_point}", response, error)
        
        return response, response_json
    
    def chat_messages_stream(self, user_query, user_id=''):
        '''Send Chat Message with Streaming'''
            
        end_point = "v1/chat-messages"
        api_url = f"{self.base_url}/{end_point}"
        
        headers = self.headers.copy()
        headers['Accept'] = 'text/event-stream'  # SSE를 위한 헤더 추가
        
        data = {
            "inputs": {},
            "query": user_query,
            "user": user_id,
            "response_mode": "streaming",
            "conversation_id": self.conversation_id  # conversation_id 추가
        }
            
        try:
            debug_print(f"Dify stream conversation_id: {data['conversation_id']}")
            response = requests.post(api_url, headers=headers, json=data, stream=True)
            return response
            
        except Exception as e:
            debug_print(f"Error in chat_messages_stream: {e}")
            raise e
    
    def get_messages(self, user_id):
        '''Get Conversation History Messages'''
        end_point = "v1/messages"
        params = {"user": user_id, "conversation_id": ""}
        api_url = f"{self.base_url}/{end_point}"
        
        response = requests.get(
            api_url,
            headers=self.headers,
            params=params
        )
        response_json = response.json()
        
        logger.log_api_status("GET", f"/{end_point}", response)
        
        return response, response_json