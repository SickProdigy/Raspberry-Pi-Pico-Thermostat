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
    Send Discord message. Import urequests locally to avoid occupying RAM when idle.
    Returns True on success, False otherwise.
    """
    resp = None
    url = _get_webhook_url(is_alert=is_alert)
    if not url:
        return False

    try:
        # local import to save RAM
        import urequests as requests  # type: ignore
        import gc

        url = str(url).strip().strip('\'"')
        content = _escape_json_str(message)
        user = _escape_json_str(username)
        body_bytes = ('{"content":"%s","username":"%s"}' % (content, user)).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}

        resp = requests.post(url, data=body_bytes, headers=headers)

        status = getattr(resp, "status", getattr(resp, "status_code", None))
        success = bool(status and 200 <= status < 300)
        if not success:
            # optional: print status for debugging, but avoid spamming
            print("Discord webhook failed, status:", status)
        return success

    except Exception as e:
        # avoid raising to prevent crashing monitors; print minimal info
        print("Discord webhook exception:", e)
        return False

    finally:
        try:
            if resp:
                resp.close()
        except:
            pass
        # free large objects and modules, then force GC
        try:
            del resp
        except:
            pass
        try:
            gc.collect()
        except:
            pass