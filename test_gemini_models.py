import requests
import json

def test_gemini_models(api_key):
    """Test which Gemini models are available"""
    
    # URL para listar modelos disponíveis
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    
    print("Testing Gemini API models...")
    print(f"API Key (first 10 chars): {api_key[:10]}...")
    
    try:
        response = requests.get(list_url)
        print(f"List models response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\nAvailable models:")
            
            for model in data.get('models', []):
                model_name = model.get('name', '')
                supported_methods = model.get('supportedGenerationMethods', [])
                
                # Apenas mostrar modelos que suportam generateContent
                if 'generateContent' in supported_methods:
                    print(f"✅ {model_name} - Supports: {supported_methods}")
                else:
                    print(f"❌ {model_name} - Supports: {supported_methods}")
                    
        else:
            print(f"Error listing models: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

# Exemplo de uso - você pode rodar isso para testar
if __name__ == "__main__":
    # Substitua pela sua API key do Gemini
    api_key = "YOUR_GEMINI_API_KEY_HERE"
    test_gemini_models(api_key)