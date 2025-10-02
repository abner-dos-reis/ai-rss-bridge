import requests
import json
from abc import ABC, abstractmethod

class AIProvider(ABC):
    @abstractmethod
    def extract_content(self, url: str, html_content: str) -> dict:
        pass

class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1/chat/completions"
    
    def extract_content(self, url: str, html_content: str) -> dict:
        prompt = f"""
        Extract RSS feed information from this website content:
        URL: {url}
        
        HTML Content: {html_content[:4000]}...
        
        Return a JSON with:
        - title: Main title of the website/page
        - description: Brief description of the content
        - items: Array of up to 10 articles/posts with detailed information
        
        For each article:
        - title: Clear, descriptive title
        - link: Full URL to the article
        - description: Detailed summary in 100-200 words explaining what the article is about, key points, and why it's interesting
        - image: URL of main article image (if available)
        - pubDate: Publication date in YYYY-MM-DD format
        
        Focus on extracting actual content, not navigation or ads.
        """
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=data, timeout=30)
            print(f"OpenAI response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                print(f"OpenAI raw content preview: {content[:200]}...")
                
                try:
                    parsed_result = json.loads(content)
                    print(f"OpenAI parsed result keys: {parsed_result.keys()}")
                    return parsed_result
                except json.JSONDecodeError as e:
                    print(f"Failed to parse OpenAI JSON: {e}")
                    return {"error": f"Failed to parse AI response: {str(e)}"}
            else:
                error_text = response.text[:500]
                print(f"OpenAI API error {response.status_code}: {error_text}")
                return {"error": f"OpenAI API error: {response.status_code}"}
                
        except requests.RequestException as e:
            print(f"OpenAI request exception: {e}")
            return {"error": f"OpenAI request failed: {str(e)}"}
        except Exception as e:
            print(f"OpenAI unexpected error: {e}")
            return {"error": f"OpenAI unexpected error: {str(e)}"}