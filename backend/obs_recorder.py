import os
import time
import json
import logging
import socket
import subprocess
import re
import obswebsocket
from obswebsocket import obsws, requests as obs_requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import requests

logger = logging.getLogger(__name__)

# Auto-configure display environment if missing
def configure_display():
    if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
        # Check for Wayland first
        uid = os.getuid()
        runtime_dir = f"/run/user/{uid}"
        wayland_display = "wayland-0"
        if os.path.exists(os.path.join(runtime_dir, wayland_display)):
            os.environ['WAYLAND_DISPLAY'] = wayland_display
            os.environ['XDG_RUNTIME_DIR'] = runtime_dir
            if not os.environ.get('DISPLAY'):
                os.environ['DISPLAY'] = ":0"
            logger.info(f"Auto-configured Wayland environment: {wayland_display}")
        else:
            # Fallback to Xvfb detection
            detect_and_set_xvfb()

def detect_and_set_xvfb():
    try:
        result = subprocess.run(['pgrep', '-f', 'Xvfb'], capture_output=True, text=True)
        if result.returncode == 0:
            ps_result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            for line in ps_result.stdout.split('\n'):
                if 'Xvfb :' in line:
                    # Extract display number like :90
                    parts = line.split('Xvfb :')
                    if len(parts) > 1:
                        display_num = parts[1].split()[0]
                        os.environ['DISPLAY'] = f":{display_num}"
                        
                        # Also try to extract Xauthority for Snap
                        if '-auth' in line:
                            auth_parts = line.split('-auth ')
                            if len(auth_parts) > 1:
                                auth_path = auth_parts[1].split()[0]
                                if os.path.exists(auth_path):
                                    os.environ['XAUTHORITY'] = auth_path
                                    logger.info(f"Set XAUTHORITY from Xvfb: {auth_path}")
                                
                        logger.info(f"Using existing Xvfb DISPLAY=:{display_num}")
                        return True
    except Exception as e:
        logger.warning(f"Error detecting Xvfb: {e}")
    
    # Last resort fallback
    if not os.environ.get('DISPLAY'):
        os.environ['DISPLAY'] = ":0"
        logger.info("Defaulting to DISPLAY=:0")
    return False

configure_display()

# Enable headless mode for Firefox to avoid display issues
os.environ['MOZ_HEADLESS'] = "1"
logger.info("Enabled MOZ_HEADLESS=1 for Firefox")

class OBSRecorder:
    def __init__(self, host='localhost', port=4455, password='natsu@pass0001'):
        self.host = host
        self.port = port
        self.password = password
        self.ws = None

    def connect(self):
        try:
            self.ws = obsws(self.host, self.port, self.password)
            self.ws.connect()
            logger.info("Connected to OBS")
        except Exception as e:
            logger.error(f"Failed to connect to OBS: {e}")
            raise

    def disconnect(self):
        if self.ws:
            self.ws.disconnect()
            logger.info("Disconnected from OBS")

    def set_source_settings(self, source_name, url=None, width=1920, height=1080, css=None):
        """Updates the settings of a Browser Source in OBS."""
        if not self.ws:
            self.connect()
        
        settings = {}
        if url:
            settings['url'] = url
        if width:
            settings['width'] = width
        if height:
            settings['height'] = height
        if css is not None:
            settings['css'] = css

        try:
            self.ws.call(obs_requests.SetInputSettings(
                inputName=source_name,
                inputSettings=settings
            ))
            logger.info(f"Updated OBS source '{source_name}' settings.")
        except Exception as e:
            logger.error(f"Failed to update OBS source settings: {e}")
            raise

    def set_source_url(self, source_name, url):
        self.set_source_settings(source_name, url=url)

    def start_recording(self):
        if not self.ws:
            self.connect()
        logger.info("Starting recording...")
        self.ws.call(obs_requests.StartRecord())

    def stop_recording(self):
        if not self.ws:
            self.connect()
        logger.info("Stopping recording...")
        response = self.ws.call(obs_requests.StopRecord())
        return response.getOutputPath()

    def ensure_scene(self, scene_name="BrowserCapture"):
        """Ensures a scene exists for capturing the browser."""
        # This is a simplified version. In reality, setting up sources via script is complex.
        # We assume the user has set up a scene or we just use the current one.
        # Ideally, we would switch to a specific scene.
        try:
            self.ws.call(obs_requests.SetCurrentProgramScene(sceneName=scene_name))
            logger.info(f"Switched to scene: {scene_name}")
        except Exception:
            logger.warning(f"Scene '{scene_name}' not found. Using current scene.")

class BrowserPlayer:
    def __init__(self, headless=True):  # Changed default to True
        self.driver = None
        self.headless = headless

    def start(self):
        # Ensure display is configured correctly for this start attempt
        if self.headless:
            detect_and_set_xvfb()
        else:
            # If not headless, try to keep user session env if it exists
            if not os.environ.get('DISPLAY'):
                detect_and_set_xvfb()
        
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        else:
            # For non-headless, try to support Wayland if detected
            if os.environ.get('WAYLAND_DISPLAY'):
                options.add_argument("--ozone-platform=wayland")
                options.add_argument("--enable-features=UseOzonePlatform")
                logger.info("Enabling Wayland flags for Chromium")
            # If we are in X11 but have no XAUTHORITY, Snap might fail
            if not os.environ.get('XAUTHORITY') and os.path.exists(os.path.expanduser("~/.Xauthority")):
                os.environ['XAUTHORITY'] = os.path.expanduser("~/.Xauthority")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        # Fix for Chromium Snap DevToolsActivePort issue
        options.add_argument("--remote-debugging-port=0")  # Let Chrome pick a free port
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        
        # Optimize for 1080p
        options.add_argument("--window-size=1920,1080")
        
        # Disable GPU to avoid issues in headless mode
        options.add_argument("--disable-gpu")
        
        # Enable autoplay for videos
        options.add_argument("--autoplay-policy=no-user-gesture-required")
        
        # Use a user data dir that Snap has permission to write to
        user_data_dir = os.path.join(os.path.expanduser("~"), "snap/chromium/common/chromedriver-profile")
        os.makedirs(user_data_dir, exist_ok=True)
        options.add_argument(f"--user-data-dir={user_data_dir}")
        logger.info(f"Using Snap-accessible user-data-dir: {user_data_dir}")
        
        # Set Chrome binary location (Chromium snap)
        options.binary_location = "/snap/bin/chromium"
        
        # Log Chromium version and get major version
        major_version = None
        try:
            chromium_v = subprocess.run([options.binary_location, "--version"], capture_output=True, text=True).stdout.strip()
            logger.info(f"Detected Chromium version: {chromium_v}")
            # Extract major version
            match = re.search(r'(\d+)\.', chromium_v)
            if match:
                major_version = match.group(1)
        except Exception as e:
            logger.warning(f"Could not detect Chromium version: {e}")
        
        # Set XAUTHORITY for X11 access
        # If we are in Xvfb, detect_and_set_xvfb already set it.
        # Otherwise try to guess common locations if not set.
        if not os.environ.get('XAUTHORITY'):
            if os.path.exists(os.path.expanduser("~/.Xauthority")):
                os.environ['XAUTHORITY'] = os.path.expanduser("~/.Xauthority")
                logger.info(f"Set XAUTHORITY from home")

        try:
            mode_str = "headless mode" if self.headless else "windowed mode"
            logger.info(f"Starting Chrome WebDriver in {mode_str} (DISPLAY={os.environ.get('DISPLAY', 'not set')})...")
            
            # Set socket timeout
            original_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(60)
            
            # Create service with explicit settings
            from webdriver_manager.core.os_manager import ChromeType
            
            # Force version 143 to match what the Snap browser actually reports
            # despite the CLI saying 144.
            major_version = "143.0.7499.192"
            logger.info(f"Forcing ChromeDriver version: {major_version}")
            
            # Use forced version
            driver_path = ChromeDriverManager(chrome_type=ChromeType.CHROMIUM, driver_version=major_version).install()
            
            service = Service(
                driver_path,
                log_output='/tmp/chromedriver.log',
            )
            
            logger.info(f"Using chromedriver at: {service.path}")
            logger.info(f"Chrome binary: {options.binary_location}")
            
            try:
                # Monkey-patch urllib3's Timeout class to use 30 seconds
                try:
                    from urllib3.util.timeout import Timeout
                    original_init = Timeout.__init__
                    
                    def patched_init(self, total=60, connect=None, read=60, *args, **kwargs):
                        original_init(self, total=total, connect=connect, read=read, *args, **kwargs)
                    
                    Timeout.__init__ = patched_init
                    logger.info("Patched urllib3.Timeout to use 60 second default")
                except Exception as e:
                    logger.warning(f"Could not patch urllib3.Timeout: {e}")
                
                # Create driver directly
                self.driver = webdriver.Chrome(
                    service=service,
                    options=options
                )
                logger.info("Chrome WebDriver created successfully")
            finally:
                # Reset socket timeout
                socket.setdefaulttimeout(original_timeout)
                logger.info(f"Reset socket timeout to {original_timeout}")
            
            # Set page timeouts after driver is created
            self.driver.set_page_load_timeout(30)  # 30 second page load timeout
            self.driver.set_script_timeout(30)     # 30 second script timeout
            logger.info("Chrome WebDriver started successfully")
            
            self.install_ublock()
            
            # Resize window explicitly
            self.driver.set_window_size(1920, 1080)
            logger.info("Browser window resized to 1920x1080")
            
        except Exception as e:
            logger.error(f"Failed to start Chrome WebDriver: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            
            # Log detailed error information
            import traceback
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            
            # Check for common Selenium exceptions
            if hasattr(e, 'msg'):
                logger.error(f"Selenium error message: {e.msg}")
            if hasattr(e, 'stacktrace'):
                logger.error(f"Selenium stacktrace: {e.stacktrace}")
            
            # Check if chromedriver log was created
            if os.path.exists('/tmp/chromedriver.log'):
                try:
                    with open('/tmp/chromedriver.log', 'r') as f:
                        log_content = f.read()
                        logger.error(f"ChromeDriver log content:\n{log_content[-2000:]}")  # Last 2000 chars
                except Exception as log_err:
                    logger.error(f"Could not read chromedriver log: {log_err}")
            else:
                logger.error("ChromeDriver log file was not created at /tmp/chromedriver.log")
            
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
            raise

    def install_ublock(self):
        # Temporarily disabled to avoid complexity with zip/crx in headless Chrome
        # and to focus on stabilizing the core recording flow.
        logger.info("uBlock Origin installation skipped")
        return

    def play_video(self, url, start_time=0):
        if not self.driver:
            logger.info("Driver not initialized, starting now...")
            self.start()
            
        full_url = f"{url}&t={start_time}" if "?" in url else f"{url}?t={start_time}"
        logger.info(f"Navigating to YouTube URL: {full_url}")
        
        try:
            self.driver.get(full_url)
            logger.info("Page navigation initiated")
            
            # Set a fixed window title so OBS can find it easily
            self.driver.execute_script("document.title = 'SupportClipCapture';")
            logger.info("Set window title to: SupportClipCapture")
            
            # Wait for player to load
            logger.info("Waiting for video player to load...")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "movie_player"))
            )
            logger.info("Video player detected")
            
            # Try to force 1080p via JS (optional/flaky)
            # self.driver.execute_script("document.getElementById('movie_player').setPlaybackQualityRange('hd1080', 'hd1080');")
            
            # Hide controls if possible or enter Fullscreen (F key)
            # body = self.driver.find_element(By.TAG_NAME, "body")
            # body.send_keys("f") 
            
            logger.info("Waiting 2 seconds for buffering...")
            time.sleep(2) # Buffer time
            logger.info("Video ready for capture")
            
        except Exception as e:
            logger.error(f"Error navigating to or setting up video player: {e}")
            raise

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

def capture_clip(url, start_time, duration, output_path=None, headless=True):
    """
    Orchestrates the capture process:
    1. Update OBS Browser Source (YoutTubeSource) URL
    2. Start OBS Recording
    3. Wait duration
    4. Stop OBS
    """
    logger.info(f"Starting OBS capture for URL: {url}, start: {start_time}s, duration: {duration}s")
    recorder = OBSRecorder()
    
    try:
        # Use the original URL directly with timestamp as embed conversion might be failing
        # Most YouTube URLs (watch, live, etc.) support the t= seconds parameter.
        t_param = f"t={int(start_time)}s"
        
        if "?" in url:
            full_url = f"{url}&{t_param}"
        else:
            full_url = f"{url}?{t_param}"
            
        # 1. Update OBS internal browser source
        # Aggressive CSS to make the video player fill the entire 1920x1440 area
        custom_css = """
        ytd-app { background: black !important; }
        #masthead-container, #secondary, #comments, #footer, .ytd-merch-shelf-renderer, #chat, #ticket-shelf { display: none !important; }
        .branding-img, .iv-click-target { display: none !important; }
        ytd-watch-flexy { --ytd-watch-flexy-sidebar-width: 0px !important; --ytd-watch-flexy-max-player-width: 100% !important; margin: 0 !important; padding: 0 !important; }
        #primary.ytd-watch-flexy { padding: 0 !important; margin: 0 !important; max-width: none !important; width: 100% !important; }
        #player-container-outer, #player-container-inner, #player-container, #ytd-player { 
            width: 100vw !important; height: 100vh !important; 
            max-width: none !important; max-height: none !important;
            padding: 0 !important; margin: 0 !important;
        }
        #movie_player, .html5-video-container, video { width: 100% !important; height: 100% !important; top: 0 !important; left: 0 !important; }
        ytd-page-manager { margin-top: 0 !important; }
        .ytp-chrome-bottom { opacity: 0 !important; } /* Hide controls voluntarily if they appear */
        """
        logger.info(f"Updating OBS 'YouTubeSource' URL to: {full_url}")
        # Set resolution back to 1920x1080 but with better CSS
        recorder.set_source_settings("YouTubeSource", url=full_url, width=1920, height=1080, css=custom_css)
        
        # Give it a moment to load
        logger.info("Waiting 7 seconds for OBS internal browser to buffer...")
        time.sleep(7)
        
        # 2. Start Recording
        logger.info("Starting OBS recording...")
        recorder.start_recording()
        
        # 3. Wait duration
        logger.info(f"Recording for {duration} seconds...")
        time.sleep(duration)
        
        # 4. Stop Recording
        logger.info("Stopping OBS recording...")
        saved_path = recorder.stop_recording()
        logger.info(f"Clip successfully saved to: {saved_path}")
        
        return saved_path
        
    except Exception as e:
        logger.error(f"Error during OBS capture: {e}")
        logger.error(f"Capture failed at URL: {url}, start: {start_time}s, duration: {duration}s")
        raise
        
    finally:
        logger.info("Cleaning up OBS connections...")
        try:
            recorder.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting from OBS: {e}")
        
        logger.info("Cleanup complete")
