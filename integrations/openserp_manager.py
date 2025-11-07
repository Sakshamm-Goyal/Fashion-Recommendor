"""
OpenSERP Manager - Manages OpenSERP server lifecycle with automatic crash recovery.

This module provides:
- Server health monitoring
- Automatic crash detection
- Auto-restart on segmentation faults
- Graceful shutdown handling
"""

import asyncio
import subprocess
import logging
import signal
import os
import time
from pathlib import Path
from typing import Optional
import httpx


logger = logging.getLogger(__name__)


class OpenSERPManager:
    """
    Manages OpenSERP server with automatic crash recovery.

    OpenSERP has a segmentation fault bug that causes crashes during heavy use.
    This manager detects crashes and automatically restarts the server.
    """

    def __init__(
        self,
        openserp_binary_path: str,
        host: str = "0.0.0.0",
        port: int = 7001,
        max_restart_attempts: int = 3,
        health_check_interval: float = 30.0,
        startup_timeout: float = 10.0
    ):
        """
        Initialize OpenSERP manager.

        Args:
            openserp_binary_path: Path to openserp binary executable
            host: Host to bind server to (default: 0.0.0.0)
            port: Port to bind server to (default: 7001)
            max_restart_attempts: Maximum consecutive restart attempts before giving up
            health_check_interval: Seconds between health checks
            startup_timeout: Seconds to wait for server startup
        """
        self.openserp_binary_path = Path(openserp_binary_path)
        self.host = host
        self.port = port
        self.max_restart_attempts = max_restart_attempts
        self.health_check_interval = health_check_interval
        self.startup_timeout = startup_timeout

        self.process: Optional[subprocess.Popen] = None
        self.base_url = f"http://{host if host != '0.0.0.0' else 'localhost'}:{port}"
        self.restart_count = 0
        self.is_running = False
        self._monitor_task: Optional[asyncio.Task] = None

        if not self.openserp_binary_path.exists():
            raise FileNotFoundError(f"OpenSERP binary not found: {self.openserp_binary_path}")

        logger.info(f"[OpenSERPManager] Initialized for {self.base_url}")

    async def start(self) -> bool:
        """
        Start OpenSERP server with monitoring.

        Returns:
            True if server started successfully, False otherwise
        """
        if self.is_running:
            logger.warning("[OpenSERPManager] Server already running")
            return True

        success = await self._start_server()
        if success:
            # Start health monitoring in background
            self._monitor_task = asyncio.create_task(self._monitor_health())
            logger.info("[OpenSERPManager] Started server with health monitoring")

        return success

    async def _start_server(self) -> bool:
        """
        Start the OpenSERP server process.

        Returns:
            True if started successfully, False otherwise
        """
        try:
            logger.info(f"[OpenSERPManager] Starting OpenSERP server on {self.host}:{self.port}")

            # Get the directory containing the binary
            working_dir = self.openserp_binary_path.parent

            # Start server in background with explicit environment
            env = os.environ.copy()
            env['OPENSERP_HOST'] = self.host
            env['OPENSERP_PORT'] = str(self.port)

            self.process = subprocess.Popen(
                [
                    str(self.openserp_binary_path),
                    'serve',
                    '-a', self.host,
                    '-p', str(self.port),
                    '--verbose'  # Enable verbose logging for debugging
                ],
                cwd=working_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True  # Create new process group for clean shutdown
            )

            # Wait for server to be ready
            logger.info(f"[OpenSERPManager] Waiting for server startup (timeout: {self.startup_timeout}s)")
            if await self._wait_for_ready(self.startup_timeout):
                self.is_running = True
                self.restart_count = 0  # Reset restart count on successful start
                logger.info("[OpenSERPManager] ✓ Server started successfully")
                return True
            else:
                logger.error("[OpenSERPManager] Server failed to start within timeout")
                await self._kill_process()
                return False

        except Exception as e:
            logger.error(f"[OpenSERPManager] Failed to start server: {e}", exc_info=True)
            return False

    async def _wait_for_ready(self, timeout: float) -> bool:
        """
        Wait for server to be ready by polling health endpoint.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if server became ready, False if timeout
        """
        start_time = time.time()
        retry_delay = 0.5

        while time.time() - start_time < timeout:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.get(f"{self.base_url}/mega/engines")
                    if response.status_code == 200:
                        data = response.json()
                        engines = data.get('engines', [])
                        initialized = sum(1 for e in engines if e.get('initialized', False))

                        if initialized > 0:
                            logger.info(f"[OpenSERPManager] {initialized} engines initialized")
                            return True

            except (httpx.ConnectError, httpx.TimeoutException):
                # Server not ready yet, keep waiting
                pass
            except Exception as e:
                logger.debug(f"[OpenSERPManager] Health check error: {e}")

            await asyncio.sleep(retry_delay)

        return False

    async def check_health(self) -> bool:
        """
        Check if server is healthy.

        Returns:
            True if healthy, False otherwise
        """
        if not self.is_running or not self.process:
            return False

        # Check if process is still alive
        if self.process.poll() is not None:
            logger.warning("[OpenSERPManager] Process has exited unexpectedly")
            return False

        # Check HTTP health
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/mega/engines")
                if response.status_code == 200:
                    data = response.json()
                    engines = data.get('engines', [])
                    initialized = sum(1 for e in engines if e.get('initialized', False))
                    return initialized > 0
                return False

        except Exception as e:
            logger.debug(f"[OpenSERPManager] Health check failed: {e}")
            return False

    async def _monitor_health(self):
        """
        Background task that monitors server health and restarts on crashes.
        """
        logger.info(f"[OpenSERPManager] Health monitoring started (interval: {self.health_check_interval}s)")

        consecutive_failures = 0

        while self.is_running:
            await asyncio.sleep(self.health_check_interval)

            healthy = await self.check_health()

            if not healthy:
                consecutive_failures += 1
                logger.warning(f"[OpenSERPManager] Health check failed ({consecutive_failures} consecutive failures)")

                # Attempt restart after first failure
                if consecutive_failures >= 1:
                    logger.error("[OpenSERPManager] Server appears to be crashed, attempting restart...")

                    if self.restart_count < self.max_restart_attempts:
                        self.restart_count += 1
                        logger.info(f"[OpenSERPManager] Restart attempt {self.restart_count}/{self.max_restart_attempts}")

                        # Kill the old process
                        await self._kill_process()

                        # Wait a bit before restarting
                        await asyncio.sleep(2.0)

                        # Try to restart
                        success = await self._start_server()
                        if success:
                            logger.info("[OpenSERPManager] ✓ Server restarted successfully")
                            consecutive_failures = 0
                        else:
                            logger.error("[OpenSERPManager] ✗ Failed to restart server")
                    else:
                        logger.error(f"[OpenSERPManager] Max restart attempts ({self.max_restart_attempts}) exceeded, giving up")
                        self.is_running = False
                        break
            else:
                # Reset failure counter on successful health check
                if consecutive_failures > 0:
                    logger.info("[OpenSERPManager] Server recovered, health check passed")
                consecutive_failures = 0

    async def _kill_process(self):
        """Kill the OpenSERP process if running."""
        if self.process:
            try:
                # Try graceful shutdown first
                if self.process.poll() is None:
                    logger.info("[OpenSERPManager] Sending SIGTERM to process")
                    self.process.terminate()

                    # Wait up to 5 seconds for graceful shutdown
                    try:
                        self.process.wait(timeout=5.0)
                        logger.info("[OpenSERPManager] Process terminated gracefully")
                    except subprocess.TimeoutExpired:
                        logger.warning("[OpenSERPManager] Process did not terminate, sending SIGKILL")
                        self.process.kill()
                        self.process.wait(timeout=2.0)
                        logger.info("[OpenSERPManager] Process killed")

            except Exception as e:
                logger.error(f"[OpenSERPManager] Error killing process: {e}")

            finally:
                self.process = None

    async def stop(self):
        """
        Stop OpenSERP server and health monitoring.
        """
        logger.info("[OpenSERPManager] Stopping server...")

        self.is_running = False

        # Cancel monitoring task
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Kill server process
        await self._kill_process()

        logger.info("[OpenSERPManager] ✓ Server stopped")

    async def restart(self) -> bool:
        """
        Manually restart the server.

        Returns:
            True if restart succeeded, False otherwise
        """
        logger.info("[OpenSERPManager] Manual restart requested")
        await self.stop()
        await asyncio.sleep(2.0)
        return await self.start()


# Test function
async def test_manager():
    """Test the OpenSERP manager"""
    # Path to OpenSERP binary
    openserp_path = "/Users/saksham/Codes/Google-Search-Test/openserp/openserp"

    manager = OpenSERPManager(openserp_path)

    try:
        # Start server
        print("\n[Test] Starting OpenSERP server...")
        success = await manager.start()
        if not success:
            print("❌ Failed to start server")
            return

        print("✓ Server started successfully")

        # Wait and check health
        print("\n[Test] Waiting 10 seconds...")
        await asyncio.sleep(10)

        healthy = await manager.check_health()
        print(f"✓ Health check: {'PASS' if healthy else 'FAIL'}")

        # Keep running for a bit to test monitoring
        print("\n[Test] Server will continue running with health monitoring...")
        print("[Test] Press Ctrl+C to stop")

        # Wait indefinitely
        await asyncio.Event().wait()

    except KeyboardInterrupt:
        print("\n\n[Test] Shutting down...")

    finally:
        await manager.stop()
        print("✓ Test complete")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    asyncio.run(test_manager())
