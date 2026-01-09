"""
Logging utility for Multi-Agent system.

This module provides a simple way to log messages to both console and file.
All print statements should be replaced with log() calls for file logging.

Usage:
    from utils.logger import setup_logger, log

    # At program start
    setup_logger("Agent1")  # Creates logs/Agent1_20260109_123456.txt

    # Replace print() with log()
    log("[Agent1] Starting exploration...")
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Global log file handle
_log_file = None
_log_enabled = True


def setup_logger(
    name: str = "agent",
    log_dir: str = "logs",
    also_print: bool = True
) -> str:
    """
    Setup logger to write to both console and file.
    
    Args:
        name: Name prefix for log file (e.g., "Agent1", "Coordinator")
        log_dir: Directory to store log files (default: "logs")
        also_print: Whether to also print to console (default: True)
    
    Returns:
        Path to the log file
    """
    global _log_file, _log_enabled
    
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{name}_{timestamp}.txt"
    log_filepath = log_path / log_filename
    
    # Open log file
    _log_file = open(log_filepath, "w", encoding="utf-8")
    _log_enabled = True
    
    # Write header
    _log_file.write(f"=" * 60 + "\n")
    _log_file.write(f"Log started at: {datetime.now().isoformat()}\n")
    _log_file.write(f"Name: {name}\n")
    _log_file.write(f"=" * 60 + "\n\n")
    _log_file.flush()
    
    # Override print function to also write to file
    _setup_print_redirect(also_print)
    
    return str(log_filepath)


def _setup_print_redirect(also_print: bool = True):
    """
    Redirect print() to also write to log file.
    """
    import builtins
    original_print = builtins.print
    
    def custom_print(*args, **kwargs):
        # Get the output string
        output = " ".join(str(arg) for arg in args)
        
        # Write to log file if available
        if _log_file and _log_enabled:
            timestamp = datetime.now().strftime("%H:%M:%S")
            _log_file.write(f"[{timestamp}] {output}\n")
            _log_file.flush()
        
        # Also print to console if enabled
        if also_print:
            original_print(*args, **kwargs)
    
    builtins.print = custom_print


def log(message: str, also_print: bool = True):
    """
    Log a message to file and optionally to console.
    
    Args:
        message: Message to log
        also_print: Whether to also print to console
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    # Write to log file
    if _log_file and _log_enabled:
        _log_file.write(f"[{timestamp}] {message}\n")
        _log_file.flush()
    
    # Print to console if enabled
    if also_print:
        print(message)


def close_logger():
    """
    Close the log file.
    """
    global _log_file
    if _log_file:
        _log_file.write(f"\n{'=' * 60}\n")
        _log_file.write(f"Log ended at: {datetime.now().isoformat()}\n")
        _log_file.write(f"{'=' * 60}\n")
        _log_file.close()
        _log_file = None


def get_log_file():
    """
    Get the current log file handle.
    """
    return _log_file


# Ensure log file is closed on exit
import atexit
atexit.register(close_logger)

