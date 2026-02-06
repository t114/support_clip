from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
import os

# Try setting DISPLAY manually for test
os.environ['DISPLAY'] = ':0'
os.environ['WAYLAND_DISPLAY'] = 'wayland-0'
os.environ['MOZ_ENABLE_WAYLAND'] = '1'
# XDG_RUNTIME_DIR is also needed for Wayland, usually /run/user/1000
os.environ['XDG_RUNTIME_DIR'] = '/run/user/1000'

try:
    print(f"DISPLAY: {os.environ.get('DISPLAY')}")
    print(f"WAYLAND_DISPLAY: {os.environ.get('WAYLAND_DISPLAY')}")
    options = Options()
    options.add_argument("--headless") # Try WITH headless to diagnose
    
    print("Installing GeckoDriver...")
    service = Service(GeckoDriverManager().install())
    
    print("Starting Firefox...")
    driver = webdriver.Firefox(service=service, options=options)
    
    print("Navigating...")
    driver.get("https://www.google.com")
    print(driver.title)
    
    driver.quit()
    print("Success!")
except Exception as e:
    print(f"Error: {e}")
