from logging import getLogger
import re
from typing import Union
from rclone_python.remote_types import RemoteTypes
from rclone_python.utils import run_rclone_cmd


logger = getLogger(__name__)


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
