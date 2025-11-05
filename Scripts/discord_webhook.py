import urequests as requests
from secrets import secrets

def _escape_json_str(s: str) -> str:
    # minimal JSON string escaper for quotes/backslashes and control chars
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    return s

def send_discord_message(message, username="Auto Garden Bot", is_alert=False):
    resp = None
    
    # Use alert webhook if specified, otherwise normal webhook
    if is_alert:
        url = secrets.get('discord_alert_webhook_url') or secrets.get('discord_webhook_url')
    else:
        url = secrets.get('discord_webhook_url')
    
    try:
        if not url:
            # print("DEBUG: no webhook URL in secrets")
            return False

        url = url.strip().strip('\'"')

        # build JSON by hand so emoji (and other unicode) are preserved as UTF-8 bytes
        content = _escape_json_str(message)
        user = _escape_json_str(username)
        body_bytes = ('{"content":"%s","username":"%s"}' % (content, user)).encode("utf-8")

        headers = {"Content-Type": "application/json; charset=utf-8"}

        resp = requests.post(url, data=body_bytes, headers=headers)

        status = getattr(resp, "status", getattr(resp, "status_code", None))

        if status and 200 <= status < 300:
            # print("Discord message sent")
            return True
        else:
            # print(f"Discord webhook failed with status {status}")
            return False

    except Exception as e:
        # print("Failed to send Discord message:", e)
        return False
    finally:
        if resp:
            try:
                resp.close()
            except:
                pass