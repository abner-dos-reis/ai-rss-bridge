import json
import os
from cryptography.fernet import Fernet
import base64

class ConfigManager:
    def __init__(self, config_path="/app/data/config.json", key_path="/app/data/encryption.key"):
        self.config_path = config_path
        self.key_path = key_path
        
        # Garantir que o diretório existe
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
        
        self.cipher = self._get_or_create_cipher()
        print(f"ConfigManager initialized - config: {self.config_path}, key: {self.key_path}")
        
    def _get_or_create_cipher(self):
        """Get or create encryption key for API keys"""
        if os.path.exists(self.key_path):
            with open(self.key_path, 'rb') as f:
                key = f.read()
            print("Loaded existing encryption key")
        else:
            key = Fernet.generate_key()
            with open(self.key_path, 'wb') as f:
                f.write(key)
            print("Created new encryption key")
        return Fernet(key)
    
    def save_api_key(self, provider, api_key):
        """Save encrypted API key for a provider"""
        print(f"Saving API key for provider: {provider}")
        config = self.load_config()
        if 'api_keys' not in config:
            config['api_keys'] = {}
        
        # Encrypt API key
        encrypted_key = self.cipher.encrypt(api_key.encode()).decode()
        config['api_keys'][provider] = encrypted_key
        
        self._save_config(config)
        print(f"API key saved successfully for {provider}")
    
    def get_api_key(self, provider):
        """Get decrypted API key for a provider"""
        config = self.load_config()
        if 'api_keys' not in config or provider not in config['api_keys']:
            print(f"No API key found for provider: {provider}")
            return None
        
        try:
            encrypted_key = config['api_keys'][provider].encode()
            return self.cipher.decrypt(encrypted_key).decode()
        except Exception as e:
            print(f"Error decrypting API key for {provider}: {e}")
            return None
    
    def delete_api_key(self, provider):
        """Delete API key for a provider"""
        print(f"Deleting API key for provider: {provider}")
        config = self.load_config()
        if 'api_keys' in config and provider in config['api_keys']:
            del config['api_keys'][provider]
            self._save_config(config)
            print(f"API key deleted for {provider}")
    
    def get_saved_providers(self):
        """Get list of providers with saved API keys"""
        config = self.load_config()
        providers = list(config.get('api_keys', {}).keys())
        print(f"Saved providers: {providers}")
        return providers
    
    def save_theme(self, theme):
        """Save user theme preference"""
        config = self.load_config()
        config['theme'] = theme
        self._save_config(config)
    
    def get_theme(self):
        """Get user theme preference"""
        config = self.load_config()
        return config.get('theme', 'light')
    
    def save_last_ai_provider(self, provider):
        """Save last selected AI provider"""
        config = self.load_config()
        config['last_ai_provider'] = provider
        self._save_config(config)
    
    def get_last_ai_provider(self):
        """Get last selected AI provider"""
        config = self.load_config()
        return config.get('last_ai_provider', 'openai')
    
    def load_config(self):
        """Load configuration from file"""
        print(f"Loading config from: {self.config_path}")
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                print(f"Loaded config: {config}")
                return config
            except Exception as e:
                print(f"Error loading config: {e}")
                return {}
        print("Config file doesn't exist, returning empty config")
        return {}
    
    def _save_config(self, config):
        """Save configuration to file"""
        print(f"Saving config to: {self.config_path}")
        print(f"Config data: {config}")
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            print("Config saved successfully")
        except Exception as e:
            print(f"Error saving config: {e}")
            raise