import socket
import time

class TempWebServer:
    """Simple web server for viewing temperatures."""
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
            
            # Generate response
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
    
    def _get_status_page(self, sensors, ac_monitor, heater_monitor):
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
        time_str = f"{current_time[0]}-{current_time[1]:02d}-{current_time[2]:02d} {current_time[3]:02d}:{current_time[4]:02d}:{current_time[5]:02d}"
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>🌱 Auto Garden</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <meta http-equiv="refresh" content="10">
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
                }}
            </style>
        </head>
        <body>
            <h1>🌱 Auto Garden Dashboard</h1>
            
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
            </div>
            
            <div class="footer">
                ⏰ Last updated: {time}<br>
                🔄 Auto-refresh every 10 seconds
            </div>
        </body>
        </html>
        """.format(
            inside_temp=f"{inside_temp:.1f}" if isinstance(inside_temp, float) else inside_temp,
            outside_temp=f"{outside_temp:.1f}" if isinstance(outside_temp, float) else outside_temp,
            ac_status=ac_status,
            ac_class="on" if ac_status == "ON" else "off",
            heater_status=heater_status,
            heater_class="on" if heater_status == "ON" else "off",
            ac_target=ac_monitor.target_temp if ac_monitor else "N/A",
            ac_swing=ac_monitor.temp_swing if ac_monitor else "N/A",
            heater_target=heater_monitor.target_temp if heater_monitor else "N/A",
            heater_swing=heater_monitor.temp_swing if heater_monitor else "N/A",
            time=time_str
        )
        return html