import sys
import json
import time
import subprocess
import os
import re
import platform
import shlex
import threading
import tempfile
from datetime import datetime, timezone
from lib.KustoHandler import execute_adx_query
from lib.AzureCliHelper import is_azure_cli_installed

# Global settings
DEBUG_MODE = os.environ.get("MCP_DEBUG", "false").lower() == "true"
SUBSCRIPTIONS_CACHE_FILE = os.path.expanduser("~/.azure/mcp_subscriptions_cache.json")

class KustoEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        # Handle pandas/numpy types if needed
        try:
            import numpy as np
            if isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
                return int(obj)
            if isinstance(obj, (np.float64, np.float32)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        return super().default(obj)

def get_timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def create_envelope(action, status="success", data=None, error=None, start_time=None, authenticated=False, metadata_extra=None):
    execution_time_ms = int((time.time() - start_time) * 1000) if start_time else 0
    
    metadata = {
        "timestamp": get_timestamp(),
        "execution_time_ms": execution_time_ms,
        "authenticated": authenticated
    }
    if metadata_extra:
        metadata.update(metadata_extra)
        
    return {
        "status": status,
        "action": action,
        "data": data,
        "error": error,
        "metadata": metadata
    }

def run_az_command(args):
    os_name = platform.system().lower()
    if os_name == "windows":
        # On Windows, az is often a batch file, so we might need shell=True or full path
        command = ["cmd.exe", "/c", "az"] + args
    else:
        command = ["az"] + args
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        return result
    except Exception as e:
        # Internal error if we can't even run the command
        return None

def get_auth_status():
    result = run_az_command(["account", "show", "--output", "json"])
    if result and result.returncode == 0:
        try:
            account_info = json.loads(result.stdout)
            return True, account_info
        except:
            pass
    return False, None

def save_subscriptions_cache(subscriptions):
    try:
        os.makedirs(os.path.dirname(SUBSCRIPTIONS_CACHE_FILE), exist_ok=True)
        payload = {
            "timestamp": get_timestamp(),
            "subscriptions": subscriptions
        }
        with open(SUBSCRIPTIONS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except:
        pass

def load_subscriptions_cache():
    try:
        if not os.path.exists(SUBSCRIPTIONS_CACHE_FILE):
            return None
        with open(SUBSCRIPTIONS_CACHE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        subscriptions = payload.get("subscriptions", [])
        if isinstance(subscriptions, list):
            return subscriptions
    except:
        pass
    return None

def clear_subscriptions_cache():
    try:
        if os.path.exists(SUBSCRIPTIONS_CACHE_FILE):
            os.remove(SUBSCRIPTIONS_CACHE_FILE)
    except:
        pass

def fetch_valid_subscriptions():
    result = run_az_command(["account", "list", "--output", "json"])
    if not result or result.returncode != 0:
        return None
    try:
        raw_subscriptions = json.loads(result.stdout)
        if not isinstance(raw_subscriptions, list):
            return None
        subscriptions = []
        for item in raw_subscriptions:
            if not isinstance(item, dict):
                continue
            state = str(item.get("state", "")).lower()
            if state and state != "enabled":
                continue
            subscriptions.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "tenant_id": item.get("tenantId"),
                "is_default": item.get("isDefault", False),
                "state": item.get("state")
            })
        return subscriptions
    except:
        return None

def refresh_subscriptions_cache():
    subscriptions = fetch_valid_subscriptions()
    if subscriptions is not None:
        save_subscriptions_cache(subscriptions)
    return subscriptions

def handle_internal_login_monitor(temp_file_path, subscription_id=None):
    """
    Background process that runs 'az login', extracts the device code,
    and then waits for the login to complete while handling subscription selection.
    """
    os_name = platform.system().lower()
    cmd = ["az", "login", "--use-device-code"]
    if os_name == "windows":
        cmd = ["cmd.exe", "/c", "az", "login", "--use-device-code"]

    # In case we were passed an empty string or something
    if not subscription_id or subscription_id.strip() == "":
        subscription_id = None

    process = None
    try:
        if DEBUG_MODE:
            with open("/tmp/mcp_login_monitor.log", "a") as f:
                f.write(f"[{get_timestamp()}] Monitor started. Temp file: {temp_file_path}, Sub ID: {subscription_id}\n")

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, text=True)
        
        # Set non-blocking mode for stdout and stderr if not on Windows
        if os_name != "windows":
            import fcntl
            for pipe in [process.stdout, process.stderr]:
                if pipe:
                    fd = pipe.fileno()
                    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        def read_nonblocking(pipe):
            if not pipe: return None
            try:
                # Use os.read for true non-blocking on Unix
                fd = pipe.fileno()
                if fd < 0: return None
                data = os.read(fd, 4096)
                if data: return data.decode("utf-8", errors="replace")
            except (OSError, BlockingIOError):
                pass
            return None

        output = ""
        device_code_written = False
        selection_done = False
        start_wait = time.time()
        timeout_sec = 120 # 120 seconds per requirement

        while time.time() - start_wait < timeout_sec:
            if process.poll() is not None:
                if DEBUG_MODE:
                    with open("/tmp/mcp_login_monitor.log", "a") as f:
                        f.write(f"[{get_timestamp()}] Process exited with code {process.returncode}\n")
                break
            
            # Read from both pipes
            data_err = read_nonblocking(process.stderr)
            data_out = read_nonblocking(process.stdout)
            data = (data_err or "") + (data_out or "")

            if not data:
                time.sleep(0.2)
                continue

            output += data
            if DEBUG_MODE:
                with open("/tmp/mcp_login_monitor.log", "a") as f:
                    f.write(f"[{get_timestamp()}] Output chunk: {data}\n")

            if not device_code_written:
                # Look for verification URL and device code
                match = re.search(r"(https://\S+).+code (\S+)", output)
                if match:
                    verification_url = match.group(1)
                    device_code = match.group(2)
                    try:
                        with open(temp_file_path, "w") as f:
                            json.dump({"url": verification_url, "code": device_code}, f)
                        device_code_written = True
                        if DEBUG_MODE:
                            with open("/tmp/mcp_login_monitor.log", "a") as f:
                                f.write(f"[{get_timestamp()}] Device code written to temp file: {device_code}\n")
                    except Exception as e:
                        if DEBUG_MODE:
                            with open("/tmp/mcp_login_monitor.log", "a") as f:
                                f.write(f"[{get_timestamp()}] Error writing temp file: {str(e)}\n")
            
            # Handle subscription selection if it appears in output
            if subscription_id and not selection_done:
                # Search entire output for a line containing both subscription_id and a bracketed index
                # The format is typically: [index] Name ID Tenant
                match = re.search(r"\[(\d+)\].+?" + re.escape(subscription_id), output)
                if match:
                    index = match.group(1)
                    process.stdin.write(f"{index}\n")
                    process.stdin.flush()
                    selection_done = True
                    if DEBUG_MODE:
                        with open("/tmp/mcp_login_monitor.log", "a") as f:
                            f.write(f"[{get_timestamp()}] Sent selection index {index} to az login for sub {subscription_id}\n")
            
            time.sleep(0.1)

        # Ensure process is finished
        if process and process.poll() is None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()

        if process and process.returncode == 0:
            if subscription_id:
                # Double check account is set
                subprocess.run(["az", "account", "set", "--subscription", subscription_id], capture_output=True)
            refresh_subscriptions_cache()
            if DEBUG_MODE:
                with open("/tmp/mcp_login_monitor.log", "a") as f:
                    f.write(f"[{get_timestamp()}] Login completed and cache refreshed.\n")
                    
    except Exception as e:
        if DEBUG_MODE:
            with open("/tmp/mcp_login_monitor.log", "a") as f:
                f.write(f"[{get_timestamp()}] Monitor error: {str(e)}\n")
    finally:
        if process and process.poll() is None:
            process.terminate()

def start_device_login_flow(start_time, action_name, subscription_id=None, restarted_for_changed_subscription=False, custom_message=None):
    os_name = platform.system().lower()
    
    # Create temp file to communicate with monitor process
    fd, temp_file_path = tempfile.mkstemp(suffix=".json", prefix="mcp_login_")
    os.close(fd)
    
    try:
        # Spawn monitor process
        # Use sys.executable and os.path.abspath(__file__) to run this script again
        script_path = os.path.abspath(__file__)
        cmd = [sys.executable, script_path, "--internal-login-monitor", temp_file_path]
        if subscription_id:
            cmd.append(subscription_id)
            
        # Detach process
        kwargs = {}
        if os_name != "windows":
            kwargs["start_new_session"] = True
            
        if DEBUG_MODE:
            with open("/tmp/mcp_login_debug.log", "a") as f:
                f.write(f"[{get_timestamp()}] Spawning monitor: {' '.join(cmd)}\n")

        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, **kwargs)
        
        # Poll for the temp file to get device code
        device_code_info = None
        poll_start = time.time()
        while time.time() - poll_start < 15:
            if os.path.exists(temp_file_path) and os.path.getsize(temp_file_path) > 0:
                try:
                    with open(temp_file_path, "r") as f:
                        device_code_info = json.load(f)
                    break
                except:
                    pass
            time.sleep(0.5)
            
        if not device_code_info:
            # Cleanup
            if os.path.exists(temp_file_path): os.remove(temp_file_path)
            error = {
                "type": "authentication_error",
                "code": "AZ_LOGIN_FAILED",
                "message": "Azure CLI login process failed to start or provide device code in time."
            }
            return create_envelope(action_name, status="error", error=error, start_time=start_time, authenticated=False)
            
        # Success! Capture details and cleanup file
        verification_url = device_code_info["url"]
        device_code_found = device_code_info["code"]
        if os.path.exists(temp_file_path): os.remove(temp_file_path)

        if custom_message:
            message = custom_message
        elif restarted_for_changed_subscription:
            message = "Subscription changed. Restarting login. Complete device login in your browser. The process will wait up to 120 seconds in background."
        else:
            message = "Complete device login in your browser. The process will wait up to 120 seconds in background."

        data = {
            "authenticated": False,
            "login_required": True,
            "device_login": {
                "verification_url": verification_url,
                "device_code": device_code_found,
                "expires_in_seconds": 900,
                "polling_interval_seconds": 5
            },
            "message": message
        }
        return create_envelope(action_name, data=data, start_time=start_time, authenticated=False)
    except Exception as e:
        if os.path.exists(temp_file_path): os.remove(temp_file_path)
        error = {
            "type": "internal_error",
            "code": "WRAPPER_EXCEPTION",
            "message": str(e) if DEBUG_MODE else "Unexpected internal error occurred during login flow start."
        }
        return create_envelope(action_name, status="error", error=error, start_time=start_time, authenticated=False)

def handle_login(start_time, subscription_id=None):
    restarted_for_changed_subscription = False

    if not subscription_id:
        error = {
            "type": "invalid_request",
            "code": "MISSING_REQUIRED_PARAMETER",
            "message": "LOGIN requires params.subscription_id."
        }
        return create_envelope("LOGIN", status="error", error=error, start_time=start_time, authenticated=False)

    # Check if already authenticated
    is_auth, account_info = get_auth_status()
    if is_auth:
        current_subscription_id = account_info.get("id")
        if current_subscription_id == subscription_id:
            data = {
                "authenticated": True,
                "message": "Azure CLI session already authenticated.",
                "subscription": {
                    "id": account_info.get("id"),
                    "name": account_info.get("name")
                },
                "tenant_id": account_info.get("tenantId")
            }
            return create_envelope("LOGIN", data=data, start_time=start_time, authenticated=True)

        # If already logged in to a different subscription, force fresh login flow.
        logout_result = run_az_command(["logout"])
        if logout_result is None or logout_result.returncode != 0:
            error = {
                "type": "authentication_error",
                "code": "AZ_LOGOUT_FAILED",
                "message": "Failed to logout existing Azure CLI session before re-login.",
                "details": {"current_subscription_id": current_subscription_id}
            }
            return create_envelope("LOGIN", status="error", error=error, start_time=start_time, authenticated=False)
        restarted_for_changed_subscription = True

    # Not authenticated, check if az is installed
    os_name = platform.system().lower()
    if not is_azure_cli_installed(os_name):
        error = {
            "type": "environment_error",
            "code": "AZ_CLI_NOT_FOUND",
            "message": "Azure CLI is not available in container environment."
        }
        return create_envelope("LOGIN", status="error", error=error, start_time=start_time, authenticated=False)

    return start_device_login_flow(
        start_time=start_time,
        action_name="LOGIN",
        subscription_id=subscription_id,
        restarted_for_changed_subscription=restarted_for_changed_subscription
    )

def handle_auth_status(start_time):
    os_name = platform.system().lower()
    if not is_azure_cli_installed(os_name):
        error = {
            "type": "environment_error",
            "code": "AZ_CLI_NOT_FOUND",
            "message": "Azure CLI is not available in container environment."
        }
        return create_envelope("AUTH_STATUS", status="error", error=error, start_time=start_time, authenticated=False)

    is_auth, account_info = get_auth_status()
    if is_auth:
        data = {
            "authenticated": True,
            "subscription": {
                "id": account_info.get("id"),
                "name": account_info.get("name")
            },
            "tenant_id": account_info.get("tenantId"),
            "account": {
                "user": account_info.get("user", {}).get("name"),
                "environment": account_info.get("environmentName")
            }
        }
        return create_envelope("AUTH_STATUS", data=data, start_time=start_time, authenticated=True)
    else:
        data = {
            "authenticated": False,
            "message": "No active Azure CLI session."
        }
        return create_envelope("AUTH_STATUS", data=data, start_time=start_time, authenticated=False)

def handle_logout(start_time):
    os_name = platform.system().lower()
    if not is_azure_cli_installed(os_name):
        error = {
            "type": "environment_error",
            "code": "AZ_CLI_NOT_FOUND",
            "message": "Azure CLI is not available in container environment."
        }
        return create_envelope("LOGOUT", status="error", error=error, start_time=start_time, authenticated=False)

    # Check if already authenticated (optional, but good for context)
    is_auth, _ = get_auth_status()
    
    # Run az logout
    result = run_az_command(["logout"])
    
    # Ensure cache is cleared regardless of az logout result
    clear_subscriptions_cache()
    
    if result and result.returncode == 0:
        data = {
            "logged_out": True,
            "message": "Successfully logged out from Azure CLI."
        }
        return create_envelope("LOGOUT", data=data, start_time=start_time, authenticated=False)
    else:
        error = {
            "type": "authentication_error",
            "code": "AZ_LOGOUT_FAILED",
            "message": "Azure CLI logout process failed.",
            "details": {"stderr": result.stderr if result else "Failed to run az command."}
        }
        return create_envelope("LOGOUT", status="error", error=error, start_time=start_time, authenticated=is_auth)

def handle_list_subscriptions(start_time, subscription_id=None):
    os_name = platform.system().lower()
    if not is_azure_cli_installed(os_name):
        error = {
            "type": "environment_error",
            "code": "AZ_CLI_NOT_FOUND",
            "message": "Azure CLI is not available in container environment."
        }
        return create_envelope("LIST_SUBSCRIPTIONS", status="error", error=error, start_time=start_time, authenticated=False)

    is_auth, _ = get_auth_status()
    if not is_auth:
        return start_device_login_flow(
            start_time=start_time,
            action_name="LIST_SUBSCRIPTIONS",
            subscription_id=subscription_id,
            custom_message="No active Azure CLI session. Login has started. Complete device login in your browser, then call LIST_SUBSCRIPTIONS again to see your subscriptions."
        )

    subscriptions = load_subscriptions_cache()
    if subscriptions is None:
        subscriptions = refresh_subscriptions_cache()
    if subscriptions is None:
        error = {
            "type": "subscription_error",
            "code": "SUBSCRIPTION_CACHE_UNAVAILABLE",
            "message": "Unable to load subscriptions stored after the last login."
        }
        return create_envelope("LIST_SUBSCRIPTIONS", status="error", error=error, start_time=start_time, authenticated=True)

    data = {
        "subscriptions": subscriptions,
        "count": len(subscriptions),
        "message": "Showing subscriptions stored after the last login."
    }
    return create_envelope("LIST_SUBSCRIPTIONS", data=data, start_time=start_time, authenticated=True)

def handle_query(params, start_time):
    query = params.get("query")
    database = params.get("database")
    cluster_url = params.get("cluster_url")
    socks5_proxy = params.get("socks5_proxy")
    socks5_dns = params.get("socks5_dns", False)

    if not query or not database or not cluster_url:
        error = {
            "type": "invalid_parameters",
            "code": "MISSING_PARAMS",
            "message": "Missing required parameters: query, database, cluster_url."
        }
        return create_envelope("QUERY", status="error", error=error, start_time=start_time)

    # Check authentication first
    is_auth, _ = get_auth_status()
    if not is_auth:
        error = {
            "type": "authentication_required",
            "code": "AZ_NOT_AUTHENTICATED",
            "message": "Azure CLI session is not authenticated. Invoke LOGIN action."
        }
        return create_envelope("QUERY", status="error", error=error, start_time=start_time, authenticated=False)

    # Set proxy if requested
    if socks5_proxy:
        protocol = "socks5h" if socks5_dns else "socks5"
        proxy_url = f"{protocol}://{socks5_proxy}"
        os.environ["HTTP_PROXY"] = proxy_url
        os.environ["HTTPS_PROXY"] = proxy_url

    metadata_extra = {
        "cluster": cluster_url,
        "database": database
    }

    try:
        df = execute_adx_query(cluster_url, database, query)
        # Convert DataFrame to list of dicts
        result_list = df.to_dict(orient="records")
        data = {
            "result": result_list,
            "row_count": len(result_list)
        }
        return create_envelope("QUERY", data=data, start_time=start_time, authenticated=True, metadata_extra=metadata_extra)
    except Exception as e:
        error_msg = str(e)
        # Check for expired token or other errors
        if "token" in error_msg.lower() and "expire" in error_msg.lower():
            error = {
                "type": "authentication_expired",
                "code": "AZ_TOKEN_EXPIRED",
                "message": "Azure CLI token has expired. Re-authentication required."
            }
            return create_envelope("QUERY", status="error", error=error, start_time=start_time, authenticated=False, metadata_extra=metadata_extra)
        
        # Generic query failure
        error = {
            "type": "query_error",
            "code": "KUSTO_QUERY_FAILED",
            "message": "Kusto query execution failed.",
            "details": {"reason": error_msg}
        }
        return create_envelope("QUERY", status="error", error=error, start_time=start_time, authenticated=True, metadata_extra=metadata_extra)

def main():
    start_time = time.time()
    try:
        # MCP usually receives input via stdin as a single line JSON
        input_str = sys.stdin.read().strip()
        if not input_str:
            return

        input_data = json.loads(input_str)
        action = input_data.get("action", "").upper()
        params = input_data.get("params", {})
        subscription_id = params.get("subscription_id")

        if action == "LOGIN":
            if isinstance(subscription_id, str):
                subscription_id = subscription_id.strip()
            response = handle_login(start_time, subscription_id)
        elif action == "LOGOUT":
            response = handle_logout(start_time)
        elif action == "AUTH_STATUS":
            response = handle_auth_status(start_time)
        elif action == "LIST_SUBSCRIPTIONS":
            if isinstance(subscription_id, str):
                subscription_id = subscription_id.strip()
            response = handle_list_subscriptions(start_time, subscription_id)
        elif action == "QUERY":
            response = handle_query(params, start_time)
        else:
            error = {
                "type": "invalid_request",
                "code": "UNKNOWN_ACTION",
                "message": f"Unknown action: {action}"
            }
            response = create_envelope(action, status="error", error=error, start_time=start_time)

        print(json.dumps(response, indent=2 if DEBUG_MODE else None, cls=KustoEncoder))
        sys.stdout.flush()
        
        # For LOGIN and LIST_SUBSCRIPTIONS starting a login flow, we must exit immediately
        # so the caller (like docker-mcp.sh) returns, while the daemon thread stays in the background
        # if the process is not truly exited. Actually, once main() returns, the process will exit
        # because the background thread is a daemon.
        if action in ["LOGIN", "LIST_SUBSCRIPTIONS"] and response.get("status") == "success" and response.get("data", {}).get("login_required"):
            sys.exit(0)

    except json.JSONDecodeError:
        error = {
            "type": "invalid_request",
            "code": "JSON_PARSE_ERROR",
            "message": "Failed to parse input JSON."
        }
        print(json.dumps(create_envelope("UNKNOWN", status="error", error=error, start_time=start_time), cls=KustoEncoder))
    except Exception as e:
        # Try to get action from input_data if it was successfully parsed
        current_action = "UNKNOWN"
        try:
            # We already tried to parse it above, but if it failed there, we might not have input_data
            if 'input_data' in locals():
                current_action = input_data.get("action", "UNKNOWN").upper()
        except:
            pass
            
        error = {
            "type": "internal_error",
            "code": "WRAPPER_EXCEPTION",
            "message": str(e) if DEBUG_MODE else "Unexpected internal error occurred."
        }
        print(json.dumps(create_envelope(current_action, status="error", error=error, start_time=start_time), cls=KustoEncoder))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--internal-login-monitor":
        # Positional arguments: --internal-login-monitor temp_file [subscription_id]
        if len(sys.argv) < 3:
            sys.exit(1)
        temp_file = sys.argv[2]
        sub_id = sys.argv[3] if len(sys.argv) > 3 else None
        handle_internal_login_monitor(temp_file, sub_id)
        sys.exit(0)
    main()
