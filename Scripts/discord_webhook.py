# Minimal module-level state (only what we need)
_CONFIG = {"discord_webhook_url": None, "discord_alert_webhook_url": None}
# Cooldown after low-memory failures (epoch seconds)
_NEXT_ALLOWED_SEND_TS = 0

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

def send_discord_message(message, username="Auto Garden Bot", is_alert=False, debug: bool = False):
    """
    Send Discord message with aggressive GC and low-memory guard to avoid ENOMEM.
    When debug=True prints mem_free at important steps so you can see peak usage.
    Returns True on success, False otherwise.
    """
    global _NEXT_ALLOWED_SEND_TS
    resp = None
    url = _get_webhook_url(is_alert=is_alert)
    if not url:
        if debug: print("DBG: no webhook URL configured")
        return False

    # Respect cooldown if we recently saw ENOMEM
    try:
        import time  # type: ignore
        now = time.time()
        if _NEXT_ALLOWED_SEND_TS and now < _NEXT_ALLOWED_SEND_TS:
            if debug: print("DBG: backing off until", _NEXT_ALLOWED_SEND_TS)
            return False
    except:
        pass

    try:
        # Lightweight local imports and GC
        import gc  # type: ignore
        import time  # type: ignore

        gc.collect(); gc.collect()
        if debug:
            try: print("DBG: mem after gc:", gc.mem_free() // 1024, "KB")
            except: pass

        # Quick mem check before importing urequests/SSL
        mem = getattr(gc, "mem_free", lambda: None)()
        if debug:
            try: print("DBG: mem before import check:", (mem or 0) // 1024, "KB")
            except: pass

        # Conservative threshold — adjust as needed
        if mem is not None and mem < 90000:
            if debug: print("DBG: skip send (low mem)")
            return False

        # Import urequests only when we plan to send
        try:
            if debug: print("DBG: importing urequests...")
            import urequests as requests  # type: ignore
        except Exception as e:
            # Back off when import fails (likely low-memory)
            try:
                _NEXT_ALLOWED_SEND_TS = time.time() + 60
            except:
                pass
            if debug: print("DBG: urequests import failed:", e)
            print("Discord webhook import failed (backing off)")
            return False

        gc.collect()
        if debug:
            try: print("DBG: mem after import:", gc.mem_free() // 1024, "KB")
            except: pass

        # Build tiny payload
        url = str(url).strip().strip('\'"')
        content = _escape_json_str(str(message)[:140])
        user = _escape_json_str(str(username)[:32])
        body_bytes = ('{"content":"%s","username":"%s"}' % (content, user)).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        if debug:
            try: print("DBG: mem before post:", gc.mem_free() // 1024, "KB")
            except: pass

        resp = requests.post(url, data=body_bytes, headers=headers)

        if debug:
            try: print("DBG: mem after post:", gc.mem_free() // 1024, "KB", "status:", getattr(resp, "status", None))
            except: pass

        status = getattr(resp, "status", getattr(resp, "status_code", None))
        return bool(status and 200 <= status < 300)

    except Exception as e:
        # On ENOMEM/MemoryError back off
        try:
            if ("ENOMEM" in str(e)) or isinstance(e, MemoryError):
                import time  # type: ignore
                _NEXT_ALLOWED_SEND_TS = time.time() + 60
        except:
            pass
        if debug:
            try: print("DBG: exception in send:", e)
            except: pass
        print("Discord webhook exception (backing off)")
        return False

    finally:
        try:
            if resp:
                resp.close()
        except:
            pass
        try:
            # remove large refs and force GC
            if 'resp' in locals(): del resp
            if 'body_bytes' in locals(): del body_bytes
            if 'requests' in locals(): del requests
        except:
            pass
        try:
            import gc as _gc  # type: ignore
            _gc.collect()
        except:
            pass