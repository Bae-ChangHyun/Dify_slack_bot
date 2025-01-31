import redis
from utils import debug_print

class RedisBase:
    """Redis 연결을 위한 기본 클래스"""
    def __init__(self, host='localhost', port=6379, db=0, pw='your_strong_password'):
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=pw,
            decode_responses=True
        )
        debug_print(f"Redis connected - Host: {host}, Port: {port}, DB: {db}")

class ConversationDB(RedisBase):
    def __init__(self, host='localhost', port=6379, db=15, pw='your_strong_password'):
        super().__init__(host, port, db, pw)
    
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

class UserDB(RedisBase):
    def __init__(self, host='localhost', port=6379, db=14, pw='your_strong_password'):
        super().__init__(host, port, db, pw)

    def get_current_model(self, user_id):
        debug_print(f"Retrieved from Redis - User: {user_id}, Model: {self.redis_client.hget(f'user:{user_id}', 'current_model')}")
        return self.redis_client.hget(f"user:{user_id}", "current_model")

    def get_current_prompt(self, user_id):
        debug_print(f"Retrieved from Redis - User: {user_id}, Prompt: {self.redis_client.hget(f'user:{user_id}', 'current_prompt')}")
        return self.redis_client.hget(f"user:{user_id}", "current_prompt")
    
    def set_user_model(self, user_id, model):
        debug_print(f"Saved to Redis - User: {user_id}, Model: {model}")
        self.redis_client.hset(f"user:{user_id}", "current_model", model)
        
    def set_user_prompt(self, user_id, prompt):
        debug_print(f"Saved to Redis - User: {user_id}, Prompt: {prompt}")
        self.redis_client.hset(f"user:{user_id}", "current_prompt", prompt)
            
