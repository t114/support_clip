import subprocess
import os

os.environ['DISPLAY'] = ':1'
xauth_path = os.path.expanduser('~/.Xauthority')
if os.path.exists(xauth_path):
    print(f"Found .Xauthority at {xauth_path}")
    os.environ['XAUTHORITY'] = xauth_path
else:
    print(".Xauthority not found in home dir")

try:
    print("Checking xdpyinfo on :1 ...")
    result = subprocess.run(['xdpyinfo'], capture_output=True, text=True)
    if result.returncode == 0:
        print("Success! Display :0 is accessible.")
        print(result.stdout[:200]) # First few lines
    else:
        print(f"Failed. Return code: {result.returncode}")
        print(f"Stderr: {result.stderr}")
except FileNotFoundError:
    print("xdpyinfo not found. Trying xset q...")
    try:
        result = subprocess.run(['xset', 'q'], capture_output=True, text=True)
        if result.returncode == 0:
            print("Success! xset q passed.")
        else:
             print(f"xset q failed: {result.stderr}")
    except:
        print("xset also not found.")
except Exception as e:
    print(f"Error: {e}")
