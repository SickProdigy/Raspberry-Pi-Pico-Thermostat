# Minimal module-level state (only what we need)
_CONFIG = {"discord_webhook_url": None, "discord_alert_webhook_url": None}
# Cooldown after low-memory failures (epoch seconds)
_NEXT_ALLOWED_SEND_TS = 0

def debug_force_send(message):
    """
    Force one send attempt and print gc.mem_free() at key points.
    Bypasses cooldown and pre-checks so you can measure peak allocations.
    Use from REPL after WiFi connects:
      import scripts.discord_webhook as d
      d.set_config(config)
      d.debug_force_send("memory test")
    WARNING: this can trigger ENOMEM and crash if device free RAM is too low.
    """
    global _NEXT_ALLOWED_SEND_TS
    resp = None
    try:
        import gc  # type: ignore
        import time  # type: ignore

        url = _get_webhook_url(False)
        if not url:
            print("DBG_FORCE: no webhook URL configured")
            return False

        print("DBG_FORCE: mem before gc:", getattr(gc, "mem_free", lambda: 0)() // 1024, "KB")
        gc.collect(); gc.collect()
        print("DBG_FORCE: mem after gc:", getattr(gc, "mem_free", lambda: 0)() // 1024, "KB")

        # Try importing urequests and show mem impact
        try:
            print("DBG_FORCE: importing urequests...")
            import urequests as requests  # type: ignore
            gc.collect()
            print("DBG_FORCE: mem after import:", getattr(gc, "mem_free", lambda: 0)() // 1024, "KB")
        except Exception as e:
            print("DBG_FORCE: urequests import failed:", e)
            return False

        # Build tiny payload
        body_bytes = ('{"content":"%s","username":"%s"}' % (str(message)[:140], "DBG")).encode("utf-8")
        print("DBG_FORCE: mem before post:", getattr(gc, "mem_free", lambda: 0)() // 1024, "KB")

        try:
            resp = requests.post(str(url).strip().strip('\'"'), data=body_bytes, headers={"Content-Type": "application/json"})
            print("DBG_FORCE: mem after post:", getattr(gc, "mem_free", lambda: 0)() // 1024, "KB", "status:", getattr(resp, "status", None))
            status = getattr(resp, "status", getattr(resp, "status_code", None))
            return bool(status and 200 <= status < 300)
        except Exception as e:
            print("DBG_FORCE: exception during post:", e)
            return False

    finally:
        try:
            if resp:
                resp.close()
        except:
            pass
        try:
            if 'requests' in globals():
                del requests
        except:
            pass
        try:
            import sys, gc
            for m in ('urequests', 'ussl', 'ssl'):
                if m in sys.modules:
                    try:
                        del sys.modules[m]
                    except:
                        pass
            gc.collect(); gc.collect()
            try:
                print("DBG_FORCE: mem final:", getattr(gc, "mem_free", lambda: 0)() // 1024, "KB")
            except:
                pass
        except:
            pass

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

        # Quick mem check before importing urequests/SSL
        mem = getattr(gc, "mem_free", lambda: None)()
        # Require larger headroom based on device testing (adjust if you re-test)
        if mem is not None and mem < 150000:
            # quietly skip send when memory is insufficient
            return False

        # Import urequests only when we plan to send
        try:
            import urequests as requests  # type: ignore
        except Exception:
            try:
                _NEXT_ALLOWED_SEND_TS = time.time() + 60
            except:
                pass
            # quiet failure to avoid spamming serial; caller can check return value
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

        resp = requests.post(url, data=body_bytes, headers=headers)

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
        # quiet exception path; return False for caller to handle/backoff
        return False

    finally:
        try:
            if resp:
                resp.close()
        except:
            pass
        # remove local refs and unload heavy modules to free peak RAM (urequests, ussl/ssl)
        try:
            if 'resp' in locals(): del resp
            if 'body_bytes' in locals(): del body_bytes
            if 'content' in locals(): del content
            if 'user' in locals(): del user
            if 'headers' in locals(): del headers
            if 'requests' in locals(): del requests
        except:
            pass
        try:
            import sys
            # remove urequests and SSL modules from module cache so their memory can be reclaimed
            for m in ('urequests', 'ussl', 'ssl'):
                if m in sys.modules:
                    try:
                        del sys.modules[m]
                    except:
                        pass
        except:
            pass
        try:
            import gc
            gc.collect(); gc.collect()
        except:
            pass