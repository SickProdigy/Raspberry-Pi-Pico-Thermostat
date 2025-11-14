import network
import time

def connect_wifi(led=None, max_retries=3, timeout=20, config=None):
    """
    Connect to WiFi using credentials from provided config dict.

    Args:
        led: Optional LED pin for visual feedback
        max_retries: Number of connection attempts (default: 3)
        timeout: Seconds to wait for connection per attempt (default: 20)
        config: Dict loaded from config.json, must contain config['wifi'] with 'ssid' and 'password'

    Returns:
        WLAN object if connected, None if failed
    """
    if config is None:
        print("connect_wifi: config is required")
        return None

    wifi_cfg = config.get('wifi') or {}
# support either config['wifi'] = {'ssid','password'} OR top-level 'ssid'/'password'
    ssid = wifi_cfg.get('ssid') or config.get('ssid')
    password = wifi_cfg.get('password') or config.get('password')

    if not ssid or not password:
        print("connect_wifi: missing wifi credentials in config['wifi']")
        return None

    wlan = network.WLAN(network.STA_IF)

    # Ensure clean state
    try:
        if wlan.active():
            wlan.active(False)
            time.sleep(1)

        wlan.active(True)
        time.sleep(1)

    except OSError as e:
        print(f"WiFi activation error: {e}")
        print("Attempting reset...")
        try:
            wlan.deinit()
            time.sleep(2)
            wlan = network.WLAN(network.STA_IF)
            wlan.active(True)
            time.sleep(1)
        except Exception as e2:
            print(f"WiFi reset failed: {e2}")
            return None

    # Try connecting with retries
    for attempt in range(1, max_retries + 1):
        if wlan.isconnected():
            print("Already connected to WiFi")
            break

        print(f'Connecting to WiFi SSID: {ssid} (attempt {attempt}/{max_retries})...')

        try:
            wlan.connect(ssid, password)
        except Exception as e:
            print(f"Connection attempt failed: {e}")
            if attempt < max_retries:
                print("Retrying in 3 seconds...")
                time.sleep(3)
            continue

        # Wait for connection with timeout
        wait_time = 0
        while wait_time < timeout:
            if wlan.isconnected():
                break

            if led:
                try:
                    # some LED wrappers use toggle(), others use on/off
                    if hasattr(led, "toggle"):
                        led.toggle()
                    else:
                        # flash quickly to show activity
                        led.on()
                        time.sleep(0.05)
                        led.off()
                except Exception:
                    pass

            time.sleep(0.5)
            wait_time += 0.5

            # Print progress dots every 2 seconds
            if int(wait_time * 2) % 4 == 0:
                print('.', end='')

        print()  # New line after dots

        if wlan.isconnected():
            break

        print(f'Connection attempt {attempt} failed')
        if attempt < max_retries:
            print("Retrying in 3 seconds...")
            time.sleep(3)

    # Final connection check
    if not wlan.isconnected():
        print('WiFi connection failed after all attempts!')
        if led:
            try:
                # prefer available method names
                if hasattr(led, "off"):
                    led.off()
            except Exception:
                pass
        return None

    # Success feedback
    if led:
        try:
            for _ in range(2):
                led.on()
                time.sleep(0.2)
                led.off()
                time.sleep(0.2)
        except Exception:
            pass

    print('Connected to WiFi successfully!')

    return wlan