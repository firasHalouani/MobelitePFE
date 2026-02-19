from dotenv import load_dotenv
load_dotenv()
import os
import traceback
from app.services import ai_helper
import requests
import json

print('OPENROUTER_API_KEY present:', bool(os.getenv('OPENROUTER_API_KEY')))
print('OPENAI_API_KEY present:', bool(os.getenv('OPENAI_API_KEY')))
print('ai_helper._client_type:', getattr(ai_helper, '_client_type', None))
print('is_ai_available():', ai_helper.is_ai_available())
print('ai_helper._client repr:', repr(getattr(ai_helper, '_client', None)))

# If OpenRouter configured, do a raw HTTP check to /chat/completions
if getattr(ai_helper, '_client_type', None) == 'openrouter':
    try:
        key = os.getenv('OPENROUTER_API_KEY')
        base = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
        model = os.getenv('OPENROUTER_MODEL', 'deepseek/deepseek-r1-0528:free')
        url = base.rstrip('/') + '/chat/completions'
        headers = {
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json'
        }
        payload = {'model': model, 'messages': [{'role': 'user', 'content': 'ping'}]}
        print('Raw POST ->', url)
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
        print('Raw response status:', r.status_code)
        print('Raw response (truncated):', r.text[:1000])
    except Exception as e:
        print('Raw HTTP check failed:')
        traceback.print_exc()

try:
    res = ai_helper.generate_ai_recommendation("def foo(x):\n    return x\n")
    print('\n--- RESULT ---')
    print('type:', type(res))
    print(res)
except Exception as e:
    print('Exception during LLM call:')
    traceback.print_exc()
