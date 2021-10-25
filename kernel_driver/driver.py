import os
import sys
import time
import uuid
import asyncio
from typing import Tuple, List, Dict, Any, Optional, cast

from zmq.sugar.socket import Socket
from rich.console import Console
from rich.live import Live
from rich.tree import Tree
from rich.status import Status

from .message import create_message, serialize, deserialize
from .connect import (
    write_connection_file as _write_connection_file,
    read_connection_file,
    launch_kernel,
    connect_channel,
    cfg_t,
)
from .kernelspec import find_kernelspec

success = "[green]✔[/green] "
failure = "[red]✘[/red] "

DELIM = b"<IDS|MSG>"


def deadline_to_timeout(deadline: float) -> float:
    return max(0, deadline - time.time())


def feed_identities(msg_list: List[bytes]) -> Tuple[List[bytes], List[bytes]]:
    idx = msg_list.index(DELIM)
    return msg_list[:idx], msg_list[idx + 1 :]  # noqa


def send_message(msg: Dict[str, Any], sock: Socket, key: str) -> None:
    to_send = serialize(msg, key)
    sock.send_multipart(to_send, copy=True)


async def receive_message(
    sock: Socket, timeout: float = float("inf")
) -> Optional[Dict[str, Any]]:
    timeout *= 1000  # in ms
    ready = await sock.poll(timeout)
    if ready:
        msg_list = await sock.recv_multipart()
        idents, msg_list = feed_identities(msg_list)
        return deserialize(msg_list)
    return None


def _output_hook_default(msg: Dict[str, Any]) -> None:
    """Default hook for redisplaying plain-text output"""
    msg_type = msg["header"]["msg_type"]
    content = msg["content"]
    if msg_type == "stream":
        stream = getattr(sys, content["name"])
        stream.write(content["text"])
    elif msg_type in ("display_data", "execute_result"):
        sys.stdout.write(content["data"].get("text/plain", ""))
    elif msg_type == "error":
        print("\n".join(content["traceback"]), file=sys.stderr)


class KernelDriver:
    def __init__(
        self,
        kernel_name: str = "",
        kernelspec_path: str = "",
        connection_file: str = "",
        write_connection_file: bool = True,
        capture_kernel_output: bool = True,
        log: bool = True,
        console: Console = None,
    ) -> None:
        self.log = log
        self.console = console
        self.capture_kernel_output = capture_kernel_output
        self.kernelspec_path = kernelspec_path or find_kernelspec(kernel_name)
        if not self.kernelspec_path:
            raise RuntimeError(
                "Could not find a kernel, maybe you forgot to install one?"
            )
        if write_connection_file:
            self.connection_file_path, self.connection_cfg = _write_connection_file(
                connection_file
            )
        else:
            self.connection_file_path = connection_file
            self.connection_cfg = read_connection_file(connection_file)
        self.key = cast(str, self.connection_cfg["key"])
        self.session_id = uuid.uuid4().hex
        self.msg_cnt = 0
        self.execute_requests: Dict[str, Any] = {}
        self.channel_tasks: List[asyncio.Task] = []

    async def restart(self, startup_timeout: float = float("inf")) -> None:
        if self.log:
            status0 = Status("Restarting kernel")
            tree0 = Tree(status0)  # type: ignore
            live = Live(tree0, refresh_per_second=10, console=self.console)
            live.start()
            status1 = Status("Shutting down kernel")
            tree1 = tree0.add(status1)  # type: ignore
        for task in self.channel_tasks:
            task.cancel()
        msg = create_message("shutdown_request", content={"restart": True})
        send_message(msg, self.control_channel, self.key)
        while True:
            msg = cast(Dict[str, Any], await receive_message(self.control_channel))
            if msg["msg_type"] == "shutdown_reply" and msg["content"]["restart"]:
                break
        if self.log:
            tree1.label = success + status1.status  # type: ignore
            status1 = Status("Waiting for kernel ready")
            tree1 = tree0.add(status1)  # type: ignore
        else:
            tree1 = None  # type: ignore
        await self._wait_for_ready(startup_timeout, tree1)
        if self.log:
            tree1.label = success + status1.status  # type: ignore
            tree0.label = success + status0.status  # type: ignore
            live.stop()
        self.channel_tasks = []
        self.listen_channels()

    async def start(self, startup_timeout: float = float("inf")) -> None:
        if self.log:
            status0 = Status("Starting kernel")
            tree0 = Tree(status0)  # type: ignore
            live = Live(tree0, refresh_per_second=10, console=self.console)
            live.start()
            status1 = Status("Launching kernel")
            tree1 = tree0.add(status1)  # type: ignore
        self.kernel_process = await launch_kernel(
            self.kernelspec_path, self.connection_file_path, self.capture_kernel_output
        )
        self.connect_channels()
        if self.log:
            tree1.label = success + status1.status  # type: ignore
            status1 = Status("Waiting for kernel ready")
            tree1 = tree0.add(status1)  # type: ignore
        else:
            tree1 = None  # type: ignore
        await self._wait_for_ready(startup_timeout, tree1)
        if self.log:
            tree1.label = success + status1.status  # type: ignore
            tree0.label = success + status0.status  # type: ignore
            live.stop()
        self.listen_channels()

    def connect_channels(self, connection_cfg: cfg_t = None):
        connection_cfg = connection_cfg or self.connection_cfg
        self.shell_channel = connect_channel("shell", connection_cfg)
        self.control_channel = connect_channel("control", connection_cfg)
        self.iopub_channel = connect_channel("iopub", connection_cfg)

    def listen_channels(self):
        self.channel_tasks.append(asyncio.create_task(self.listen_iopub()))
        self.channel_tasks.append(asyncio.create_task(self.listen_shell()))

    async def stop(self) -> None:
        self.kernel_process.kill()
        if self.log:
            status0 = Status("Stopping kernel")
            tree0 = Tree(status0)  # type: ignore
            live = Live(tree0, refresh_per_second=10, console=self.console)
            live.start()
            tree0.add("Sent SIGKILL to process")
            status1 = Status("Waiting for the process to terminate")
            tree1 = tree0.add(status1)  # type: ignore
        await self.kernel_process.wait()
        os.remove(self.connection_file_path)
        if self.log:
            tree0.label = success + status0.status  # type: ignore
            tree1.label = success + status1.status  # type: ignore
            live.stop()
        for task in self.channel_tasks:
            task.cancel()

    async def listen_iopub(self):
        while True:
            msg = await receive_message(self.iopub_channel)  # type: ignore
            msg_id = msg["parent_header"].get("msg_id")
            if msg_id in self.execute_requests.keys():
                self.execute_requests[msg_id]["iopub_msg"] = msg
                self.execute_requests[msg_id]["iopub_event"].set()

    async def listen_shell(self):
        while True:
            msg = await receive_message(self.shell_channel)  # type: ignore
            msg_id = msg["parent_header"].get("msg_id")
            if msg_id in self.execute_requests.keys():
                self.execute_requests[msg_id]["shell_msg"] = msg
                self.execute_requests[msg_id]["shell_event"].set()

    async def execute(
        self,
        code: str,
        timeout: float = float("inf"),
        msg_id: str = "",
        wait_for_executed: bool = True,
    ) -> None:
        if self.log:
            status0 = Status("Executing code")
            tree0 = Tree(status0)  # type: ignore
            live = Live(tree0, refresh_per_second=10, console=self.console)
            live.start()
        content = {"code": code, "silent": False}
        msg = create_message(
            "execute_request", content, session_id=self.session_id, msg_cnt=self.msg_cnt
        )
        if msg_id:
            msg["header"]["msg_id"] = msg_id
        else:
            msg_id = msg["header"]["msg_id"]
        self.msg_cnt += 1
        send_message(msg, self.shell_channel, self.key)
        if self.log:
            tree0.add("Sent execute request")
        if wait_for_executed:
            deadline = time.time() + timeout
            self.execute_requests[msg_id] = {
                "iopub_event": asyncio.Event(),
                "shell_event": asyncio.Event(),
            }
            if self.log:
                status1 = Status("Waiting for idle execution state")
                tree1 = tree0.add(status1)  # type: ignore
            while True:
                try:
                    await asyncio.wait_for(
                        self.execute_requests[msg_id]["iopub_event"].wait(),
                        deadline_to_timeout(deadline),
                    )
                except asyncio.TimeoutError:
                    error_message = f"Kernel didn't respond in {timeout} seconds"
                    if self.log:
                        tree0.label = failure + cast(str, status0.status)
                        tree1.label = failure + cast(str, status1.status)
                        tree0.add(f"[red]{error_message}")
                    raise RuntimeError(error_message)
                msg = self.execute_requests[msg_id]["iopub_msg"]
                _output_hook_default(msg)
                if (
                    msg["header"]["msg_type"] == "status"
                    and msg["content"]["execution_state"] == "idle"
                ):
                    if self.log:
                        tree1.label = success + status1.status  # type: ignore
                    break
                self.execute_requests[msg_id]["iopub_event"].clear()
            if self.log:
                status1 = Status("Waiting for execute reply")
                tree1 = tree0.add(status1)  # type: ignore
            try:
                await asyncio.wait_for(
                    self.execute_requests[msg_id]["shell_event"].wait(),
                    deadline_to_timeout(deadline),
                )
            except asyncio.TimeoutError:
                error_message = f"Kernel didn't respond in {timeout} seconds"
                if self.log:
                    tree0.label = failure + cast(str, status0.status)
                    tree1.label = failure + cast(str, status1.status)
                    tree0.add(f"[red]{error_message}")
                raise RuntimeError(error_message)
            msg = self.execute_requests[msg_id]["shell_msg"]
            if self.log:
                tree1.label = success + status1.status  # type: ignore
            del self.execute_requests[msg_id]
        if self.log:
            tree0.label = success + status0.status  # type: ignore
            live.stop()

    async def _wait_for_ready(self, timeout, tree):
        deadline = time.time() + timeout
        new_timeout = timeout
        while True:
            msg = create_message(
                "kernel_info_request", session_id=self.session_id, msg_cnt=self.msg_cnt
            )
            self.msg_cnt += 1
            send_message(msg, self.shell_channel, self.key)
            if self.log:
                tree.add("Sent kernel info request")
                status0 = Status("Waiting for kernel info reply")
                tree0 = tree.add(status0)
            msg = await receive_message(self.shell_channel, new_timeout)
            if msg is None:
                error_message = f"Kernel didn't respond in {timeout} seconds"
                if self.log:
                    tree0.label = failure + status0.status
                raise RuntimeError(error_message)
            if msg["msg_type"] == "kernel_info_reply":
                if self.log:
                    tree0.label = success + status0.status
                    status1 = Status("Waiting for IOPub to connect")
                    tree1 = tree.add(status1)
                msg = await receive_message(self.iopub_channel, 0.2)
                if msg is None:
                    if self.log:
                        tree1.label = failure + status1.status
                        tree.add("IOPub not connected, start over")
                else:
                    if self.log:
                        tree1.label = success + status1.status
                    break
            new_timeout = deadline_to_timeout(deadline)
