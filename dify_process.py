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
        
    def create_conversation(self):
        """새로운 conversation 생성"""
        response, response_json = self.chat_messages(
            "Initialize conversation",
            "user",
            ""
        )
        conversation_id = response_json.get('conversation_id')
        debug_print(f"LLM BOT: {response.json}")
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
            "user": 'user',
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
    
    def get_current_model(self):
        """현재 사용 중인 모델 조회"""
        end_point = "v1/parameters"
        api_url = f"{self.base_url}/{end_point}"
        
        response = requests.get(api_url, headers=self.headers)
        response_json = response.json()
        
        return response_json.get("model", "gpt-3.5-turbo")  # 기본값 설정
    
    def get_available_models(self):
        """사용 가능한 모델 목록 조회"""
        end_point = "v1/parameters"  # 또는 올바른 엔드포인트
        api_url = f"{self.base_url}/{end_point}"
        
        try:
            response = requests.get(api_url, headers=self.headers)
            response.raise_for_status()
            response_json = response.json()
            
            # 기본 모델 리스트
            default_models = ["gpt-3.5-turbo", "gpt-4", "claude-2"]
            
            # API에서 모델 목록을 가져오거나 기본값 사용
            models = response_json.get("available_models", default_models)
            
            return models
            
        except Exception as e:
            debug_print(f"Error getting available models: {e}")
            return ["gpt-3.5-turbo", "gpt-4", "claude-2"]
    
    def set_model(self, model_name):
        """모델 변경"""
        end_point = "v1/parameters"
        api_url = f"{self.base_url}/{end_point}"
        
        data = {"model": model_name}
        response = requests.post(api_url, headers=self.headers, json=data)
        
        return response.json()
    
    def get_current_prompt(self):
        """현재 프롬프트 조회"""
        response, response_json = self.chat_messages(
            "[API] /prompt/show",
            "system",  # 시스템 사용자로 조회
            ""  # 새로운 대화로 시작
        )
        
        return response_json.get('answer', '')  # 응답에서 프롬프트 추출
    
    def set_prompt(self, prompt):
        """프롬프트 설정"""
        response, response_json = self.chat_messages(
            f"[API] /prompt/change {prompt}",
            "system",  # 시스템 사용자로 조회
            ""  # 새로운 대화로 시작
        )
        
        return response_json
    
    def get_enabled_tools(self):
        """현재 활성화된 툴 목록 조회"""
        end_point = "v1/parameters"
        api_url = f"{self.base_url}/{end_point}"
        
        response = requests.get(api_url, headers=self.headers)
        response_json = response.json()
        
        return response_json.get("tools", [])