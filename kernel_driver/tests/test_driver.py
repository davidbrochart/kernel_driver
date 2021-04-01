import os

import pytest
from kernel_driver import KernelDriver


@pytest.mark.asyncio
@pytest.mark.parametrize("kernel_name", ["xpython", "python3"])
async def test_driver(kernel_name, capfd):
    timeout = 1
    kernel_spec_path = (
        os.environ["CONDA_PREFIX"] + f"/share/jupyter/kernels/{kernel_name}/kernel.json"
    )
    kd = KernelDriver(kernel_spec_path, log=False)
    await kd.start(timeout)
    await kd.execute("print('Hello World!')", timeout)
    await kd.stop()

    out, err = capfd.readouterr()
    assert out == "Hello World!\n"
