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

def send_discord_message(message, username="Auto Garden Bot", is_alert=False):
    """
    Send Discord message with aggressive GC and low-memory guard to avoid ENOMEM.
    Returns True on success, False otherwise.
    """
    global _NEXT_ALLOWED_SEND_TS
    resp = None
    url = _get_webhook_url(is_alert=is_alert)
    if not url:
        return False

    # Respect cooldown if we recently saw ENOMEM
    try:
        import time  # type: ignore
        now = time.time()
        if _NEXT_ALLOWED_SEND_TS and now < _NEXT_ALLOWED_SEND_TS:
            return False
    except:
        pass

    try:
        # 1) Free heap before TLS
        import gc  # type: ignore
        gc.collect()
        gc.collect()  # run twice as a precaution

        # 1b) quick mem check - avoid importing urequests/TLS when too low
        try:
            mem = getattr(gc, "mem_free", lambda: None)()
            # lower threshold to match this board's free heap (~100 KB observed)
            if mem is not None and mem < 90000:
                return False
        except:
            pass

        try:
            # 2) Import urequests locally (keeps RAM free when idle)
            import urequests as requests  # type: ignore
        except Exception as e:
            # import likely failed due to ENOMEM or missing module; back off
            # do not spam full exception text to conserve heap and serial output
            try:
                import time  # type: ignore
                _NEXT_ALLOWED_SEND_TS = time.time() + 60
            except:
                pass
            print("Discord webhook import failed (backing off)")
            return False

        gc.collect()  # collect again after import to reduce fragmentation

        # 3) Keep payload tiny
        url = str(url).strip().strip('\'"')
        content = _escape_json_str(str(message)[:140])  # trim further
        user = _escape_json_str(str(username)[:32])
        body_bytes = ('{"content":"%s","username":"%s"}' % (content, user)).encode("utf-8")

        # Minimal headers to reduce allocations
        headers = {"Content-Type": "application/json"}

        # 4) Send
        resp = requests.post(url, data=body_bytes, headers=headers)

        status = getattr(resp, "status", getattr(resp, "status_code", None))
        return bool(status and 200 <= status < 300)

    except Exception as e:
        # On ENOMEM/MemoryError, back off for longer to avoid repeated failures
        try:
            if ("ENOMEM" in str(e)) or isinstance(e, MemoryError):
                import time  # type: ignore
                _NEXT_ALLOWED_SEND_TS = time.time() + 60
        except:
            pass
        # print concise message only
        print("Discord webhook exception (backing off)")
        return False

    finally:
        try:
            if resp:
                resp.close()
        except:
            pass
        # Free refs and force GC
        try:
            # only delete names if they exist
            if 'resp' in locals():
                del resp
            if 'body_bytes' in locals():
                del body_bytes
            if 'requests' in locals():
                del requests
        except:
            pass
        try:
            gc.collect()
        except:
            pass