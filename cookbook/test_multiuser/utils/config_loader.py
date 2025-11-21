"""
Configuration loader module
Load unified configuration from config.json
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

_config_cache: Optional[Dict[str, Any]] = None


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration file
    
    Args:
        config_path: Configuration file path, defaults to config.json in project root
    
    Returns:
        Configuration dictionary
    """
    global _config_cache
    
    # Use cache to avoid repeated reads
    if _config_cache is not None:
        return _config_cache
    
    # Determine config file path
    if config_path is None:
        # Default to config.json in project root
        current_file = Path(__file__)
        project_root = current_file.parent.parent
        config_path = project_root / "config.json"
    else:
        config_path = Path(config_path)
    
    # Read configuration file
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    _config_cache = config
    return config


def get_config_value(key: str, default: Any = None, config: Optional[Dict] = None) -> Any:
    """
    Get configuration value, supports dot-separated nested keys
    
    Args:
        key: Configuration key, supports dot-separated nested keys (e.g. "llm.api_key")
        default: Default value
        config: Configuration dictionary, will be auto-loaded if None
    
    Returns:
        Configuration value
    
    Examples:
        >>> get_config_value("llm.api_key")
        "sk-xxx"
        >>> get_config_value("llm.model", "gpt-4")
        "gemini-2.5-flash"
    """
    if config is None:
        config = load_config()
    
    # Support dot-separated nested keys
    keys = key.split('.')
    value = config
    
    try:
        for k in keys:
            value = value[k]
        return value
    except (KeyError, TypeError):
        return default


def sync_unity_config():
    """
    Synchronize Unity config file's outputBasePath
    Ensure camera_extraction_config.json path matches config.json
    """
    config = load_config()
    output_base_path = config.get("unity_output_base_path")
    
    if not output_base_path:
        return
    
    # Unity config file path
    current_file = Path(__file__)
    project_root = current_file.parent.parent
    unity_config_path = project_root / "com.camera.extraction" / "camera_extraction_config.json"
    
    if not unity_config_path.exists():
        print(f"[Config Sync] Unity config file not found: {unity_config_path}")
        return
    
    # Read Unity config
    with open(unity_config_path, 'r', encoding='utf-8') as f:
        unity_config = json.load(f)
    
    # Check if update is needed
    current_path = unity_config.get("outputBasePath")
    if current_path != output_base_path:
        print(f"[Config Sync] Updating Unity outputBasePath: {current_path} -> {output_base_path}")
        unity_config["outputBasePath"] = output_base_path
        
        # Sync agentControlRequestDir
        unity_config["agentControlRequestDir"] = f"{output_base_path}\\agent_requests"
        
        # Write back to file
        with open(unity_config_path, 'w', encoding='utf-8') as f:
            json.dump(unity_config, f, indent=4)
        
        print(f"[Config Sync] Unity config file updated")
    else:
        print(f"[Config Sync] Unity outputBasePath already up to date: {current_path}")


if __name__ == "__main__":
    # Test configuration loading
    config = load_config()
    print("Configuration content:")
    print(json.dumps(config, indent=2, ensure_ascii=False))
    
    print("\nTest nested key retrieval:")
    print(f"LLM API Key: {get_config_value('llm.api_key')}")
    print(f"LLM Model: {get_config_value('llm.model')}")
    print(f"Max Steps: {get_config_value('max_steps')}")
    print(f"Unity Output Path: {get_config_value('unity_output_base_path')}")
    
    print("\nTest Unity config sync:")
    sync_unity_config()

