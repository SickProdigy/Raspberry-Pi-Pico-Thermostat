import socket
import time

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
            self.socket.setblocking(False)  # Non-blocking mode
            print(f"Web server started on port {self.port}")
        except Exception as e:
            print(f"Failed to start web server: {e}")
    
    def check_requests(self, sensors, ac_monitor=None, heater_monitor=None):
        """Check for incoming requests (call in main loop)."""
        if not self.socket:
            return
        
        try:
            conn, addr = self.socket.accept()
            conn.settimeout(3.0)
            request = conn.recv(1024).decode('utf-8')
            
            # Check if this is a POST request (form submission)
            if 'POST /update' in request:
                response = self._handle_update(request, sensors, ac_monitor, heater_monitor)
            else:
                # Regular GET request
                response = self._get_status_page(sensors, ac_monitor, heater_monitor)
            
            conn.send('HTTP/1.1 200 OK\r\n')
            conn.send('Content-Type: text/html; charset=utf-8\r\n')
            conn.send('Connection: close\r\n\r\n')
            conn.sendall(response.encode('utf-8'))
            conn.close()
        except OSError:
            pass  # No connection, continue
        except Exception as e:
            print(f"Web server error: {e}")
    
    def _save_config_to_file(self, ac_monitor, heater_monitor):
        """Save current settings to config.json file."""
        try:
            import json
            config = {
                'ac_target': ac_monitor.target_temp,
                'ac_swing': ac_monitor.temp_swing,
                'heater_target': heater_monitor.target_temp,
                'heater_swing': heater_monitor.temp_swing
            }
            with open('config.json', 'w') as f:
                json.dump(config, f)
            print("Settings saved to config.json")
            return True
        except Exception as e:
            print("Error saving config: {}".format(e))
            return False
    
    def _handle_update(self, request, sensors, ac_monitor, heater_monitor):
        """Handle form submission and update settings."""
        try:
            # Extract form data from POST body
            body = request.split('\r\n\r\n')[1] if '\r\n\r\n' in request else ''
            params = {}
            
            for pair in body.split('&'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    params[key] = float(value)
            
            # Update AC settings
            if 'ac_target' in params and ac_monitor:
                ac_monitor.target_temp = params['ac_target']
                print("AC target updated to {}°F".format(params['ac_target']))
            
            if 'ac_swing' in params and ac_monitor:
                ac_monitor.temp_swing = params['ac_swing']
                print("AC swing updated to {}°F".format(params['ac_swing']))
            
            # Update heater settings
            if 'heater_target' in params and heater_monitor:
                heater_monitor.target_temp = params['heater_target']
                print("Heater target updated to {}°F".format(params['heater_target']))
            
            if 'heater_swing' in params and heater_monitor:
                heater_monitor.temp_swing = params['heater_swing']
                print("Heater swing updated to {}°F".format(params['heater_swing']))
            
            # Save settings to file
            if self._save_config_to_file(ac_monitor, heater_monitor):
                print("Settings persisted to disk")
            
            # Send Discord notification
            from scripts.discord_webhook import send_discord_message
            ac_target_str = str(params.get('ac_target', 'N/A'))
            ac_swing_str = str(params.get('ac_swing', 'N/A'))
            heater_target_str = str(params.get('heater_target', 'N/A'))
            heater_swing_str = str(params.get('heater_swing', 'N/A'))
            
            message = "Settings Updated - AC: {}F +/- {}F | Heater: {}F +/- {}F".format(
                ac_target_str, ac_swing_str, heater_target_str, heater_swing_str
            )
            send_discord_message(message)
            
        except Exception as e:
            print("Error updating settings: {}".format(e))
        
        # Return updated page
        return self._get_status_page(sensors, ac_monitor, heater_monitor, show_success=True)
    
    def _get_status_page(self, sensors, ac_monitor, heater_monitor, show_success=False):
        """Generate HTML status page."""
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
        
        # Load config to show schedules
        try:
            import json
            with open('config.json', 'r') as f:
                config = json.load(f)
        except:
            config = {'schedules': [], 'schedule_enabled': False}
        
        # Build schedule display
        schedule_status = "ENABLED ✅" if config.get('schedule_enabled') else "DISABLED ⚠️"
        
        if config.get('schedules'):
            schedule_cards = ""
            for schedule in config.get('schedules', []):
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
        
        # Success message
        success_html = """
        <div class="success-message">
            ✅ Settings updated successfully!
        </div>
        """ if show_success else ""
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>🌱 Auto Garden</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <meta http-equiv="refresh" content="30">
            <meta charset="utf-8">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
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
                .card:hover {{
                    transform: translateY(-5px);
                }}
                .card.full-width {{
                    margin: 15px 0;
                }}
                .temp-card {{
                    position: relative;
                    overflow: hidden;
                }}
                .temp-icon {{
                    font-size: 64px;
                    text-align: center;
                    margin-bottom: 15px;
                }}
                .temp-display {{
                    font-size: 56px;
                    font-weight: bold;
                    text-align: center;
                    margin: 15px 0;
                    font-family: 'Courier New', monospace;
                }}
                .inside {{ 
                    color: #e74c3c;
                    text-shadow: 2px 2px 4px rgba(231, 76, 60, 0.3);
                }}
                .outside {{ 
                    color: #3498db;
                    text-shadow: 2px 2px 4px rgba(52, 152, 219, 0.3);
                }}
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
                .status-item {{
                    text-align: center;
                    flex: 1;
                    min-width: 200px;
                }}
                .status-icon {{
                    font-size: 48px;
                    margin-bottom: 10px;
                }}
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
                .status-indicator:hover {{
                    transform: scale(1.05);
                }}
                .on {{
                    background: linear-gradient(135deg, #2ecc71, #27ae60);
                    color: white;
                    animation: pulse 2s infinite;
                }}
                .off {{
                    background: linear-gradient(135deg, #95a5a6, #7f8c8d);
                    color: white;
                }}
                @keyframes pulse {{
                    0%, 100% {{ opacity: 1; }}
                    50% {{ opacity: 0.8; }}
                }}
                .controls {{
                    margin-top: 20px;
                    padding: 20px;
                    background: #f8f9fa;
                    border-radius: 10px;
                }}
                .control-group {{
                    margin: 15px 0;
                }}
                .control-label {{
                    display: block;
                    font-size: 16px;
                    font-weight: 600;
                    color: #34495e;
                    margin-bottom: 8px;
                }}
                input[type="number"] {{
                    width: 100%;
                    padding: 12px;
                    font-size: 18px;
                    border: 2px solid #ddd;
                    border-radius: 8px;
                    transition: border-color 0.3s;
                }}
                input[type="number"]:focus {{
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
                .btn:hover {{
                    transform: translateY(-2px);
                }}
                .btn:active {{
                    transform: translateY(0);
                }}
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
                @keyframes fadeIn {{
                    from {{ opacity: 0; }}
                    to {{ opacity: 1; }}
                }}
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
                .degree {{
                    font-size: 0.6em;
                    vertical-align: super;
                }}
                @media (max-width: 768px) {{
                    .temp-grid {{
                        grid-template-columns: 1fr;
                    }}
                    .status {{
                        flex-direction: column;
                    }}
                }}
            </style>
        </head>
        <body>
            <h1>🌱 Auto Garden Dashboard</h1>
            
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
                        {schedule_status}
                    </span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                    {schedule_cards}
                </div>
            </div>
            
            <div class="footer">
                ⏰ Last updated: {time}<br>
                🔄 Auto-refresh every 30 seconds
            </div>
        </body>
        </html>
        """.format(
            success_message=success_html,
            inside_temp="{:.1f}".format(inside_temp) if isinstance(inside_temp, float) else inside_temp,
            outside_temp="{:.1f}".format(outside_temp) if isinstance(outside_temp, float) else outside_temp,
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
            schedule_color="#2ecc71" if config.get('schedule_enabled') else "#95a5a6",
            schedule_cards=schedule_cards
        )
        return html