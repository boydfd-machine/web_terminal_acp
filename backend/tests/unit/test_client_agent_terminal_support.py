import asyncio

from concurrent.futures import ThreadPoolExecutor

import contextlib

import errno

import os

import pty

import select

import shlex

import shutil

import subprocess

import threading

import time

from uuid import UUID

import pytest

import app.client_agent.terminal as client_terminal
import app.client_agent.terminal.private_ops as client_terminal_private_ops
import app.client_agent.terminal.public_ops as client_terminal_public_ops

from app.client_agent.terminal import (
    PTY_DRAIN_BUFFER_MAX_BYTES,
    PTY_OUTPUT_SEND_CHUNK_BYTES,
    ClientTerminalMultiplexer,
    _AttachedTerminal,
)

from app.client_agent.shell_hook import build_managed_shell_command

WINDOW_ID = UUID("87654321-4321-8765-4321-876543218765")

OTHER_WINDOW_ID = UUID("11111111-2222-3333-4444-555555555555")

__all__ = [name for name in globals() if not name.startswith("__")]
