import os
import asyncio

import pytest
from kernel_driver import write_connection_file, launch_kernel


@pytest.mark.asyncio
async def test_driver():
    connection_file_path, cfg = write_connection_file()
    assert os.path.exists(connection_file_path)
    assert cfg["ip"] == "127.0.0.1"

    kernel_spec_path = (
        os.environ["CONDA_PREFIX"] + "/share/jupyter/kernels/xpython/kernel.json"
    )
    p = await launch_kernel(kernel_spec_path, connection_file_path)
    await asyncio.sleep(1)
    p.kill()
