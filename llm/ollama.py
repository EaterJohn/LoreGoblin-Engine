import json
import urllib.request
import urllib.error

class OllamaClient:
    def __init__(self, model='gemma4:e4b', host='http://localhost:11434'):
        self.model=model; self.host=host.rstrip('/')

    def chat(self, messages, tools=None):
        payload={'model':self.model,'messages':messages,'stream':False}
        if tools: payload['tools']=tools
        req=urllib.request.Request(self.host+'/api/chat', data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                raw=r.read()
        except urllib.error.URLError as e:
            # Не даём приложению упасть трейсбэком, если Ollama не отвечает.
            raise RuntimeError(f'Не удалось связаться с Ollama ({self.host}): {e}') from e
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f'Ollama вернула не-JSON ответ: {e}') from e