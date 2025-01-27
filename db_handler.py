import redis
from utils import debug_print

class ConversationDB:
    def __init__(self, host='localhost', port=6379, db=15, pw='your_strong_password'):
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=pw,  # Redis 비밀번호
            decode_responses=True  # 문자열 자동 디코딩
        )
    
    def save_conversation(self, thread_ts, conversation_id):
        """대화 ID 저장"""
        try:
            self.redis_client.set(f"conv:{thread_ts}", conversation_id)
            debug_print(f"Saved to Redis - Thread: {thread_ts}, Conversation ID: {conversation_id}")
        except Exception as e:
            debug_print(f"Redis save error: {e}")
    
    def get_conversation(self, thread_ts):
        """대화 ID 조회"""
        try:
            conversation_id = self.redis_client.get(f"conv:{thread_ts}")
            debug_print(f"Retrieved from Redis - Thread: {thread_ts}, Conversation ID: {conversation_id}")
            return conversation_id
        except Exception as e:
            debug_print(f"Redis get error: {e}")
            return None
    
    def delete_conversation(self, thread_ts):
        """대화 ID 삭제"""
        try:
            self.redis_client.delete(f"conv:{thread_ts}")
        except Exception as e:
            debug_print(f"Redis delete error: {e}")

class UserDB:
    def __init__(self, host='localhost', port=6379, db=14, pw='your_strong_password'):
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=pw,  # Redis 비밀번호
            decode_responses=True  # 문자열 자동 디코딩
        )

    def get_current_model(self, user_id):
        return self.redis_client.hget(f"user:{user_id}", "current_model")

    def get_current_prompt(self, user_id):
        return self.redis_client.hget(f"user:{user_id}", "current_prompt")
    
    def set_user_model(self, user_id, model):
        self.redis_client.hset(f"user:{user_id}", "current_model", model)
        
    def set_user_prompt(self, user_id, prompt):
        self.redis_client.hset(f"user:{user_id}", "current_prompt", prompt)
            
