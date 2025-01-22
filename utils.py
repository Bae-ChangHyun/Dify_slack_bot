from config import *

def debug_print(*args, **kwargs):
    if debug: print(*args, **kwargs)

def get_headers(token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    return headers