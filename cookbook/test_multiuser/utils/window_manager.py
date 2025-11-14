"""
Window management utilities for Unity/Meta XR Simulator
Handles finding and focusing of application windows
"""
import time
import sys

try:
    import pygetwindow as gw  # type: ignore
except ImportError:
    gw = None


def find_window_by_title(window_title: str, timeout: float = 30.0):
    """
    Find a window by exact title match.
    
    Args:
        window_title: Exact window title to search for
        timeout: Maximum time to wait for window to appear (seconds)
    
    Returns:
        Window object if found, None otherwise
    """
    if gw is None:
        raise RuntimeError("pygetwindow is not installed. Please `pip install pygetwindow`.")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        all_windows = gw.getAllWindows()
        
        for window in all_windows:
            if window.title == window_title:
                return window
        
        time.sleep(0.5)  # Check every 500ms
    
    return None


def find_and_focus_meta_xr_simulator() -> bool:
    """
    Find and focus the Meta XR Simulator window.
    
    Window title is hardcoded as "Meta XR Simulator".
    If window is not found, the function returns False (caller should exit).
    
    Returns:
        True if window was found and focused, False otherwise
    """
    if gw is None:
        print("[WindowManager] Error: pygetwindow not installed. Cannot focus window.")
        print("[WindowManager] Please install: pip install pygetwindow")
        return False
    
    # Hardcoded window title
    WINDOW_TITLE = "Meta XR Simulator"
    SEARCH_TIMEOUT = 5.0  # seconds - quick search since window should already exist
    
    # Search for the window
    print(f"[WindowManager] Searching for window: {WINDOW_TITLE}...")
    window = find_window_by_title(WINDOW_TITLE, timeout=SEARCH_TIMEOUT)
    
    if window:
        print(f"[WindowManager] Found window: {window.title}")
        try:
            window.restore()  # Restore if minimized
            window.activate()  # Activate window to bring it to front
            time.sleep(0.5)  # Give it time to focus
            print("[WindowManager] Window focused successfully")
            return True
        except Exception as e:
            print(f"[WindowManager] Error focusing window: {e}")
            return False
    else:
        print(f"[WindowManager] Error: Could not find window '{WINDOW_TITLE}'")
        print(f"[WindowManager] Please make sure Meta XR Simulator is running.")
        return False


if __name__ == "__main__":
    # Test function
    print("Testing Meta XR Simulator find and focus...")
    success = find_and_focus_meta_xr_simulator()
    if success:
        print("✅ Success!")
    else:
        print("❌ Failed")
        sys.exit(1)

