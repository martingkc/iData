from logging import getLogger, Logger
from subprocess import Popen, PIPE
import requests
from io import StringIO
import re
import json
import errno
import os
import signal
import functools

from typing import List, Callable, Dict, Union, Tuple
from rclone_python import rclone
from rclone_python.remote_types import RemoteTypes
from rclone_python.utils import run_rclone_cmd

import document_collector.globals as G

logger = getLogger(__name__)


def _format_rclone_remote_name(remote: str) -> str:
    """Helper function to format a remote name with a trailing colon if not already present"""
    return remote.replace(" ", "_")


def _get_readable_remote_name(remote: str) -> str:
    """Helper function to get a readable remote name without trailing colon"""

    return remote.rstrip(":").replace("_", " ")


def _get_remote_name_with_colon(remote: str) -> str:
    """Helper function to get a remote name with trailing colon"""
    remote = _format_rclone_remote_name(
        remote
    )  # Ensure the name is formatted correctly
    return remote if remote.endswith(":") else remote + ":"


## CRUD operations for rclone remotes
def create_rclone_remote(name: str, remote_type: str) -> None:
    """Create a new rclone remote with the given name and type"""
    name = _format_rclone_remote_name(name)  # Ensure the name is formatted correctly
    rclone.create_remote(name, RemoteTypes(remote_type))


def check_rclone_remote(name: str) -> bool:
    """Check if the rclone remote with the given name is configured correctly"""
    name = _get_remote_name_with_colon(
        name
    )  # Rclone remotes are referenced with a trailing colon
    return rclone.check_remote_existing(name)


## Remote navigation operations
def list_rclone_remotes() -> List[str]:
    """List all configured rclone remotes without trailing colons"""
    return [_get_readable_remote_name(remote) for remote in rclone.get_remotes()]


def list_rclone_remote_contents(
    remote_name: str,
    path: str,
    max_depth: int | None = None,
    dirs_only: bool = False,
    files_only: bool = False,
) -> List[dict]:
    """List the contents of a specific rclone remote"""
    remote_name = _get_remote_name_with_colon(remote_name)  # Ensure no trailing colon
    return rclone.ls(
        path=f"{remote_name}{path}",
        max_depth=max_depth,
        dirs_only=dirs_only,
        files_only=files_only,
    )


## Sync operations


def add_cron_job(cmd: str, interval_minutes: int) -> None:
    """Add a cron job for periodical sync between source and destination paths using rclone"""
    # Note: This is a placeholder implementation. Actual cron job management would require
    # integration with the system's cron service, which may involve writing to the crontab file.


class RcloneSyncLogger:
    """Logger class for rclone sync operations"""

    def __init__(
        self,
        _logger: Logger,
        remote_name: str,
        source_path: str,
        destination_path: str,
    ) -> None:
        self.logger = _logger
        self.remote_name = remote_name
        self.source_path = source_path
        self.destination_path = destination_path

    def log(self, *args, **kwargs) -> None:
        self.logger.info(
            "Rclone Sync [%s]%s: %s\n progress info: %s",
            self.remote_name,
            self.source_path,
            self.destination_path,
            *args,
            **kwargs,
        )


def rclone_sync_paths(
    remote_name: str,
    source_path: str,
    destination_path: str,
    listener: Callable[[Dict], None] | None = None,
    do_schedule_periodical_sync: bool = False,
) -> bool:
    """Copy files from source to destination using rclone without deleting existing destination files."""
    try:
        source_path = f"{_get_remote_name_with_colon(remote_name)}{source_path}"
        # command = f"rclone sync {source_path} {destination_path}"
        rclone.copy(
            src_path=source_path,
            dest_path=destination_path,
            listener=listener,
        )
    except Exception as e:
        # Handle exceptions (e.g., log them)
        logger.error("Error occurred while syncing: %s", e)
        return False
    return True
    # Note: schedule_periodical_sync is not implemented in this function.


def rclone_sync_to_nas(
    remote_name: str,
    source_path: str,
    listener: Callable[[Dict], None] | None = None,
    schedule_periodical_sync: bool = False,
) -> bool:
    """Sync files from source to destination using rclone, a listener is used to log files
    TODO : use listener to log progress in a more structured way"""
    return rclone_sync_paths(
        remote_name=remote_name,
        source_path=source_path,
        destination_path=G.NAS_DOCUMENTS_FOLDER_PATH,
        listener=listener,
        do_schedule_periodical_sync=schedule_periodical_sync,  # No scheduling for NAS sync
    )


def run_rclone_authorize_command(remote_type: str) -> Union[str, None]:
    """Run the rclone authorize command for the given remote"""
    stdout: str = ""
    stderr: str = ""
    remote_type = RemoteTypes(remote_type).value
    command = f'authorize "{remote_type}"'
    # this command raises errors so we catch them
    token_start_delimiter = "Paste the following into your remote machine --->"
    token_end_delimiter = "<---End paste"
    try:
        stdout, stderr = run_rclone_cmd(command)
        # extract the token from stdout
        # remove newlines and carriage returns
        stdout_cleaned = stdout.replace("\n", "").replace("\r", "")
        # use regex to extract the token between the delimiters
        token_pattern = re.compile(
            rf"{token_start_delimiter}(.*?){token_end_delimiter}"
        )
        match = token_pattern.search(stdout_cleaned)
        if match:
            return match.group(1).strip()
    except Exception as e:
        logger.error("Error occurred while authorizing remote '%s': %s", remote_type, e)
        return None
    return None


class TimeoutError(Exception):
    pass


def timeout(seconds=10, error_message=os.strerror(errno.ETIME)):
    def decorator(func):
        def _handle_timeout(signum, frame):
            raise TimeoutError(error_message)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wrapper

    return decorator


@timeout(1)
def read_prompt_timeout(stdout: StringIO, output: list) -> list:
    """Read a line from stdout with a timeout"""
    for line in stdout:
        print(f"Read line: {line.strip()}")
        output.append(line)
    return output


def read_prompt(stdout: StringIO) -> str:
    """Read a line from stdout with a timeout"""
    output = []
    try:
        output = read_prompt_timeout(stdout, output)
    except TimeoutError:
        pass
    return "".join(output)


def terminal_prompt_routine(
    command: List[str], prompt_answer_lists: List[Tuple[Tuple[str, str]]]
) -> Union[Tuple[str, str], None]:
    """Run the rclone configure command, this,
    Args
        prompt_answer_dict: A dictionary mapping prompts to answers."""

    with Popen(command, stdin=PIPE, stdout=PIPE, universal_newlines=True) as p:
        for prompt_answer_list in prompt_answer_lists:
            output = read_prompt(p.stdout)
            found_prompt = False
            for prompt, answer in prompt_answer_list:
                if prompt in output:
                    found_prompt = True
                    print(f"Prompt detected: {prompt}")
                    # write answer to stdin buffer
                    p.stdin.write(answer + "\n")
                    # send the answer
                    p.stdin.flush()
                    # get next prompt and answer
                    break
            if not found_prompt:
                print(f"Unexpected output: {output}")  # print other output lines
                break
    print("Rclone configure command completed.")
    return None


def configure_rclone_headless_remote(
    name: str, remote_type: str, config_token: str = "HEADLESS_AUTH_CODE"
) -> Union[Tuple[str, str], None]:
    """Configure a headless rclone remote"""
    stdout: str = ""
    stderr: str = ""
    command = ["rclone", "config"]
    "No remotes found, make a new one?"
    prompt_answer_lists = [
        (("Current remotes:", "n"), ("No remotes found, make a new one?", "n")),
        (("Enter name for new remote.", name),),
        (("Option Storage", RemoteTypes(remote_type).value),),
        (("Option client_id.", ""),),
        (("Option client_secret.", ""),),
        (("Option scope.", "1"),),
        (("Option service_account_file.", ""),),
        (("Edit advanced config?", "n"),),
        (("Use web browser to automatically authenticate rclone with remote?", "n"),),
        (("Option config_token.", config_token),),
        (("Configure this as a Shared Drive (Team Drive)?", "n"),),
        (("Configuration complete.", "y"),),
    ]
    # this command raises errors so we catch them
    try:
        terminal_prompt_routine(command, prompt_answer_lists)
        return stdout, stderr
    except Exception as e:
        logger.error("Error occurred while configuring headless remote: %s", e)
        return None
    return None


def rclone_configure_headless_routine(config_token: str, name: str, remote_type: str):
    """Rclone headless configuration routine to get the config token URL"""
    name = _format_rclone_remote_name(name)  # Ensure the name is formatted correctly
    configure_rclone_headless_remote(
        name=name, remote_type=remote_type, config_token=config_token
    )
