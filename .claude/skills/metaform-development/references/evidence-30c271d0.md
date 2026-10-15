before: web_signs row ['facing'] | view.json exists False
after one start: web_signs row None
view.json: {'': {'web_layout': '{"areas": {}, "floating": [], "off": []}', 'web_physics': 'flat', 'web_signs': 'facing'}}
peers: {"peers": [{"name": "other", "url": "http://127.0.0.1:7440/.well-known/agent-card.json", "token_env": "OTHER_TOKEN", "token_set": false}]}