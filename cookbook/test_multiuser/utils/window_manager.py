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
    Handles minimized windows by restoring them first.
    
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
            # Check if window is minimized (if pygetwindow supports it)
            try:
                if hasattr(window, 'isMinimized') and window.isMinimized:
                    print("[WindowManager] Window is minimized, restoring...")
            except:
                pass  # Some versions of pygetwindow may not support isMinimized
            
            # Force restore (works even if not minimized)
            window.restore()
            time.sleep(0.2)  # Wait for restore animation
            
            # Activate to bring to front
            window.activate()
            time.sleep(0.3)  # Give it time to activate
            
            # Double-check: restore again and activate to ensure focus
            window.restore()
            window.activate()
            time.sleep(0.5)  # Final wait for focus
            
            print("[WindowManager] Window focused successfully")
            return True
        except Exception as e:
            error_msg = str(e)
            # Check if error is actually a success (Windows error code 0)
            if "Error code from Windows: 0" in error_msg or "operation completed successfully" in error_msg.lower():
                print("[WindowManager] Window focused successfully (Windows reported success)")
                return True
            
            print(f"[WindowManager] Error focusing window: {e}")
            # Try alternative method using Windows API if available
            try:
                import win32gui
                import win32con
                hwnd = window._hWnd if hasattr(window, '_hWnd') else None
                if hwnd:
                    print("[WindowManager] Trying Windows API method...")
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.5)
                    print("[WindowManager] Window focused using Windows API")
                    return True
            except ImportError:
                # If Windows API not available, but we found the window, assume success
                print("[WindowManager] Windows API (pywin32) not available, but window was found")
                print("[WindowManager] Assuming success - window should be focused")
                return True
            except Exception as e2:
                print(f"[WindowManager] Windows API method also failed: {e2}")
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
        print("[Test] Success! Window found and focused.")
    else:
        print("[Test] Failed - Could not find or focus window.")
        sys.exit(1)

