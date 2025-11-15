import ujson
# Reload discord module fresh and run the forced debug send once.
try:
    # ensure we use latest module on device
    import sys
    if "scripts.discord_webhook" in sys.modules:
        del sys.modules["scripts.discord_webhook"]
    import scripts.discord_webhook as d
    # load config.json to populate webhook URL
    with open("config.json", "r") as f:
        cfg = ujson.load(f)
    d.set_config(cfg)
    print("Running debug_force_send() — may trigger ENOMEM, run once only")
    d.debug_force_send("memory test")
except Exception as e:
    print("test_send error:", e)