# coding: utf-8
import json
import urllib.request
import urllib.error
import xbmc
import re
import xbmcgui
import xbmcaddon

ADDON_SETTINGS = xbmcaddon.Addon()
icon_path = ADDON_SETTINGS.getAddonInfo('icon')

class DeepSeekExtractor:
    def __init__(self, api_key, base_url, model, prompt_template):
        self.api_key = api_key
        # Ensure base URL ends with correct path if user just entered "https://api.deepseek.com"
        # DeepSeek API is /chat/completions
        # If user provides full path, respect it? No, standard is baseurl.
        if base_url.endswith("/v1"):
            self.base_url = base_url
        elif base_url.endswith("/"):
            self.base_url = base_url.rstrip('/')
        else:
            self.base_url = base_url
            
        self.model = model
        # Prepend instruction to ensure JSON output
        if not prompt_template.startswith("Parse"):
             self.prompt_template = "Parse filename to JSON: " + prompt_template
        else:
             self.prompt_template = prompt_template

    def extract(self, filename):
        if not self.api_key:
            xbmc.log("[DeepSeek] API Key is missing", xbmc.LOGWARNING)
            return None

        # Handle different base URL styles if needed, but standard deepseek is https://api.deepseek.com
        # Completion endpoint: https://api.deepseek.com/chat/completions
        url = f"{self.base_url}/chat/completions"
        
        # Build prompt
        # User defined prompt template + filename
        content_prompt = f"{self.prompt_template}\n文件名: {filename}"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你只能返回标准json格式的数据"},
                {"role": "user", "content": content_prompt}
            ],
            "stream": False
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                resp_data = response.read()
                resp_json = json.loads(resp_data)
                
                # Check for errors in response
                if 'error' in resp_json:
                    xbmc.log(f"[DeepSeek] API returned error: {resp_json['error']}", xbmc.LOGERROR)
                    return None

                content = resp_json['choices'][0]['message']['content']
                xbmc.log(f"[DeepSeek] Raw response for {filename}: {content}", xbmc.LOGDEBUG)
                
                # Attempt to find JSON blob
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    try:
                        data = json.loads(json_str)
                        # Normalize keys if needed? User asked for specific keys.
                        # {"chinese":chinese, "englist":english, "year":year} (sic) in request
                        # Correct keys to expected internal use
                        return data
                    except json.JSONDecodeError:
                        xbmc.log(f"[DeepSeek] JSON decode failed for: {json_str}", xbmc.LOGERROR)
                else:
                    xbmc.log("[DeepSeek] No JSON found in response", xbmc.LOGERROR)
                    xbmcgui.Dialog().notification("TMDB CN Optimization", "DeepSeek 响应中未找到 JSON 数据", icon_path, 3000)
        except Exception as e:
            xbmc.log(f"[DeepSeek] Request Error: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification("TMDB CN Optimization", f"DeepSeek 请求错误: {e}", icon_path, 3000)
        return None
