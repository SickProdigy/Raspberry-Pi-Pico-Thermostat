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
            conn.send('Content-Type: text/html\r\n')
            conn.send('Connection: close\r\n\r\n')
            conn.sendall(response)
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
            <title>Auto Garden Status</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <meta http-equiv="refresh" content="10">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                h1 {{
                    color: #2c3e50;
                    text-align: center;
                }}
                .card {{
                    background: white;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 10px 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .temp-display {{
                    font-size: 48px;
                    font-weight: bold;
                    text-align: center;
                    margin: 20px 0;
                }}
                .inside {{ color: #e74c3c; }}
                .outside {{ color: #3498db; }}
                .label {{
                    font-size: 18px;
                    color: #7f8c8d;
                    text-align: center;
                    margin-bottom: 10px;
                }}
                .status {{
                    display: flex;
                    justify-content: space-around;
                    margin-top: 20px;
                }}
                .status-item {{
                    text-align: center;
                }}
                .status-indicator {{
                    font-size: 24px;
                    font-weight: bold;
                    padding: 10px 20px;
                    border-radius: 5px;
                    display: inline-block;
                    margin-top: 10px;
                }}
                .on {{
                    background-color: #2ecc71;
                    color: white;
                }}
                .off {{
                    background-color: #95a5a6;
                    color: white;
                }}
                .footer {{
                    text-align: center;
                    color: #7f8c8d;
                    margin-top: 20px;
                    font-size: 14px;
                }}
                .targets {{
                    font-size: 14px;
                    color: #7f8c8d;
                    text-align: center;
                    margin-top: 10px;
                }}
            </style>
        </head>
        <body>
            <h1>🌱 Auto Garden Status</h1>
            
            <div class="card">
                <div class="label">Inside Temperature</div>
                <div class="temp-display inside">{inside_temp}°F</div>
            </div>
            
            <div class="card">
                <div class="label">Outside Temperature</div>
                <div class="temp-display outside">{outside_temp}°F</div>
            </div>
            
            <div class="card">
                <div class="status">
                    <div class="status-item">
                        <div class="label">❄️ Air Conditioning</div>
                        <div class="status-indicator {ac_class}">{ac_status}</div>
                        <div class="targets">Target: {ac_target}°F ± {ac_swing}°F</div>
                    </div>
                    <div class="status-item">
                        <div class="label">🔥 Heater</div>
                        <div class="status-indicator {heater_class}">{heater_status}</div>
                        <div class="targets">Target: {heater_target}°F ± {heater_swing}°F</div>
                    </div>
                </div>
            </div>
            
            <div class="footer">
                Last updated: {time}<br>
                Auto-refresh every 10 seconds
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