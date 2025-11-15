# Minimal module-level state (only what we need)
_CONFIG = {"discord_webhook_url": None, "discord_alert_webhook_url": None}

def set_config(cfg: dict):
    """Initialize module with minimal values from loaded config (call from main)."""
    global _CONFIG
    if not cfg:
        _CONFIG = {"discord_webhook_url": None, "discord_alert_webhook_url": None}
        return
    _CONFIG = {
        "discord_webhook_url": cfg.get("discord_webhook_url"),
        "discord_alert_webhook_url": cfg.get("discord_alert_webhook_url"),
    }

def _get_webhook_url(is_alert: bool = False):
    if is_alert:
        return _CONFIG.get("discord_alert_webhook_url") or _CONFIG.get("discord_webhook_url")
    return _CONFIG.get("discord_webhook_url")

def _escape_json_str(s: str) -> str:
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    return s

def send_discord_message(message, username="Auto Garden Bot", is_alert=False):
    """
    Send Discord message with aggressive GC and low-memory guard to avoid ENOMEM.
    Returns True on success, False otherwise.
    """
    resp = None
    url = _get_webhook_url(is_alert=is_alert)
    if not url:
        return False

    try:
        # 1) Free heap before TLS
        import gc  # type: ignore
        gc.collect()
        try:
            # If MicroPython provides mem_free, skip send if heap is very low
            if hasattr(gc, "mem_free") and gc.mem_free() < 60000:  # ~60KB threshold
                return False
        except:
            pass

        # 2) Import urequests locally (keeps RAM free when idle)
        import urequests as requests  # type: ignore

        # 3) Keep payload tiny
        url = str(url).strip().strip('\'"')
        content = _escape_json_str(str(message)[:160])
        user = _escape_json_str(str(username)[:40])
        body_bytes = ('{"content":"%s","username":"%s"}' % (content, user)).encode("utf-8")

        # Minimal headers to reduce allocations
        headers = {"Content-Type": "application/json"}

        # 4) Send
        resp = requests.post(url, data=body_bytes, headers=headers)

        status = getattr(resp, "status", getattr(resp, "status_code", None))
        return bool(status and 200 <= status < 300)

    except Exception as e:
        print("Discord webhook exception:", e)
        return False

    finally:
        try:
            if resp:
                resp.close()
        except:
            pass
        # Free refs and force GC
        try:
            del resp, body_bytes
        except:
            pass
        try:
            gc.collect()
        except:
            pass