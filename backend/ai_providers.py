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
        # Limitar o tamanho do conteúdo para evitar timeouts
        max_content_length = 6000  # Aumentar para 6000 caracteres
        truncated_content = html_content[:max_content_length]
        if len(html_content) > max_content_length:
            print(f"OpenAI: Content truncated from {len(html_content)} to {max_content_length} chars")
        
        prompt = f"""
        Extract RSS feed information from this website content:
        URL: {url}
        
        HTML Content: {truncated_content}...
        
        CRITICAL INSTRUCTIONS:
        - The content above contains structured ARTICLE blocks with TITLE, LINK, DATE, IMAGE, CONTENT already extracted
        - YOU MUST USE THE EXACT LINKS PROVIDED - DO NOT CREATE OR GUESS NEW LINKS
        - YOU MUST USE THE EXACT IMAGES PROVIDED - DO NOT CREATE OR GUESS NEW IMAGES  
        - YOU MUST USE THE EXACT DATES PROVIDED - DO NOT CREATE OR GUESS NEW DATES
        - Your job is to organize this data into clean JSON and improve descriptions
        - DO NOT hallucinate or fabricate URLs - use what's provided
        
        Return a JSON with:
        - title: Main title of the website/page
        - description: Brief description of the content
        - items: Array of up to 10 articles/posts with detailed information
        
        For each article:
        - title: Clear, descriptive title
        - link: **USE THE EXACT LINK PROVIDED IN THE ARTICLE BLOCK** (do not create new URLs!)
        - description: Detailed summary in 100-200 words explaining what the article is about, key points, and why it's interesting
        - image: **USE THE EXACT IMAGE PROVIDED IN THE ARTICLE BLOCK** (do not create new image URLs!)
        - pubDate: **USE THE EXACT DATE PROVIDED IN THE ARTICLE BLOCK** (format as YYYY-MM-DD)
        
        CRITICAL IMAGE EXTRACTION:
        - Use the IMAGE value from each ARTICLE block
        - If IMAGE is empty, leave as empty string ""
        - DO NOT fabricate image URLs
        
        CRITICAL DATE EXTRACTION:
        - Use the DATE value from each ARTICLE block
        - Format as YYYY-MM-DD
        - If DATE is empty, use current date: 2025-10-30
        
        CRITICAL LINK EXTRACTION:
        - Use the LINK value from each ARTICLE block
        - DO NOT create or guess article URLs
        - If LINK is empty, use the base URL: {url}
        
        CRITICAL SORTING:
        *** MUST sort articles by pubDate in DESCENDING order (newest FIRST, oldest LAST) ***
        *** Article with date 2025-10-28 MUST come BEFORE article with date 2025-10-14 ***
        *** DO NOT return articles in the order they appear in HTML - SORT BY DATE! ***
        
        IMPORTANT: 
        1. Sort articles by pubDate DESC (newest first) - THIS IS MANDATORY!
        2. Focus on RECENT articles from 2024-2025
        3. Extract actual content, not navigation or ads
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
            response = requests.post(self.base_url, headers=headers, json=data, timeout=60)
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

class GeminiProvider(AIProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    
    def extract_content(self, url: str, html_content: str) -> dict:
        # Limitar o tamanho do conteúdo para evitar timeouts
        max_content_length = 8000  # Aumentar para 8000 caracteres para capturar mais conteúdo
        truncated_content = html_content[:max_content_length]
        if len(html_content) > max_content_length:
            truncated_content += "... [conteúdo truncado para evitar timeout]"
            print(f"Content truncated from {len(html_content)} to {max_content_length} chars")
        
        prompt = f"""
        You are an expert web scraper. Analyze this website and extract individual news articles, blog posts, or content items.

        Website URL: {url}
        Content: {truncated_content}

        CRITICAL INSTRUCTIONS - READ CAREFULLY:
        The content above contains structured ARTICLE blocks with:
        - TITLE: Article title
        - LINK: **EXACT article URL** (already extracted from HTML <a href>)
        - DATE: Publication date
        - IMAGE: **EXACT image URL** (already extracted from HTML <img src>)
        - CONTENT: Article preview text
        
        YOUR JOB:
        1. Parse these ARTICLE blocks
        2. **USE THE EXACT LINK VALUES** - DO NOT create or modify URLs
        3. **USE THE EXACT IMAGE VALUES** - DO NOT create or modify image URLs
        4. **USE THE EXACT DATE VALUES** - format as YYYY-MM-DD
        5. Improve the DESCRIPTION by expanding on the CONTENT provided
        6. DO NOT hallucinate or fabricate any URLs or data
        
        INSTRUCTIONS:
        1. Look for MULTIPLE different ARTICLE blocks in the content
        2. Each item should have a unique title and detailed description (100-200 words)
        3. **EXTRACT EXACT LINKS** - Use LINK value from ARTICLE block, do not create new URLs
        4. **EXTRACT EXACT IMAGES** - Use IMAGE value from ARTICLE block, do not create new image URLs
        5. **EXTRACT EXACT DATES** - Use DATE value from ARTICLE block, format as YYYY-MM-DD
        6. Focus on RECENT articles from 2024-2025
        7. SORT articles by date DESC (newest first)
        
        CRITICAL LINK GUIDELINES:
        - **NEVER CREATE OR GUESS ARTICLE URLs**
        - Use the LINK value exactly as provided in each ARTICLE block
        - If LINK is empty, use base URL: {url}
        
        CRITICAL IMAGE GUIDELINES:
        - **NEVER CREATE OR GUESS IMAGE URLs**  
        - Use the IMAGE value exactly as provided in each ARTICLE block
        - If IMAGE is empty, leave as empty string ""
        
        CRITICAL DATE GUIDELINES:
        - Use the DATE value from each ARTICLE block
        - Format as YYYY-MM-DD
        - If DATE is empty, use current date: 2025-10-30

        For a blog/news site like this, look for:
        - Article headlines
        - Post titles
        - News items
        - Blog entries
        - Event announcements

        Return a JSON object with this exact structure:
        {{
            "title": "Website/Section Title",
            "description": "Brief description of the website/section",
            "items": [
                {{
                    "title": "Article Title",
                    "link": "https://full-url-to-article",
                    "description": "Detailed 100-200 word description explaining what this article covers, its main points, and why readers would find it interesting or valuable.",
                    "image": "https://url-to-article-image",
                    "pubDate": "2024-10-01"
                }}
            ]
        }}

        Make sure each article has a UNIQUE title and comprehensive description.
        """
        
        headers = {
            "Content-Type": "application/json",
        }
        
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        try:
            # Retry logic for timeout errors
            max_retries = 2
            retry_count = 0
            last_error = None
            
            while retry_count <= max_retries:
                try:
                    # Aumentar timeout para 60s
                    response = requests.post(f"{self.base_url}?key={self.api_key}", headers=headers, json=data, timeout=60)
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result['candidates'][0]['content']['parts'][0]['text']
                        
                        # Clean up the response
                        content = content.strip()
                        if content.startswith('```json'):
                            content = content[7:]
                        if content.endswith('```'):
                            content = content[:-3]
                        content = content.strip()
                        
                        try:
                            return json.loads(content)
                        except json.JSONDecodeError as e:
                            return {"error": f"Failed to parse Gemini response: {str(e)}"}
                    else:
                        error_text = response.text[:500]
                        return {"error": f"Gemini API error: {response.status_code} - {error_text}"}
                
                except requests.exceptions.ReadTimeout as e:
                    retry_count += 1
                    last_error = e
                    print(f"Gemini timeout, tentativa {retry_count} de {max_retries + 1}...")
                    if retry_count <= max_retries:
                        import time
                        time.sleep(2)  # Esperar 2s antes de tentar novamente
                        continue
                    else:
                        return {"error": f"Gemini timeout após {max_retries + 1} tentativas. Tente usar menos conteúdo ou outro provider."}
                
                except requests.exceptions.RequestException as e:
                    return {"error": f"Gemini request error: {str(e)}"}
                    
        except Exception as e:
            return {"error": f"Gemini error: {str(e)}"}

class ClaudeProvider(AIProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1/messages"
    
    def extract_content(self, url: str, html_content: str) -> dict:
        # Limitar o tamanho do conteúdo
        max_content_length = 6000  # Aumentar para 6000 caracteres
        truncated_content = html_content[:max_content_length]
        if len(html_content) > max_content_length:
            print(f"Claude: Content truncated from {len(html_content)} to {max_content_length} chars")
        
        prompt = f"""
        Extract RSS feed information from this website content:
        URL: {url}
        
        HTML Content: {truncated_content}...
        
        CRITICAL - The content contains structured ARTICLE blocks with TITLE, LINK, DATE, IMAGE already extracted.
        **YOUR JOB: Use these EXACT values, do not create new URLs or data.**
        
        Return a JSON with:
        - title: Main title of the website/page
        - description: Brief description of the content
        - items: Array of up to 10 articles/posts with detailed information
        
        For each article:
        - title: Clear, descriptive title
        - link: **USE EXACT LINK from ARTICLE block** (do not create new URLs!)
        - description: Detailed summary in 100-200 words
        - image: **USE EXACT IMAGE from ARTICLE block** (do not create new image URLs!)
        - pubDate: **USE EXACT DATE from ARTICLE block** (format as YYYY-MM-DD)
        
        CRITICAL RULES:
        - DO NOT create or guess article URLs - use LINK from ARTICLE blocks
        - DO NOT create or guess image URLs - use IMAGE from ARTICLE blocks  
        - DO NOT create or guess dates - use DATE from ARTICLE blocks
        - If LINK/IMAGE/DATE is empty, use empty string "" or current date
        
        CRITICAL SORTING:
        *** MUST sort articles by pubDate in DESCENDING order (newest FIRST, oldest LAST) ***
        *** Article with date 2025-10-28 MUST come BEFORE article with date 2025-10-14 ***
        *** DO NOT return articles in the order they appear in HTML - SORT BY DATE! ***
        
        IMPORTANT: 
        1. Sort articles by pubDate DESC (newest first) - THIS IS MANDATORY!

        2. Focus on RECENT articles from 2024-2025
        3. Extract actual content, not navigation or ads
        """
        
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=data, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                content = result['content'][0]['text']
                try:
                    return json.loads(content)
                except:
                    return {"error": "Failed to parse Claude response"}
            else:
                return {"error": f"Claude API error: {response.status_code}"}
                
        except Exception as e:
            return {"error": f"Claude error: {str(e)}"}

class PerplexityProvider(AIProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.perplexity.ai/chat/completions"
    
    def extract_content(self, url: str, html_content: str) -> dict:
        # Limitar o tamanho do conteúdo
        max_content_length = 6000  # Aumentar para 6000 caracteres
        truncated_content = html_content[:max_content_length]
        if len(html_content) > max_content_length:
            print(f"Perplexity: Content truncated from {len(html_content)} to {max_content_length} chars")
        
        prompt = f"""
        Extract RSS feed information from this website content:
        URL: {url}
        
        HTML Content: {truncated_content}...
        
        CRITICAL - The content contains structured ARTICLE blocks with TITLE, LINK, DATE, IMAGE already extracted.
        **YOUR JOB: Use these EXACT values, do not create new URLs or data.**
        
        Return a JSON with:
        - title: Main title of the website/page
        - description: Brief description of the content
        - items: Array of up to 10 articles/posts with detailed information
        
        For each article:
        - title: Clear, descriptive title
        - link: **USE EXACT LINK from ARTICLE block** (do not create new URLs!)
        - description: Detailed summary in 100-200 words
        - image: **USE EXACT IMAGE from ARTICLE block** (do not create new image URLs!)
        - pubDate: **USE EXACT DATE from ARTICLE block** (format as YYYY-MM-DD)
        
        CRITICAL RULES:
        - DO NOT create or guess article URLs - use LINK from ARTICLE blocks
        - DO NOT create or guess image URLs - use IMAGE from ARTICLE blocks
        - DO NOT create or guess dates - use DATE from ARTICLE blocks
        
        CRITICAL SORTING:
        *** MUST sort articles by pubDate in DESCENDING order (newest FIRST, oldest LAST) ***
        *** Article with date 2025-10-28 MUST come BEFORE article with date 2025-10-14 ***
        *** DO NOT return articles in the order they appear in HTML - SORT BY DATE! ***
        - If LINK/IMAGE/DATE is empty, use empty string "" or current date
        
        IMPORTANT: 
        1. Sort articles by pubDate DESC (newest first)
        2. Focus on RECENT articles from 2024-2025
        3. Extract actual content, not navigation or ads
        """
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=data, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                try:
                    return json.loads(content)
                except:
                    return {"error": "Failed to parse Perplexity response"}
            else:
                return {"error": f"Perplexity API error: {response.status_code}"}
                
        except Exception as e:
            return {"error": f"Perplexity error: {str(e)}"}

def get_ai_provider(provider_name: str, api_key: str) -> AIProvider:
    """
    Factory function to get the appropriate AI provider
    """
    providers = {
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "perplexity": PerplexityProvider
    }
    
    if provider_name not in providers:
        raise ValueError(f"Unsupported AI provider: {provider_name}")
    
    return providers[provider_name](api_key)