import socket
import time # type: ignore
import json
import scripts.discord_webhook as discord_webhook
import os


class TempWebServer:
    """Simple web server for viewing temperatures and adjusting settings."""
    def __init__(self, port=80):
        self.port = port
        self.socket = None
        self.sensors = {}
        self.last_page_render = 0  # Track last successful HTML generation

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

    def check_requests(self, sensors, ac_monitor, heater_monitor, schedule_monitor, config):
        """Check for incoming requests (call in main loop)."""
        if not self.socket:
            return
        try:
            conn, addr = self.socket.accept()
            conn.settimeout(3.0)
            
            # Read request headers first (in chunks to avoid truncation)
            request_bytes = b''
            while b'\r\n\r\n' not in request_bytes:
                chunk = conn.recv(512)
                if not chunk:
                    break
                request_bytes += chunk
                if len(request_bytes) > 4096:  # Safety limit
                    break
            
            # Parse Content-Length from headers
            request = request_bytes.decode('utf-8')
            content_length = 0
            if 'Content-Length:' in request:
                for line in request.split('\r\n'):
                    if line.lower().startswith('content-length:'):
                        content_length = int(line.split(':')[1].strip())
                        break
            
                        # If POST request with body, read remaining data
            if 'POST' in request and content_length > 0:
                # Check how much body we already have
                header_end = request.find('\r\n\r\n') + 4
                body_so_far = request[header_end:]
                bytes_read = len(body_so_far.encode('utf-8'))
                bytes_needed = content_length - bytes_read
                
                # ===== DEBUG: Print body reading info =====
                print("DEBUG POST: Content-Length = {} bytes".format(content_length))
                print("DEBUG POST: Already read = {} bytes".format(bytes_read))
                print("DEBUG POST: Still need = {} bytes".format(bytes_needed))
                # ===== END DEBUG =====
                
                # Read remaining body in loop (recv() may not return all at once!)
                if bytes_needed > 0:
                    remaining_parts = []
                    total_read = 0
                    
                    # Keep reading until we have all bytes
                    while total_read < bytes_needed:
                        chunk = conn.recv(min(512, bytes_needed - total_read))
                        if not chunk:
                            print("WARNING: Connection closed before all data received!")
                            break
                        remaining_parts.append(chunk)
                        total_read += len(chunk)
                        print("DEBUG POST: Read {} bytes (total: {}/{})".format(
                            len(chunk), total_read, bytes_needed))
                    
                    remaining = b''.join(remaining_parts)
                    print("DEBUG POST: Read additional {} bytes (expected {})".format(
                        len(remaining), bytes_needed))
                    request = request[:header_end] + body_so_far + remaining.decode('utf-8')
                
                # ===== DEBUG: Print final body length =====
                final_body = request[header_end:]
                print("DEBUG POST: Final body length = {} bytes (expected {})".format(
                    len(final_body), content_length))
                print("DEBUG POST: First 100 chars = {}".format(final_body[:100]))
                # ===== END DEBUG =====

            if 'POST /update' in request:
                response = self._handle_update(request, sensors, ac_monitor, heater_monitor, schedule_monitor, config)
                # If error page redirects, handle it
                if isinstance(response, str) and response.startswith('HTTP/1.1'):
                    print("DEBUG: Sending redirect from /update ({} bytes)".format(len(response)))
                    conn.sendall(response.encode('utf-8'))
                    conn.close()
                    print("DEBUG: Redirect sent, connection closed")
                    return

            elif 'GET /schedule' in request:
                response = self._get_schedule_editor_page(sensors, ac_monitor, heater_monitor)
                response_bytes = response.encode('utf-8')
                
                # Send headers
                conn.sendall(b'HTTP/1.1 200 OK\r\n')
                conn.sendall(b'Content-Type: text/html; charset=utf-8\r\n')
                conn.send('Content-Length: {}\r\n'.format(len(response_bytes)))
                conn.send('Connection: close\r\n')
                conn.send('\r\n')
                
                # Send body in chunks (MicroPython has small socket buffer)
                chunk_size = 1024  # Send 1KB at a time
                for i in range(0, len(response_bytes), chunk_size):
                    chunk = response_bytes[i:i+chunk_size]
                    conn.send(chunk)
                    print("DEBUG: Sent chunk {} ({} bytes)".format(i//chunk_size + 1, len(chunk)))
                
                conn.close()
                print("DEBUG: Schedule editor page sent successfully ({} bytes total)".format(len(response_bytes)))
                return

            elif 'GET /settings' in request:
                response = self._get_settings_page(sensors, ac_monitor, heater_monitor)
                response_bytes = response.encode('utf-8')
                
                conn.send('HTTP/1.1 200 OK\r\n')
                conn.send('Content-Type: text/html; charset=utf-8\r\n')
                conn.send('Content-Length: {}\r\n'.format(len(response_bytes)))
                conn.send('Connection: close\r\n')
                conn.send('\r\n')
                
                chunk_size = 1024
                for i in range(0, len(response_bytes), chunk_size):
                    chunk = response_bytes[i:i+chunk_size]
                    conn.send(chunk)
                
                conn.close()
                print("DEBUG: Settings page sent successfully ({} bytes total)".format(len(response_bytes)))
                return
            
            elif 'POST /settings' in request:
                response = self._handle_settings_update(request, sensors, ac_monitor, heater_monitor, schedule_monitor, config)
                if isinstance(response, str) and response.startswith('HTTP/1.1'):
                    conn.sendall(response.encode('utf-8'))
                    conn.close()
                    print("DEBUG: Settings update redirect sent")
                    return

            elif 'POST /schedule' in request:
                response = self._handle_schedule_update(request, sensors, ac_monitor, heater_monitor, schedule_monitor, config)
                # Redirects are already complete HTTP responses, send directly
                if isinstance(response, str) and response.startswith('HTTP/1.1'):
                    print("DEBUG: Sending redirect ({} bytes)".format(len(response)))
                    conn.sendall(response.encode('utf-8'))
                    conn.close()
                    print("DEBUG: Redirect sent, connection closed")
                    return

            elif 'GET /ping' in request:
                # Quick health check endpoint (no processing)
                conn.send('HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n')
                conn.sendall(b'OK')
                conn.close()
                return

            else:
                response = self._get_status_page(sensors, ac_monitor, heater_monitor, schedule_monitor)

            if response is None:
                response = self._get_status_page(sensors, ac_monitor, heater_monitor, schedule_monitor)
            
            # ===== START: Send response with proper HTTP headers =====
            print("DEBUG: Sending response ({} bytes)".format(len(response)))
            try:
                # Check if response already has HTTP headers (like redirects)
                if response.startswith('HTTP/1.1'):
                    # Response already has headers (redirect or other), send as-is
                    conn.sendall(response.encode('utf-8'))
                else:
                    # HTML response needs headers added first
                    conn.send(b'HTTP/1.1 200 OK\r\n')
                    conn.send(b'Content-Type: text/html; charset=utf-8\r\n')
                    conn.send('Content-Length: {}\r\n'.format(len(response.encode('utf-8'))).encode('utf-8'))
                    conn.send(b'Connection: close\r\n')
                    conn.send(b'\r\n')  # Blank line separates headers from body
                    conn.sendall(response.encode('utf-8'))
                
                print("DEBUG: Response sent successfully")
            except Exception as e:
                print("ERROR: Failed to send response: {}".format(e))
            finally:
                conn.close()
                print("DEBUG: Client connection closed")
            # ===== END: Send response =====

        except OSError:
            pass
        except Exception as e:
            print("Web server error: {}".format(e))
            import sys
            sys.print_exception(e)

    def _save_config_to_file(self, config):
        """Save configuration to config.json file (atomic write)."""
        try:
            import os
            
            print("DEBUG: Saving config with {} schedules".format(len(config.get('schedules', []))))
            
            # Write to temp file first
            with open('config.tmp', 'w') as f:
                json.dump(config, f)
            
            # Remove old config if exists
            try:
                os.remove('config.json')
            except:
                pass
            
            # Rename temp to config (atomic on most filesystems)
            os.rename('config.tmp', 'config.json')
            
            # Update discord module in-memory config so webhook URLs are current
            try:
                discord_webhook.set_config(config)
            except Exception:
                pass
    
            print("Settings saved to config.json")
            return True
        except Exception as e:
            print("❌ Error saving config: {}".format(e))
            import sys
            sys.print_exception(e)
            return False

    def _load_config(self):
        """Load configuration from file."""
        try:
            with open('config.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            print("Error loading config:", e)
            raise  # Or handle as appropriate

    def _handle_schedule_update(self, request, sensors, ac_monitor, heater_monitor, schedule_monitor, config):
        """Handle schedule form submission."""

        try:
            body = request.split('\r\n\r\n')[1] if '\r\n\r\n' in request else ''
            params = {}
            
            for pair in body.split('&'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    params[key] = value.replace('+', ' ')
            
            # ===== START: Handle mode actions =====
            mode_action = params.get('mode_action', '')
            
            if mode_action == 'resume':
                # Resume automatic scheduling
                config['schedule_enabled'] = True
                config['permanent_hold'] = False
                
                if self._save_config_to_file(config):
                    print("▶️ Schedule resumed - Automatic mode")
            
                    if schedule_monitor:
                        schedule_monitor.reload_config(config)
                        # ===== IMMEDIATELY APPLY ACTIVE SCHEDULE =====
                        active_schedule = schedule_monitor._find_active_schedule()
                        if active_schedule:
                            schedule_monitor._apply_schedule(active_schedule)
                            print("✅ Active schedule applied immediately after resume: {}".format(
                                active_schedule.get('name', 'Unnamed')
                            ))
                
                # Send Discord notification
                try:
                    discord_webhook.send_discord_message("▶️ Schedule resumed - Automatic temperature control active")
                except:
                    pass
                
                # Redirect back to Dashboard with proper headers
                redirect_response = 'HTTP/1.1 303 See Other\r\n'
                redirect_response += 'Location: /\r\n'
                redirect_response += 'Content-Length: 0\r\n'
                redirect_response += 'Connection: close\r\n'
                redirect_response += '\r\n'
                print("DEBUG: Returning redirect to dashboard")
                return redirect_response
            
            elif mode_action == 'temporary_hold':
                # Enter temporary hold (pause schedules temporarily)
                config['schedule_enabled'] = False
                config['permanent_hold'] = False
                
                if self._save_config_to_file(config):
                    print("⏸️ Temporary hold activated")
                    
                    if schedule_monitor:
                        schedule_monitor.reload_config(config)
                
                try:
                    discord_webhook.send_discord_message("⏸️ Temporary hold - Schedules paused, manual control active")
                except:
                    pass
                
                # Redirect to dashboard after error (settings weren't saved)
                redirect_response = 'HTTP/1.1 303 See Other\r\n'
                redirect_response += 'Location: /\r\n'
                redirect_response += 'Content-Length: 0\r\n'
                redirect_response += 'Connection: close\r\n'
                redirect_response += '\r\n'
                return redirect_response
            
            elif mode_action == 'permanent_hold':
                # Enter permanent hold (disable schedules permanently)
                config['schedule_enabled'] = False
                config['permanent_hold'] = True
                
                if self._save_config_to_file(config):
                    print("🛑 Permanent hold activated")
                    
                    if schedule_monitor:
                        schedule_monitor.reload_config(config)
                
                try:
                    discord_webhook.send_discord_message("🛑 Permanent hold - Schedules disabled, manual control only")
                except:
                    pass
                
                # Redirect back to Dashboard with proper headers
                redirect_response = 'HTTP/1.1 303 See Other\r\n'
                redirect_response += 'Location: /\r\n'
                redirect_response += 'Content-Length: 0\r\n'
                redirect_response += 'Connection: close\r\n'
                redirect_response += '\r\n'
                print("DEBUG: Returning redirect to dashboard")
                return redirect_response
            
            elif mode_action == 'save_schedules':
                # Just fall through to schedule parsing below
                pass
            # ===== END: Handle mode actions =====
            
            # ===== START: Handle schedule configuration save =====
            # DEBUG: Print what we received
            print("DEBUG: Received POST body parameters:")
            for key, value in params.items():
                print("  {} = '{}'".format(key, value))
            print("DEBUG: Total params received: {}".format(len(params)))
            
            # Parse schedules (4 slots)
            schedules = []
            has_any_schedule_data = False
            
            for i in range(4):
                time_key = 'schedule_{}_time'.format(i)
                name_key = 'schedule_{}_name'.format(i)
                ac_key = 'schedule_{}_ac'.format(i)
                heater_key = 'schedule_{}_heater'.format(i)
                
                # Check if this schedule slot has data
                if time_key in params or name_key in params or ac_key in params or heater_key in params:
                    has_any_schedule_data = True
                
                if time_key in params and params[time_key]:
                    # ===== VALIDATE: If time is set, AC and Heater MUST be set =====
                    if ac_key not in params or not params[ac_key]:
                        print("❌ Validation failed: Schedule {} has time but missing AC target".format(i+1))
                        return self._get_error_page(
                            "Incomplete Schedule",
                            "Schedule {}: AC target is required when time is set".format(i+1),
                            sensors, ac_monitor, heater_monitor
                        )
                    
                    if heater_key not in params or not params[heater_key]:
                        print("❌ Validation failed: Schedule {} has time but missing Heater target".format(i+1))
                        return self._get_error_page(
                            "Incomplete Schedule",
                            "Schedule {}: Heater target is required when time is set".format(i+1),
                            sensors, ac_monitor, heater_monitor
                        )
                    # ===== END VALIDATION =====
                    
                    # URL decode the time (converts %3A back to :)
                    schedule_time = params[time_key].replace('%3A', ':')
                    
                    # Validate time format
                    if ':' not in schedule_time or len(schedule_time.split(':')) != 2:
                        print("Invalid time format: {}".format(schedule_time))
                        return self._get_error_page(
                            "Invalid Time",
                            "Schedule {}: Time format must be HH:MM".format(i+1),
                            sensors, ac_monitor, heater_monitor
                        )
                    
                    try:
                        hours, mins = schedule_time.split(':')
                        if not (0 <= int(hours) <= 23 and 0 <= int(mins) <= 59):
                            raise ValueError
                    except:
                        print("Invalid time value: {}".format(schedule_time))
                        return self._get_error_page(
                            "Invalid Time",
                            "Schedule {}: Invalid time value {}".format(i+1, schedule_time),
                            sensors, ac_monitor, heater_monitor
                        )
                    
                    # URL decode the name
                    schedule_name = params.get(name_key, 'Schedule {}'.format(i+1)).replace('+', ' ')
                    
                    # Parse temperatures (they're guaranteed to exist due to validation above)
                    try:
                        ac_target = float(params[ac_key])
                        heater_target = float(params[heater_key])
                    except (ValueError, TypeError):
                        return self._get_error_page(
                            "Invalid Temperature",
                            "Schedule {}: Temperature values must be numbers".format(i+1),
                            sensors, ac_monitor, heater_monitor
                        )
                    
                    # Create schedule entry
                    schedule = {
                        'time': schedule_time,
                        'name': schedule_name,
                        'ac_target': ac_target,
                        'heater_target': heater_target
                    }
                    schedules.append(schedule)
                    print("DEBUG: Parsed schedule {}: time='{}', name='{}', heater={}, ac={}".format(
                        i, schedule_time, schedule_name, heater_target, ac_target))
            
            # Only update schedules if user submitted schedule form data
            if has_any_schedule_data:
                config['schedules'] = schedules
                print("Updating schedules: {} schedules configured".format(len(schedules)))
            else:
                # No schedule data in form - preserve existing schedules
                print("No schedule data in request - preserving existing schedules")
            
            # ===== START: Validate all schedules =====
            for i, schedule in enumerate(schedules):
                heater_temp = schedule.get('heater_target', 80.0)
                ac_temp = schedule.get('ac_target', 77.0)
                
                if heater_temp > ac_temp:
                    print("❌ Schedule validation failed: Schedule {} has heater ({}) > AC ({})".format(
                        i+1, heater_temp, ac_temp
                    ))
                    return self._get_error_page(
                        "Invalid Schedule",
                        "Schedule {} ({}): Heater target ({:.1f}°F) cannot be greater than AC target ({:.1f}°F)".format(
                            i+1, schedule.get('name', 'Unnamed'), heater_temp, ac_temp
                        ),
                        sensors, ac_monitor, heater_monitor
                    )
            # ===== END: Validate all schedules =====
            
            # Save to file
            if self._save_config_to_file(config):
                print("Schedule configuration saved")
                
                # ===== ADD THIS: Reload config into memory immediately =====
                try:
                    with open('config.json', 'r') as f:
                        updated_config = json.load(f)
                        # Update the passed-in config dict (updates reference, not copy)
                        config.clear()
                        config.update(updated_config)
                    print("✅ Config reloaded into memory")
                except Exception as e:
                    print("⚠️ Warning: Could not reload config: {}".format(e))
                # ===== END: Reload config =====
                
                if schedule_monitor:
                    schedule_monitor.reload_config(config)
                    
                # Update AC and heater monitors with new targets from config
                if ac_monitor:
                    ac_monitor.target_temp = config['ac_target']
                    ac_monitor.temp_swing = config['ac_swing']
                if heater_monitor:
                    heater_monitor.target_temp = config['heater_target']
                    heater_monitor.temp_swing = config['heater_swing']
            
            # Send Discord notification
            try:
                mode = "automatic" if config.get('schedule_enabled') else "hold"
                message = "📅 Schedules updated ({} mode) - {} schedules configured".format(
                    mode, len(schedules)
                )
                discord_webhook.send_discord_message(message)
            except:
                pass
            # ===== END: Handle schedule configuration save =====
            
            # Redirect back to homepage with cache-busting headers
            redirect_response = 'HTTP/1.1 303 See Other\r\n'
            redirect_response += 'Location: /\r\n'
            redirect_response += 'Content-Length: 0\r\n'
            redirect_response += 'Connection: close\r\n'
            redirect_response += 'Cache-Control: no-cache, no-store, must-revalidate\r\n'
            redirect_response += 'Pragma: no-cache\r\n'
            redirect_response += 'Expires: 0\r\n'
            redirect_response += '\r\n'
            print("DEBUG: Returning redirect to dashboard (with cache-busting)")
            return redirect_response
            
        except Exception as e:
            print("Error updating schedule: {}".format(e))
            import sys
            sys.print_exception(e)
            # Safety: avoid rendering an error page here; just redirect
            redirect_response = 'HTTP/1.1 303 See Other\r\n'
            redirect_response += 'Location: /schedule\r\n'
            redirect_response += 'Content-Length: 0\r\n'
            redirect_response += 'Connection: close\r\n'
            redirect_response += '\r\n'
            return redirect_response

    def _handle_update(self, request, sensors, ac_monitor, heater_monitor, schedule_monitor, config):
        """Handle form submission and update settings."""
        try:
            body = request.split('\r\n\r\n')[1] if '\r\n\r\n' in request else ''
            params = {}
            
            for pair in body.split('&'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    # Don't convert hold_type to float
                    if key == 'hold_type':
                        params[key] = value
                    else:
                        params[key] = float(value)
            
            # Check which hold button was clicked
            hold_type = params.get('hold_type', 'temp')  # Default to temp hold
            is_permanent = (hold_type == 'perm')
            
            # ===== START: Validate Heat <= AC =====
            new_heater_target = params.get('heater_target', config.get('heater_target', 80.0))
            new_ac_target = params.get('ac_target', config.get('ac_target', 77.0))
            
            if new_heater_target > new_ac_target:
                print("❌ Validation failed: Heater target ({}) cannot be greater than AC target ({})".format(
                    new_heater_target, new_ac_target
                ))
                return self._get_error_page(
                    "Invalid Settings",
                    "Heater target ({:.1f}°F) cannot be greater than AC target ({:.1f}°F)".format(
                        new_heater_target, new_ac_target
                    ),
                    sensors, ac_monitor, heater_monitor
                )
            # ===== END: Validate Heat <= AC =====
            
            # ===== START: Update AC Settings =====
            if 'ac_target' in params and ac_monitor:
                ac_monitor.target_temp = params['ac_target']
                config['ac_target'] = params['ac_target']
                print("AC target updated to {}°F".format(params['ac_target']))
            # ===== END: Update AC Settings =====
            
            # ===== START: Update Heater Settings =====
            if 'heater_target' in params and heater_monitor:
                heater_monitor.target_temp = params['heater_target']
                config['heater_target'] = params['heater_target']
                print("Heater target updated to {}°F".format(params['heater_target']))
            # ===== END: Update Heater Settings =====
            
            # ===== START: Enter hold mode based on button clicked =====
            config['schedule_enabled'] = False
            config['permanent_hold'] = is_permanent
            
            if is_permanent:
                # Permanent hold - no timer
                config['temp_hold_start_time'] = None
                print("🛑 Permanent hold activated - Manual control")
            else:
                # Temporary hold - set timer
                config['temp_hold_start_time'] = time.time()
                print("⏸️ Temporary hold activated - Manual override (1 hour)")
            
            # Reload schedule monitor to disable it
            if schedule_monitor:
                schedule_monitor.reload_config(config)
            # ===== END: Enter hold mode =====

            
            # ===== START: Save settings to file =====
            if self._save_config_to_file(config):
                print("Settings persisted to disk")
                
                # ===== RELOAD config into memory immediately =====
                try:
                    with open('config.json', 'r') as f:
                        updated_config = json.load(f)
                        config.clear()
                        config.update(updated_config)
                    print("✅ Config reloaded into memory")
                except Exception as e:
                    print("⚠️ Warning: Could not reload config: {}".format(e))
                # ===== END: Reload config =====
            # ===== END: Save settings to file =====
            
            # ===== START: Send Discord notification =====
            try:
                hold_label = "PERMANENT HOLD" if is_permanent else "TEMPORARY HOLD"
                duration = "" if is_permanent else " (1 hour)"
                
                message = "{} {} - AC: {}°F | Heater: {}°F{}".format(
                    "🛑" if is_permanent else "⏸️",
                    hold_label,
                    params.get('ac_target', 'N/A'),
                    params.get('heater_target', 'N/A'),
                    duration
                )
                discord_webhook.send_discord_message(message)
            except Exception as discord_error:
                print("Discord notification failed: {}".format(discord_error))
            # ===== END: Send Discord notification =====
            
        except Exception as e:
            print("Error updating settings: {}".format(e))
            import sys
            sys.print_exception(e)
        
        return self._get_status_page(sensors, ac_monitor, heater_monitor, schedule_monitor, show_success=True)

    def _get_status_page(self, sensors, ac_monitor, heater_monitor, schedule_monitor=None, show_success=False):
        """Generate HTML status page."""
        print("DEBUG: Generating status page...")
        
        # ===== FORCE GARBAGE COLLECTION BEFORE BIG ALLOCATION =====
        import gc # type: ignore
        gc.collect()
        print("DEBUG: Memory freed, {} bytes available".format(gc.mem_free()))
        # ===== END GARBAGE COLLECTION =====
        
        try:
            # Get current temperatures (use cached values to avoid blocking)
            inside_temp = getattr(sensors.get('inside'), 'last_temp', None)
            outside_temp = getattr(sensors.get('outside'), 'last_temp', None)
            
            # Fallback to sensor read if no cached value (first load only)
            if inside_temp is None:
                inside_temps = sensors['inside'].read_all_temps(unit='F')
                inside_temp = list(inside_temps.values())[0] if inside_temps else "N/A"
            
            if outside_temp is None:
                outside_temps = sensors['outside'].read_all_temps(unit='F')
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
            
            # ===== START: Determine schedule status display =====
            has_schedules = len([s for s in config.get('schedules', []) if s.get('time')]) > 0
            
            if not has_schedules:
                schedule_status = "NO SCHEDULES"
                schedule_color = "#95a5a6"
                schedule_icon = "⚠️"
            elif config.get('schedule_enabled'):
                schedule_status = "AUTOMATIC"
                schedule_color = "#2ecc71"
                schedule_icon = "✅"
            elif config.get('permanent_hold', False):
                schedule_status = "PERMANENT HOLD"
                schedule_color = "#e74c3c"
                schedule_icon = "🛑"
            else:
                schedule_status = "TEMPORARY HOLD"
                schedule_color = "#f39c12"
                schedule_icon = "⏸️"
            # ===== END: Determine schedule status display =====
            
            # Build schedule cards
            schedule_cards = ""
            
            # Build mode buttons for dashboard
            mode_buttons = self._build_mode_buttons(config)
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
                            Heat: {heater_temp}°F | AC: {ac_temp}°F
                        </div>
                    </div>
                    """.format(
                        time=time_value,      # Use decoded value
                        name=name_value,      # Use decoded value
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
            
            # Format temperature values
            inside_temp_str = "{:.1f}".format(inside_temp) if isinstance(inside_temp, float) else str(inside_temp)
            outside_temp_str = "{:.1f}".format(outside_temp) if isinstance(outside_temp, float) else str(outside_temp)
            
          # ===== START: Add HOLD mode banner with countdown timer =====
            hold_banner = ""
            
            # Calculate remaining time for temporary hold
            temp_hold_remaining = ""
            if not config.get('schedule_enabled', False) and not config.get('permanent_hold', False):
                # In temporary hold - check timer from CONFIG (not schedule_monitor)
                temp_hold_start = config.get('temp_hold_start_time')  # READ FROM CONFIG
                
                if temp_hold_start is not None:
                    # Get hold duration from config
                    temp_hold_duration = config.get('temp_hold_duration', 3600)
                    
                    # Calculate elapsed time
                    elapsed = time.time() - temp_hold_start
                    # Calculate remaining time
                    remaining = temp_hold_duration - elapsed
                    
                    if remaining > 0:
                        # Convert to minutes
                        mins_remaining = int(remaining // 60)
                        
                        # Format the display text
                        if mins_remaining > 60:
                            # Show hours and minutes for long durations
                            hours = mins_remaining // 60
                            mins = mins_remaining % 60
                            temp_hold_remaining = " - {}h {}m remaining".format(hours, mins)
                        elif mins_remaining > 1:
                            # Show just minutes
                            temp_hold_remaining = " - {} min remaining".format(mins_remaining)
                        elif mins_remaining == 1:
                            # Show singular "minute"
                            temp_hold_remaining = " - 1 minute remaining"
                        else:
                            # Less than 1 minute left
                            secs_remaining = int(remaining)
                            temp_hold_remaining = " - {}s remaining".format(secs_remaining)
                    else:
                        # Timer expired (should auto-resume soon)
                        temp_hold_remaining = " - Resuming..."
            
            if config.get('permanent_hold', False):
                # PERMANENT HOLD - No timer, stays until user resumes or reboot
                hold_banner = """
                <div style="background: linear-gradient(135deg, #e74c3c, #c0392b); color: white; padding: 15px; border-radius: 10px; text-align: center; font-weight: bold; margin-bottom: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.2); animation: fadeIn 0.5s;">
                    🛑 PERMANENT HOLD - Schedules disabled (Manual control only)
                </div>
                """
            elif not config.get('schedule_enabled', False) and has_schedules:
                # TEMPORARY HOLD - Show countdown timer
                hold_banner = """
                <div style="background: linear-gradient(135deg, #f39c12, #e67e22); color: white; padding: 15px; border-radius: 10px; text-align: center; font-weight: bold; margin-bottom: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.2); animation: fadeIn 0.5s;">
                    ⏸️ TEMPORARY HOLD - Manual override active{remaining}
                </div>
                """.format(remaining=temp_hold_remaining)
            # ===== END: Add HOLD mode banner with countdown timer =====
            # Final HTML assembly
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
            <!-- ===== HEATER FIRST (LEFT) ===== -->
            <div class="status-item">
                <div class="status-icon">🔥</div>
                <div class="label">Heating System</div>
                <div class="status-indicator {heater_class}">{heater_status}</div>
                <div class="targets">Target: {heater_target}°F ± {heater_swing}°F</div>
            </div>
            <!-- ===== AC SECOND (RIGHT) ===== -->
            <div class="status-item">
                <div class="status-icon">❄️</div>
                <div class="label">Air Conditioning</div>
                <div class="status-indicator {ac_class}">{ac_status}</div>
                <div class="targets">Target: {ac_target}°F ± {ac_swing}°F</div>
            </div>
        </div>
        
                <form method="POST" action="/update" class="controls">
            <h2 style="text-align: center; color: #34495e; margin-bottom: 20px;">🎯 Adjust Hold Settings</h2>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px;">
                <!-- ===== LEFT COLUMN: Heater ===== -->
                <div>
                    <div class="control-group">
                        <label class="control-label">🔥 Heater Target (°F)</label>
                        <input type="number" name="heater_target" value="{heater_target}" step="0.5" min="60" max="85">
                    </div>
                </div>
                
                <!-- ===== RIGHT COLUMN: AC ===== -->
                <div>
                    <div class="control-group">
                        <label class="control-label">❄️ AC Target (°F)</label>
                        <input type="number" name="ac_target" value="{ac_target}" step="0.5" min="60" max="85">
                    </div>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-top: 20px;">
                <button type="submit" name="hold_type" value="temp" class="btn" style="background: linear-gradient(135deg, #f39c12, #e67e22);">
                    ⏸️ Temp Hold
                </button>
                <button type="submit" name="hold_type" value="perm" class="btn" style="background: linear-gradient(135deg, #e74c3c, #c0392b);">
                    🛑 Perm Hold
                </button>
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
        {mode_buttons}
        
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-top: 20px;">
            <a href="/schedule" class="btn" style="text-decoration: none; display: inline-block;">
                📅 Edit Schedules
            </a>
            <a href="/settings" class="btn" style="text-decoration: none; display: inline-block; background: linear-gradient(135deg, #95a5a6, #7f8c8d);">
                ⚙️ Advanced Settings
            </a>
        </div>
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
                mode_buttons=mode_buttons
            )
            self.last_page_render = time.time()  # Track successful render
            return html
            
        except Exception as e:
            print("Error generating page: {}".format(e))
            import sys
            sys.print_exception(e)
            return "<html><body><h1>Error loading page</h1><pre>{}</pre></body></html>".format(str(e))

    def _get_error_page(self, error_title, error_message, sensors, ac_monitor, heater_monitor):
        """Generate error page with message."""
        # Get current temps (cached, fast - no blocking sensor reads)
        inside_temp = getattr(sensors.get('inside'), 'last_temp', None) or "N/A"
        outside_temp = getattr(sensors.get('outside'), 'last_temp', None) or "N/A"
        
        # Format temperature values
        inside_temp_str = "{:.1f}".format(inside_temp) if isinstance(inside_temp, float) else str(inside_temp)
        outside_temp_str = "{:.1f}".format(outside_temp) if isinstance(outside_temp, float) else str(outside_temp)
        
        # Get current statuses
        ac_status = "ON" if ac_monitor and ac_monitor.ac.get_state() else "OFF"
        heater_status = "ON" if heater_monitor and heater_monitor.heater.get_state() else "OFF"
        
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Error - Climate Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        .container {{
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        .error-banner {{
            background: linear-gradient(135deg, #e74c3c, #c0392b);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            font-weight: bold;
            margin-bottom: 20px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        .error-title {{
            font-size: 24px;
            margin-bottom: 10px;
        }}
        .error-message {{
            font-size: 16px;
            line-height: 1.5;
        }}
        .btn {{
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            text-decoration: none;
            display: inline-block;
            margin-top: 20px;
        }}
        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(52, 152, 219, 0.4);
        }}
        .status-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 20px;
        }}
        .status-card {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="error-banner">
            <div class="error-title">❌ {error_title}</div>
            <div class="error-message">{error_message}</div>
        </div>
        
        <div class="status-grid">
            <div class="status-card">
                <div style="font-size: 14px; color: #7f8c8d; margin-bottom: 5px;">🏠 Inside</div>
                <div style="font-size: 24px; font-weight: bold; color: #2c3e50;">{inside_temp}°F</div>
            </div>
            <div class="status-card">
                <div style="font-size: 14px; color: #7f8c8d; margin-bottom: 5px;">🌡️ Outside</div>
                <div style="font-size: 24px; font-weight: bold; color: #2c3e50;">{outside_temp}°F</div>
            </div>
            <div class="status-card">
                <div style="font-size: 14px; color: #7f8c8d; margin-bottom: 5px;">🔥 Heater</div>
                <div style="font-size: 24px; font-weight: bold; color: #2c3e50;">{heater_status}</div>
            </div>
            <div class="status-card">
                <div style="font-size: 14px; color: #7f8c8d; margin-bottom: 5px;">❄️ AC</div>
                <div style="font-size: 24px; font-weight: bold; color: #2c3e50;">{ac_status}</div>
            </div>
        </div>
        
        <div style="text-align: center;">
            <a href="/" class="btn">⬅️ Go Back</a>
        </div>
    </div>
</body>
</html>
        """.format(
            error_title=error_title,
            error_message=error_message,
            inside_temp=inside_temp_str,
            outside_temp=outside_temp_str,
            heater_status=heater_status,
            ac_status=ac_status
        )
        
        return html

    def _get_schedule_editor_page(self, sensors, ac_monitor, heater_monitor):
        """Generate schedule editor page (no auto-refresh, schedules only)."""
        # Get current temps (read if not cached)
        inside_temp = getattr(sensors.get('inside'), 'last_temp', None)
        if inside_temp is None:
            inside_temps = sensors['inside'].read_all_temps(unit='F')
            inside_temp = list(inside_temps.values())[0] if inside_temps else "N/A"
        
        outside_temp = getattr(sensors.get('outside'), 'last_temp', None)
        if outside_temp is None:
            outside_temps = sensors['outside'].read_all_temps(unit='F')
            outside_temp = list(outside_temps.values())[0] if outside_temps else "N/A"
        
        # Format temperature values
        inside_temp_str = "{:.1f}".format(inside_temp) if isinstance(inside_temp, float) else str(inside_temp)
        outside_temp_str = "{:.1f}".format(outside_temp) if isinstance(outside_temp, float) else str(outside_temp)
        
        # Load config
        config = self._load_config()
        schedules = config.get('schedules', [])
        
        # Pad with empty schedules up to 4
        while len(schedules) < 4:
            schedules.append({
                'time': '',
                'name': '',
                'ac_target': config.get('ac_target', 75.0),      # ✅ Uses 78°F from config
                'heater_target': config.get('heater_target', 72.0)  # ✅ Uses 70°F from config
            })

        # ===== DEBUG: Verify we have 4 schedules =====
        print("DEBUG: Schedule editor will render {} schedules:".format(len(schedules[:4])))
        for i, s in enumerate(schedules[:4]):
            print("  Schedule {}: time='{}', name='{}', heater={}, ac={}".format(
                i, s.get('time', '(empty)'), s.get('name', '(empty)'),
                s.get('heater_target', 'N/A'), s.get('ac_target', 'N/A')
            ))
        # ===== END DEBUG =====

        # Build schedule inputs
        schedule_inputs = ""
        for i, schedule in enumerate(schedules[:4]):
            print("DEBUG: Building HTML for schedule {}...".format(i))
            
            time_value = schedule.get('time', '')
            name_value = schedule.get('name', '')
            heater_value = schedule.get('heater_target', config.get('heater_target'))
            ac_value = schedule.get('ac_target', config.get('ac_target'))
            
            print("DEBUG:   Values: time='{}', name='{}', heater={}, ac={}".format(
                time_value, name_value, heater_value, ac_value))
            
            # Build HTML - MINIMAL VERSION with hidden markers
            schedule_inputs += '<div class="sched">\n'
            schedule_inputs += '<h3>Schedule ' + str(i+1) + '</h3>\n'
            
            # Hidden input to mark this schedule exists (always sent)
            schedule_inputs += '<input type="hidden" name="schedule_' + str(i) + '_exists" value="1">\n'
            
            schedule_inputs += '<label>Time</label>\n'
            schedule_inputs += '<input type="time" name="schedule_' + str(i) + '_time" value="' + str(time_value) + '">\n'
            schedule_inputs += '<label>Name</label>\n'
            schedule_inputs += '<input type="text" name="schedule_' + str(i) + '_name" value="' + str(name_value) + '" placeholder="Schedule ' + str(i+1) + '">\n'
            schedule_inputs += '<label>Heater (°F)</label>\n'
            # Add required attribute to force validation
            schedule_inputs += '<input type="number" name="schedule_' + str(i) + '_heater" value="' + str(heater_value) + '" step="0.5" min="60" max="85" required>\n'
            schedule_inputs += '<label>AC (°F)</label>\n'
            # Add required attribute to force validation
            schedule_inputs += '<input type="number" name="schedule_' + str(i) + '_ac" value="' + str(ac_value) + '" step="0.5" min="60" max="90" required>\n'
            schedule_inputs += '</div>\n'
            
            print("DEBUG:   HTML generated, length now: {} bytes".format(len(schedule_inputs)))
        
        html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Schedule Editor - Climate Control</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta charset="utf-8">
        <style>
            .sched {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 15px;
                border: 2px solid #ddd;
            }}
            .sched h3 {{
                color: #34495e;
                margin-bottom: 15px;
            }}
            .sched label {{
                display: block;
                margin: 10px 0 5px 0;
                font-weight: bold;
                color: #555;
            }}
            .sched input {{
                width: 100%;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-bottom: 10px;
            }}
            body {{
                font-family: Arial, sans-serif;
                max-width: 1000px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            .container {{
                background: white;
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            }}
            h1 {{
                color: #2c3e50;
                text-align: center;
                margin-bottom: 20px;
            }}
            .header-info {{
                display: flex;
                justify-content: center;
                gap: 30px;
                margin-bottom: 30px;
                padding: 15px;
                background: #f8f9fa;
                border-radius: 10px;
            }}
            .btn {{
                padding: 12px 24px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                cursor: pointer;
                font-size: 16px;
                text-decoration: none;
                display: inline-block;
            }}
            .btn:hover {{ transform: translateY(-2px); }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📅 Schedule Configuration</h1>
            
            <div class="header-info">
                <div>🏠 Inside: <strong>{inside_temp}°F</strong></div>
                <div>🌡️ Outside: <strong>{outside_temp}°F</strong></div>
            </div>
            
            <form method="POST" action="/schedule">
                <h3 style="color: #34495e; margin-bottom: 15px;">⏰ Configure Schedule Times & Temperatures</h3>
                <p style="color: #7f8c8d; margin-bottom: 20px;">
                    Set up to 4 time-based schedules. Leave time blank to disable a schedule.
                </p>
                
                {schedule_inputs}
                
                <div style="margin-top: 20px;">
                    <button type="submit" name="mode_action" value="save_schedules" class="btn" style="width: 100%;">
                        💾 Save Schedule Configuration
                    </button>
                </div>
            </form>
            
            <div style="text-align: center; margin-top: 20px;">
                <a href="/" class="btn" style="background: linear-gradient(135deg, #95a5a6, #7f8c8d);">
                    ⬅️ Back to Dashboard
                </a>
            </div>
            
            <div style="text-align: center; color: #7f8c8d; margin-top: 20px; padding-top: 20px; border-top: 2px solid #ecf0f1;">
                💡 This page does not auto-refresh<br>
                To change modes (Automatic/Hold), return to the dashboard
            </div>
        </div>
    </body>
    </html>
        """.format(
            inside_temp=inside_temp_str,
            outside_temp=outside_temp_str,
            schedule_inputs=schedule_inputs
        )
        
        return html

    def _build_mode_buttons(self, config):
        """Build mode control buttons for dashboard only."""
        schedules = config.get('schedules', [])
        has_schedules = len([s for s in schedules if s.get('time')]) > 0
        
        if not has_schedules:
            return """
            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; color: #7f8c8d; margin: 20px 0;">
                ℹ️ No schedules configured - <a href="/schedule" style="color: #667eea; font-weight: bold;">Configure schedules</a>
            </div>
            """
        
        # Build mode buttons based on current state
        if config.get('schedule_enabled'):
            # ===== NEW: Find active schedule =====
            active_schedule_name = "None"
            current_time = time.localtime()
            current_minutes = current_time[3] * 60 + current_time[4]
            
            # Sort schedules by time and find the active one
            sorted_schedules = []
            for schedule in schedules:
                if schedule.get('time'):
                    try:
                        time_parts = schedule['time'].split(':')
                        schedule_minutes = int(time_parts[0]) * 60 + int(time_parts[1])
                        sorted_schedules.append((schedule_minutes, schedule))
                    except:
                        pass
            
            sorted_schedules.sort()
            
            # Find most recent schedule that has passed
            for schedule_minutes, schedule in sorted_schedules:
                if current_minutes >= schedule_minutes:
                    active_schedule_name = schedule.get('name', 'Unnamed')
                else:
                    break
            
            # If no schedule found (before first one), use last from yesterday
            if active_schedule_name == "None" and sorted_schedules:
                active_schedule_name = sorted_schedules[-1][1].get('name', 'Unnamed')
            # ===== END: Find active schedule =====
            
            return """
            <form method="POST" action="/schedule" style="margin: 20px 0;">
                <div style="background: linear-gradient(135deg, #2ecc71, #27ae60); color: white; padding: 15px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.2);">
                    <div style="font-weight: bold; font-size: 18px; margin-bottom: 5px;">✅ Automatic Mode</div>
                    <div style="font-size: 14px; opacity: 0.9; margin-bottom: 10px;">Currently running: <strong>{active_schedule}</strong></div>
                    <div style="font-size: 13px; opacity: 0.8;">Temperatures adjust based on schedule</div>
                </div>
            </form>
            """.format(active_schedule=active_schedule_name)
        elif config.get('permanent_hold', False):
            return """
            <form method="POST" action="/schedule" style="margin: 20px 0;">
                <div style="background: linear-gradient(135deg, #e74c3c, #c0392b); color: white; padding: 15px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.2);">
                    <div style="font-weight: bold; font-size: 18px; margin-bottom: 10px;">🛑 Permanent Hold</div>
                    <div style="font-size: 14px; margin-bottom: 15px;">Manual control only - Schedules disabled</div>
                    <div style="text-align: center;">
                        <button type="submit" name="mode_action" value="resume" style="padding: 10px 20px; background: #2ecc71; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold;">▶️ Resume Scheduling</button>
                    </div>
                </div>
            </form>
            """
        else:
            return """
            <form method="POST" action="/schedule" style="margin: 20px 0;">
                <div style="background: linear-gradient(135deg, #f39c12, #e67e22); color: white; padding: 15px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.2);">
                    <div style="font-weight: bold; font-size: 18px; margin-bottom: 10px;">⏸️ Temporary Hold</div>
                    <div style="font-size: 14px; margin-bottom: 15px;">Manual override active</div>
                    <div style="text-align: center;">
                        <button type="submit" name="mode_action" value="resume" style="padding: 10px 20px; background: #2ecc71; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold;">▶️ Resume Scheduling</button>
                    </div>
                </div>
            </form>
            """
    
    def _get_settings_page(self, sensors, ac_monitor, heater_monitor):
        """Generate advanced settings page."""
        config = self._load_config()
        
        # Get temperatures (read if not cached)
        inside_temp = getattr(sensors.get('inside'), 'last_temp', None)
        if inside_temp is None:
            inside_temps = sensors['inside'].read_all_temps(unit='F')
            inside_temp = list(inside_temps.values())[0] if inside_temps else "N/A"
        
        outside_temp = getattr(sensors.get('outside'), 'last_temp', None)
        if outside_temp is None:
            outside_temps = sensors['outside'].read_all_temps(unit='F')
            outside_temp = list(outside_temps.values())[0] if outside_temps else "N/A"
        
        inside_temp_str = "{:.1f}".format(inside_temp) if isinstance(inside_temp, float) else str(inside_temp)
        outside_temp_str = "{:.1f}".format(outside_temp) if isinstance(outside_temp, float) else str(outside_temp)
        
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Advanced Settings - Climate Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta charset="utf-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            margin-bottom: 20px;
        }}
        .header-info {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 30px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
        }}
        .setting-group {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .setting-group h3 {{
            color: #34495e;
            margin-bottom: 15px;
        }}
        label {{
            display: block;
            margin: 15px 0 5px 0;
            font-weight: bold;
            color: #555;
        }}
        input[type="number"] {{
            width: 100%;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 16px;
        }}
        input[type="number"]:focus {{
            border-color: #667eea;
            outline: none;
        }}
        .btn {{
            padding: 12px 24px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: bold;
            cursor: pointer;
            font-size: 16px;
            text-decoration: none;
            display: inline-block;
            width: 100%;
        }}
        .btn:hover {{ transform: translateY(-2px); }}
        .btn-secondary {{
            background: linear-gradient(135deg, #95a5a6, #7f8c8d);
            margin-top: 10px;
        }}
        .info-box {{
            background: #e8f4f8;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>⚙️ Advanced Settings</h1>
        
        <div class="header-info">
            <div>🏠 Inside: <strong>{inside_temp}°F</strong></div>
            <div>🌡️ Outside: <strong>{outside_temp}°F</strong></div>
        </div>
        
        <div class="info-box">
            💡 <strong>Note:</strong> These settings control the tolerance ranges for automatic climate control. Changes take effect immediately.
        </div>
        
        <form method="POST" action="/settings">
            <div class="setting-group">
                <h3>🔥 Heating System</h3>
                <label>Heater Swing (±°F)</label>
                <input type="number" name="heater_swing" value="{heater_swing}" step="0.5" min="0.5" max="5" required>
                <small style="color: #7f8c8d; display: block; margin-top: 5px;">
                    How many degrees below target before heater turns ON
                </small>
            </div>
            
            <div class="setting-group">
                <h3>❄️ Air Conditioning</h3>
                <label>AC Swing (±°F)</label>
                <input type="number" name="ac_swing" value="{ac_swing}" step="0.5" min="0.5" max="5" required>
                <small style="color: #7f8c8d; display: block; margin-top: 5px;">
                    How many degrees above target before AC turns ON
                </small>
            </div>
            
            <div class="setting-group">
                <h3>⏱️ Hold Duration</h3>
                <label>Temporary Hold Duration (minutes)</label>
                <input type="number" name="temp_hold_duration" value="{temp_hold_mins}" step="1" min="1" max="1440" required>
                <small style="color: #7f8c8d; display: block; margin-top: 5px;">
                    How long temporary holds last before auto-resuming (default: 60 min)
                </small>
            </div>
            
            <div class="setting-group">
                <h3>🌐 Timezone</h3>
                <label>UTC Offset (hours)</label>
                <input type="number" name="timezone_offset" value="{timezone_offset}" step="1" min="-12" max="14" required>
                <small style="color: #7f8c8d; display: block; margin-top: 5px;">
                    CST=-6, CDT=-5, EST=-5, EDT=-4, MST=-7, PST=-8
                </small>
            </div>
            
            <button type="submit" class="btn">💾 Save Settings</button>
        </form>
        
        <a href="/" class="btn btn-secondary" style="text-align: center;">⬅️ Back to Dashboard</a>
    </div>
</body>
</html>
        """.format(
            inside_temp=inside_temp_str,
            outside_temp=outside_temp_str,
            heater_swing=config.get('heater_swing', 2.0),
            ac_swing=config.get('ac_swing', 1.0),
            temp_hold_mins=int(config.get('temp_hold_duration', 3600) / 60),
            timezone_offset=config.get('timezone_offset', -6)
        )
        
        return html

    def _handle_settings_update(self, request, sensors, ac_monitor, heater_monitor, schedule_monitor, config):
        """Handle advanced settings update."""
        try:
            body = request.split('\r\n\r\n')[1] if '\r\n\r\n' in request else ''
            params = {}
            
            for pair in body.split('&'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    params[key] = float(value)
            
            # Update swing settings
            if 'ac_swing' in params:
                config['ac_swing'] = params['ac_swing']
                if ac_monitor:
                    ac_monitor.temp_swing = params['ac_swing']
                print("AC swing updated to {}°F".format(params['ac_swing']))
            
            if 'heater_swing' in params:
                config['heater_swing'] = params['heater_swing']
                if heater_monitor:
                    heater_monitor.temp_swing = params['heater_swing']
                print("Heater swing updated to {}°F".format(params['heater_swing']))
            
            # Update hold duration (convert minutes to seconds)
            if 'temp_hold_duration' in params:
                duration_seconds = int(params['temp_hold_duration'] * 60)
                config['temp_hold_duration'] = duration_seconds
                if schedule_monitor:
                    schedule_monitor.temp_hold_duration = duration_seconds
                print("Temp hold duration updated to {} minutes".format(int(params['temp_hold_duration'])))
            
            # Update timezone offset
            if 'timezone_offset' in params:
                config['timezone_offset'] = int(params['timezone_offset'])
                print("Timezone offset updated to UTC{:+d}".format(int(params['timezone_offset'])))
            
            # Save to file
            if self._save_config_to_file(config):
                print("Advanced settings saved")
                
                # Reload config
                try:
                    with open('config.json', 'r') as f:
                        updated_config = json.load(f)
                        config.clear()
                        config.update(updated_config)
                    print("✅ Config reloaded")
                except Exception as e:
                    print("⚠️ Could not reload: {}".format(e))
            
            # Discord notification
            try:
                discord_webhook.send_discord_message("⚙️ Advanced settings updated")
            except:
                pass
            
        except Exception as e:
            print("Error updating settings: {}".format(e))
            import sys
            sys.print_exception(e)
        
        # Redirect to dashboard
        redirect_response = 'HTTP/1.1 303 See Other\r\n'
        redirect_response += 'Location: /\r\n'
        redirect_response += 'Content-Length: 0\r\n'
        redirect_response += 'Connection: close\r\n'
        redirect_response += '\r\n'
        return redirect_response