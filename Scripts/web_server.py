import socket
import time
import json

class TempWebServer:
    """Simple web server for viewing temperatures and adjusting settings."""
    def __init__(self, port=80):
        self.port = port
        self.socket = None
        self.sensors = {}
    
    def start(self):
        """Start the web server (non-blocking)."""
        try:
            self.socket = socket.socket()
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('0.0.0.0', self.port))
            self.socket.listen(1)
            self.socket.setblocking(False)
            print("Web server started on port {}".format(self.port))
        except Exception as e:
            print("Failed to start web server: {}".format(e))
    
    def check_requests(self, sensors, ac_monitor=None, heater_monitor=None, schedule_monitor=None):
        """Check for incoming requests (call in main loop)."""
        if not self.socket:
            return
        
        try:
            conn, addr = self.socket.accept()
            conn.settimeout(3.0)
            request = conn.recv(1024).decode('utf-8')
            
            # Check if this is a POST request (form submission)
            if 'POST /update' in request:
                response = self._handle_update(request, sensors, ac_monitor, heater_monitor, schedule_monitor)
            elif 'POST /schedule' in request:
                response = self._handle_schedule_update(request, sensors, ac_monitor, heater_monitor, schedule_monitor)
            else:
                # Regular GET request
                response = self._get_status_page(sensors, ac_monitor, heater_monitor)
            
            # Make sure we have a valid response
            if response is None:
                print("Error: response is None, generating default page")
                response = self._get_status_page(sensors, ac_monitor, heater_monitor)
            
            conn.send('HTTP/1.1 200 OK\r\n')
            conn.send('Content-Type: text/html; charset=utf-8\r\n')
            conn.send('Connection: close\r\n\r\n')
            conn.sendall(response.encode('utf-8'))
            conn.close()
        except OSError:
            pass
        except Exception as e:
            print("Web server error: {}".format(e))
            import sys
            sys.print_exception(e)
    
    def _save_config_to_file(self, config):
        """Save configuration to config.json file."""
        try:
            with open('config.json', 'w') as f:
                json.dump(config, f)
            print("Settings saved to config.json")
            return True
        except Exception as e:
            print("Error saving config: {}".format(e))
            return False
    
    def _load_config(self):
        """Load configuration from file."""
        try:
            with open('config.json', 'r') as f:
                return json.load(f)
        except:
            return {
                'ac_target': 77.0,
                'ac_swing': 1.0,
                'heater_target': 80.0,
                'heater_swing': 2.0,
                'schedules': [],
                'schedule_enabled': False
            }
    
    def _handle_schedule_update(self, request, sensors, ac_monitor, heater_monitor, schedule_monitor):
        """Handle schedule form submission."""
        try:
            body = request.split('\r\n\r\n')[1] if '\r\n\r\n' in request else ''
            params = {}
            
            for pair in body.split('&'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    params[key] = value.replace('+', ' ')
            
            # Load current config
            config = self._load_config()
            
            # Check if this is a "Resume Schedule" request
            if params.get('resume_schedule') == 'true':
                config['schedule_enabled'] = True
                
                # Save to file
                if self._save_config_to_file(config):
                    print("▶️ Schedule resumed")
                    
                    # Reload schedule monitor
                    if schedule_monitor:
                        schedule_monitor.reload_config(config)
                
                # Send Discord notification
                try:
                    from scripts.discord_webhook import send_discord_message
                    message = "▶️ Schedule resumed - Automatic temperature control active"
                    send_discord_message(message)
                except:
                    pass
                
                return self._get_status_page(sensors, ac_monitor, heater_monitor, show_success=True)
            
            # Otherwise, handle normal schedule update
            # Update schedule enabled status
            config['schedule_enabled'] = params.get('schedule_enabled') == 'on'
            
            # Parse schedules
            schedules = []
            for i in range(4):
                time_key = 'schedule_{}_time'.format(i)
                name_key = 'schedule_{}_name'.format(i)
                ac_key = 'schedule_{}_ac'.format(i)
                heater_key = 'schedule_{}_heater'.format(i)
                
                if time_key in params and params[time_key]:
                    schedule = {
                        'time': params[time_key],
                        'name': params.get(name_key, 'Schedule {}'.format(i+1)),
                        'ac_target': float(params.get(ac_key, 77.0)),
                        'heater_target': float(params.get(heater_key, 80.0))
                    }
                    schedules.append(schedule)
            
            config['schedules'] = schedules
            
            # Save to file
            if self._save_config_to_file(config):
                print("Schedule settings saved")
                
                # Reload schedule monitor config
                if schedule_monitor:
                    schedule_monitor.reload_config(config)
            
            # Send Discord notification
            try:
                from scripts.discord_webhook import send_discord_message
                status = "enabled" if config['schedule_enabled'] else "disabled"
                message = "📅 Schedules updated ({}) - {} schedules configured".format(
                    status, len(schedules)
                )
                send_discord_message(message)
            except:
                pass
                
        except Exception as e:
            print("Error updating schedule: {}".format(e))
            import sys
            sys.print_exception(e)
        
        return self._get_status_page(sensors, ac_monitor, heater_monitor, show_success=True)

    def _handle_update(self, request, sensors, ac_monitor, heater_monitor, schedule_monitor):
        """Handle form submission and update settings."""
        try:
            body = request.split('\r\n\r\n')[1] if '\r\n\r\n' in request else ''
            params = {}
            
            for pair in body.split('&'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    params[key] = float(value)
            
            # Load current config
            config = self._load_config()
            
            # ===== START: Update AC Settings =====
            if 'ac_target' in params and ac_monitor:
                ac_monitor.target_temp = params['ac_target']  # Update monitor
                config['ac_target'] = params['ac_target']      # Update config
                print("AC target updated to {}°F".format(params['ac_target']))
            
            if 'ac_swing' in params and ac_monitor:
                ac_monitor.temp_swing = params['ac_swing']    # Update monitor
                config['ac_swing'] = params['ac_swing']        # Update config
                print("AC swing updated to {}°F".format(params['ac_swing']))
            # ===== END: Update AC Settings =====
            
            # ===== START: Update Heater Settings =====
            if 'heater_target' in params and heater_monitor:
                heater_monitor.target_temp = params['heater_target']  # Update monitor
                config['heater_target'] = params['heater_target']      # Update config
                print("Heater target updated to {}°F".format(params['heater_target']))
            
            if 'heater_swing' in params and heater_monitor:
                heater_monitor.temp_swing = params['heater_swing']    # Update monitor
                config['heater_swing'] = params['heater_swing']        # Update config
                print("Heater swing updated to {}°F".format(params['heater_swing']))
            # ===== END: Update Heater Settings =====
            
            # ===== START: Disable scheduling and enter HOLD mode =====
            if config.get('schedule_enabled'):
                config['schedule_enabled'] = False
                print("⏸️ Schedule disabled - entering HOLD mode")
                
                # Reload schedule monitor to disable it
                if schedule_monitor:
                    schedule_monitor.reload_config(config)
            # ===== END: Disable scheduling and enter HOLD mode =====
            
            # ===== START: Save settings to file =====
            if self._save_config_to_file(config):
                print("Settings persisted to disk")
            # ===== END: Save settings to file =====
            
            # ===== START: Send Discord notification =====
            try:
                from scripts.discord_webhook import send_discord_message
                ac_target_str = str(params.get('ac_target', 'N/A'))
                ac_swing_str = str(params.get('ac_swing', 'N/A'))
                heater_target_str = str(params.get('heater_target', 'N/A'))
                heater_swing_str = str(params.get('heater_swing', 'N/A'))
                
                message = "⏸️ HOLD Mode - Manual override: AC: {}F +/- {}F | Heater: {}F +/- {}F (Schedule disabled)".format(
                    ac_target_str, ac_swing_str, heater_target_str, heater_swing_str
                )
                send_discord_message(message)
            except Exception as discord_error:
                print("Discord notification failed: {}".format(discord_error))
            # ===== END: Send Discord notification =====
            
            # ===== START: Debug output =====
            print("DEBUG: After update, monitor values are:")
            if ac_monitor:
                print("  AC target: {}".format(ac_monitor.target_temp))
                print("  AC swing: {}".format(ac_monitor.temp_swing))
            if heater_monitor:
                print("  Heater target: {}".format(heater_monitor.target_temp))
                print("  Heater swing: {}".format(heater_monitor.temp_swing))
            # ===== END: Debug output =====
            
        except Exception as e:
            print("Error updating settings: {}".format(e))
            import sys
            sys.print_exception(e)
        
        return self._get_status_page(sensors, ac_monitor, heater_monitor, show_success=True)

    def _get_status_page(self, sensors, ac_monitor, heater_monitor, show_success=False):
        """Generate HTML status page."""
        print("DEBUG: Generating status page...")
        try:
            # Get current temperatures
            inside_temps = sensors['inside'].read_all_temps(unit='F')
            outside_temps = sensors['outside'].read_all_temps(unit='F')
            
            inside_temp = list(inside_temps.values())[0] if inside_temps else "N/A"
            outside_temp = list(outside_temps.values())[0] if outside_temps else "N/A"
            
            # Get AC/Heater status
            ac_status = "ON" if ac_monitor and ac_monitor.ac.get_state() else "OFF"
            heater_status = "ON" if heater_monitor and heater_monitor.heater.get_state() else "OFF"
            
            # Get current time
            current_time = time.localtime()
            time_str = "{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                current_time[0], current_time[1], current_time[2], 
                current_time[3], current_time[4], current_time[5]
            )
            
            # Load config
            config = self._load_config()
            
            # **NEW: Check if in HOLD mode**
            is_hold_mode = not config.get('schedule_enabled', False) and len(config.get('schedules', [])) > 0
            
            # Build schedule display
            if is_hold_mode:
                schedule_status = "HOLD MODE"
                schedule_color = "#f39c12"  # Orange color for hold
                schedule_icon = "⏸️"
            elif config.get('schedule_enabled'):
                schedule_status = "ENABLED"
                schedule_color = "#2ecc71"
                schedule_icon = "✅"
            else:
                schedule_status = "DISABLED"
                schedule_color = "#95a5a6"
                schedule_icon = "⚠️"
            
            # Build schedule cards
            schedule_cards = ""
            if config.get('schedules'):
                for schedule in config.get('schedules', []):
                    # ===== START: Decode URL-encoded values =====
                    # Replace %3A with : and + with space
                    time_value = schedule.get('time', 'N/A').replace('%3A', ':')
                    name_value = schedule.get('name', 'Unnamed').replace('+', ' ')
                    # ===== END: Decode URL-encoded values =====
                    
                    schedule_cards += """
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">
                        <div style="font-weight: bold; color: #34495e; margin-bottom: 5px;">
                            🕐 {time} - {name}
                        </div>
                        <div style="color: #7f8c8d; font-size: 14px;">
                            AC: {ac_temp}°F | Heater: {heater_temp}°F
                        </div>
                    </div>
                    """.format(
                        time=schedule.get('time', 'N/A'),
                        name=schedule.get('name', 'Unnamed'),
                        ac_temp=schedule.get('ac_target', 'N/A'),
                        heater_temp=schedule.get('heater_target', 'N/A')
                    )
            else:
                schedule_cards = """
                <div style="text-align: center; color: #95a5a6; grid-column: 1 / -1;">
                    No schedules configured
                </div>
                """
            
            # Build schedule form
            schedule_form = self._build_schedule_form(config)
            
            # Success message
            success_html = """
            <div class="success-message">
                ✅ Settings updated successfully!
            </div>
            """ if show_success else ""
            
            # Format temperature values
            inside_temp_str = "{:.1f}".format(inside_temp) if isinstance(inside_temp, float) else str(inside_temp)
            outside_temp_str = "{:.1f}".format(outside_temp) if isinstance(outside_temp, float) else str(outside_temp)
            
            # ===== START: Add HOLD mode banner =====
            # Check if in HOLD mode (schedules exist but are disabled)
            is_hold_mode = not config.get('schedule_enabled', False) and len(config.get('schedules', [])) > 0
            
            hold_banner = ""
            if is_hold_mode:
                hold_banner = """
                <div style="background: linear-gradient(135deg, #f39c12, #e67e22); color: white; padding: 15px; border-radius: 10px; text-align: center; font-weight: bold; margin-bottom: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.2); animation: fadeIn 0.5s;">
                    ⏸️ HOLD MODE ACTIVE - Manual settings in use (Schedule paused)
                </div>
                """
            # ===== END: Add HOLD mode banner =====
            html = """
<!DOCTYPE html>
<html>
<head>
    <title>🌱 Auto Garden</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="30">
    <meta charset="utf-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        h1 {{
            color: white;
            text-align: center;
            font-size: 36px;
            margin-bottom: 30px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }}
        .temp-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 20px;
        }}
        .card {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.2);
            transition: transform 0.2s;
        }}
        .card:hover {{ transform: translateY(-5px); }}
        .card.full-width {{ margin: 15px 0; }}
        .temp-icon {{ font-size: 64px; text-align: center; margin-bottom: 15px; }}
        .temp-display {{
            font-size: 56px;
            font-weight: bold;
            text-align: center;
            margin: 15px 0;
            font-family: 'Courier New', monospace;
        }}
        .inside {{ color: #e74c3c; text-shadow: 2px 2px 4px rgba(231, 76, 60, 0.3); }}
        .outside {{ color: #3498db; text-shadow: 2px 2px 4px rgba(52, 152, 219, 0.3); }}
        .label {{
            font-size: 20px;
            color: #34495e;
            text-align: center;
            margin-bottom: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .status {{
            display: flex;
            justify-content: space-around;
            margin-top: 20px;
            flex-wrap: wrap;
            gap: 20px;
        }}
        .status-item {{ text-align: center; flex: 1; min-width: 200px; }}
        .status-icon {{ font-size: 48px; margin-bottom: 10px; }}
        .status-indicator {{
            font-size: 22px;
            font-weight: bold;
            padding: 15px 30px;
            border-radius: 25px;
            display: inline-block;
            margin-top: 10px;
            text-transform: uppercase;
            letter-spacing: 2px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            transition: all 0.3s;
        }}
        .status-indicator:hover {{ transform: scale(1.05); }}
        .on {{
            background: linear-gradient(135deg, #2ecc71, #27ae60);
            color: white;
            animation: pulse 2s infinite;
        }}
        .off {{ background: linear-gradient(135deg, #95a5a6, #7f8c8d); color: white; }}
        @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.8; }} }}
        .controls {{
            margin-top: 20px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
        }}
        .control-group {{ margin: 15px 0; }}
        .control-label {{
            display: block;
            font-size: 16px;
            font-weight: 600;
            color: #34495e;
            margin-bottom: 8px;
        }}
        input[type="number"], input[type="time"], input[type="text"] {{
            width: 100%;
            padding: 12px;
            font-size: 18px;
            border: 2px solid #ddd;
            border-radius: 8px;
            transition: border-color 0.3s;
        }}
        input[type="number"]:focus, input[type="time"]:focus, input[type="text"]:focus {{
            outline: none;
            border-color: #667eea;
        }}
        .btn {{
            width: 100%;
            padding: 15px;
            font-size: 18px;
            font-weight: bold;
            color: white;
            background: linear-gradient(135deg, #667eea, #764ba2);
            border: none;
            border-radius: 10px;
            cursor: pointer;
            text-transform: uppercase;
            letter-spacing: 1px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            transition: transform 0.2s;
        }}
        .btn:hover {{ transform: translateY(-2px); }}
        .btn:active {{ transform: translateY(0); }}
        .success-message {{
            background: #2ecc71;
            color: white;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            font-weight: bold;
            margin-bottom: 20px;
            animation: fadeIn 0.5s;
        }}
        @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
        .footer {{
            text-align: center;
            color: white;
            margin-top: 30px;
            font-size: 14px;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
        }}
        .targets {{
            font-size: 15px;
            color: #7f8c8d;
            text-align: center;
            margin-top: 12px;
            font-weight: 500;
        }}
        .degree {{ font-size: 0.6em; vertical-align: super; }}
        .schedule-row {{
            display: grid;
            grid-template-columns: 1fr 2fr 1fr 1fr;
            gap: 10px;
            margin-bottom: 15px;
            padding: 15px;
            background: white;
            border-radius: 8px;
        }}
        .toggle-switch {{
            position: relative;
            display: inline-block;
            width: 60px;
            height: 34px;
        }}
        .toggle-switch input {{ opacity: 0; width: 0; height: 0; }}
        .slider {{
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            transition: .4s;
            border-radius: 34px;
        }}
        .slider:before {{
            position: absolute;
            content: "";
            height: 26px;
            width: 26px;
            left: 4px;
            bottom: 4px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }}
        input:checked + .slider {{ background-color: #2ecc71; }}
        input:checked + .slider:before {{ transform: translateX(26px); }}
        @media (max-width: 768px) {{
            .temp-grid {{ grid-template-columns: 1fr; }}
            .status {{ flex-direction: column; }}
            .schedule-row {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <h1>🌱 Auto Garden Dashboard</h1>
    
    {hold_banner}
    {success_message}
    
    <div class="temp-grid">
        <div class="card temp-card">
            <div class="temp-icon">🏠</div>
            <div class="label">Indoor Climate</div>
            <div class="temp-display inside">{inside_temp}<span class="degree">°F</span></div>
        </div>
        
        <div class="card temp-card">
            <div class="temp-icon">🌤️</div>
            <div class="label">Outdoor Climate</div>
            <div class="temp-display outside">{outside_temp}<span class="degree">°F</span></div>
        </div>
    </div>
    
    <div class="card full-width">
        <div class="status">
            <div class="status-item">
                <div class="status-icon">❄️</div>
                <div class="label">Air Conditioning</div>
                <div class="status-indicator {ac_class}">{ac_status}</div>
                <div class="targets">Target: {ac_target}°F ± {ac_swing}°F</div>
            </div>
            <div class="status-item">
                <div class="status-icon">🔥</div>
                <div class="label">Heating System</div>
                <div class="status-indicator {heater_class}">{heater_status}</div>
                <div class="targets">Target: {heater_target}°F ± {heater_swing}°F</div>
            </div>
        </div>
        
        <form method="POST" action="/update" class="controls">
            <h2 style="text-align: center; color: #34495e; margin-bottom: 20px;">⚙️ Adjust Settings</h2>
            
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px;">
                <div>
                    <div class="control-group">
                        <label class="control-label">❄️ AC Target (°F)</label>
                        <input type="number" name="ac_target" value="{ac_target}" step="0.5" min="60" max="85">
                    </div>
                    <div class="control-group">
                        <label class="control-label">❄️ AC Swing (°F)</label>
                        <input type="number" name="ac_swing" value="{ac_swing}" step="0.5" min="0.5" max="5">
                    </div>
                </div>
                
                <div>
                    <div class="control-group">
                        <label class="control-label">🔥 Heater Target (°F)</label>
                        <input type="number" name="heater_target" value="{heater_target}" step="0.5" min="60" max="85">
                    </div>
                    <div class="control-group">
                        <label class="control-label">🔥 Heater Swing (°F)</label>
                        <input type="number" name="heater_swing" value="{heater_swing}" step="0.5" min="0.5" max="5">
                    </div>
                </div>
            </div>
            
            <div class="control-group" style="margin-top: 20px;">
                <button type="submit" class="btn">💾 Save Settings</button>
            </div>
        </form>
    </div>
    
    <div class="card full-width">
        <h2 style="text-align: center; color: #34495e; margin-bottom: 20px;">📅 Daily Schedule</h2>
        <div style="text-align: center; margin-bottom: 15px;">
            <strong>Status:</strong> 
            <span style="color: {schedule_color}; font-weight: bold;">
                {schedule_status} {schedule_icon}
            </span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px;">
            {schedule_cards}
        </div>
        {schedule_form}
    </div>
    
    <div class="footer">
        ⏰ Last updated: {time}<br>
        🔄 Auto-refresh every 30 seconds
    </div>
</body>
</html>
            """.format(
                hold_banner=hold_banner,
                success_message=success_html,
                inside_temp=inside_temp_str,
                outside_temp=outside_temp_str,
                ac_status=ac_status,
                ac_class="on" if ac_status == "ON" else "off",
                heater_status=heater_status,
                heater_class="on" if heater_status == "ON" else "off",
                ac_target=ac_monitor.target_temp if ac_monitor else "N/A",
                ac_swing=ac_monitor.temp_swing if ac_monitor else "N/A",
                heater_target=heater_monitor.target_temp if heater_monitor else "N/A",
                heater_swing=heater_monitor.temp_swing if heater_monitor else "N/A",
                time=time_str,
                schedule_status=schedule_status,
                schedule_color=schedule_color,
                schedule_icon=schedule_icon,
                schedule_cards=schedule_cards,
                schedule_form=schedule_form
            )
            return html
            
        except Exception as e:
            print("Error generating page: {}".format(e))
            import sys
            sys.print_exception(e)
            return "<html><body><h1>Error loading page</h1><pre>{}</pre></body></html>".format(str(e))
    
    def _build_schedule_form(self, config):
        """Build the schedule editing form."""
        schedules = config.get('schedules', [])
        
        # Pad with empty schedules up to 4
        while len(schedules) < 4:
            schedules.append({'time': '', 'name': '', 'ac_target': 77.0, 'heater_target': 80.0})
        
        enabled_checked = 'checked' if config.get('schedule_enabled') else ''
        
        # Check if in HOLD mode
        is_hold_mode = not config.get('schedule_enabled', False) and len(config.get('schedules', [])) > 0
        
        # Build header with toggle or resume button
        if is_hold_mode:
            # Show Resume Schedule button instead of toggle
            header = """
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h3 style="color: #34495e; margin: 0;">⚙️ Edit Schedules</h3>
                <button type="submit" name="resume_schedule" value="true" style="padding: 10px 20px; background: linear-gradient(135deg, #2ecc71, #27ae60); color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.2); transition: transform 0.2s;">
                    ▶️ Resume Schedule
                </button>
            </div>
            """
        else:
            # Show toggle switch for enable/disable
            header = """
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h3 style="color: #34495e; margin: 0;">⚙️ Edit Schedules</h3>
                <label class="toggle-switch">
                    <input type="checkbox" name="schedule_enabled" {enabled_checked}>
                    <span class="slider"></span>
                </label>
            </div>
            """.format(enabled_checked=enabled_checked)
        
        form = """
        <form method="POST" action="/schedule" class="controls" style="margin-top: 20px;">
            {header}
        """.format(header=header)
        
        for i, schedule in enumerate(schedules[:4]):
            form += """
            <div class="schedule-row">
                <div class="control-group" style="margin: 0;">
                    <label class="control-label" style="font-size: 14px;">Time</label>
                    <input type="time" name="schedule_{i}_time" value="{time}">
                </div>
                <div class="control-group" style="margin: 0;">
                    <label class="control-label" style="font-size: 14px;">Name</label>
                    <input type="text" name="schedule_{i}_name" value="{name}" placeholder="e.g. Morning">
                </div>
                <div class="control-group" style="margin: 0;">
                    <label class="control-label" style="font-size: 14px;">AC (°F)</label>
                    <input type="number" name="schedule_{i}_ac" value="{ac}" step="0.5" min="60" max="85">
                </div>
                <div class="control-group" style="margin: 0;">
                    <label class="control-label" style="font-size: 14px;">Heater (°F)</label>
                    <input type="number" name="schedule_{i}_heater" value="{heater}" step="0.5" min="60" max="85">
                </div>
            </div>
            """.format(
                i=i,
                time=schedule.get('time', ''),
                name=schedule.get('name', ''),
                ac=schedule.get('ac_target', 77.0),
                heater=schedule.get('heater_target', 80.0)
            )
        
        form += """
            <div class="control-group" style="margin-top: 20px;">
                <button type="submit" class="btn">💾 Save Schedule</button>
            </div>
        </form>
        """
        
        return form