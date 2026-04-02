import os
import sys
import time
import psutil
import win32gui
import win32process
import win32con
import pywintypes

# List of critical system processes that should NOT be closed
SAFE_PROCESSES = {
    "explorer.exe",
    "taskmgr.exe",
    "runtimebroker.exe",
    "dwm.exe",
    "lsass.exe",
    "services.exe",
    "wininit.exe",
    "winlogon.exe",
    "csrss.exe",
    "smss.exe",
    "system",
    "searchhost.exe",
    "shellexperiencehost.exe",
    "startmenuexperiencehost.exe",
    "textinputhost.exe",
    "py.exe",
    "python.exe",
    "pythonw.exe"
}

# Set to store PIDs that we've tried to close
attempted_pids = set()

def get_process_name(pid):
    try:
        proc = psutil.Process(pid)
        return proc.name().lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None

def is_main_window(hwnd):
    # Check if window is visible
    if not win32gui.IsWindowVisible(hwnd):
        return False
    
    # Check if window has a title - some apps use empty titles for sub-windows
    title = win32gui.GetWindowText(hwnd)
    
    # Filter out common background or system-owned windows
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    if style & win32con.WS_CHILD:
        return False
    
    # Exclude most system-related windows that are definitely not applications
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    # Some apps like LegionZone might use WS_EX_TOOLWINDOW, so we only exclude if it has no title
    if (ex_style & win32con.WS_EX_TOOLWINDOW) and not title:
        return False

    return True

def close_window(hwnd, lParam):
    if not is_main_window(hwnd):
        return

    # Get the process ID of the window
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    process_name = get_process_name(pid)

    if process_name and process_name not in SAFE_PROCESSES:
        # Don't close our own process or our parent (terminal)
        current_pid = os.getpid()
        try:
            current_proc = psutil.Process(current_pid)
            parent_pid = current_proc.ppid()
            if pid == current_pid or pid == parent_pid:
                return
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        title = win32gui.GetWindowText(hwnd) or "Unknown Application"
        print(f"Closing window: '{title}' (Process: {process_name}, PID: {pid})")
        
        # Record this PID for a potential second pass (force kill)
        attempted_pids.add(pid)
        
        # First attempt: Send WM_CLOSE message (graceful)
        try:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        except pywintypes.error as e:
            if e.winerror == 5:  # Access Denied
                print(f"Access denied for window: '{title}' (PID: {pid}).")
            else:
                print(f"Error closing window: '{title}' (PID: {pid}): {e}")

def main():
    print("Starting 'One-click Clear Screen'...")
    print("Step 1: Sending close signals to application windows...")
    
    # Pass 1: Enumerating all windows and closing gracefully
    win32gui.EnumWindows(close_window, None)
    
    # Wait for apps to close gracefully
    time.sleep(1.5)
    
    # Pass 2: Force Kill remaining processes that were attempted but are still alive
    print("Step 2: Checking for stubborn applications...")
    for pid in list(attempted_pids):
        try:
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                if proc.is_running():
                    name = proc.name()
                    if name.lower() not in SAFE_PROCESSES:
                        print(f"Force closing stubborn process: {name} (PID: {pid})")
                        proc.kill() # Direct kill
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    print("Cleanup complete.")

if __name__ == "__main__":
    # If compiled with PyInstaller, the script name will be close_all_apps.exe
    if getattr(sys, 'frozen', False):
        current_exe = os.path.basename(sys.executable).lower()
        SAFE_PROCESSES.add(current_exe)
    
    main()
