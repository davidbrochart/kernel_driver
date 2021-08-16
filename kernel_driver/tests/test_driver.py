import os

import pytest
from kernel_driver import KernelDriver


@pytest.mark.asyncio
@pytest.mark.parametrize("kernel_name", ["xpython", "python3", "akernel"])
async def test_driver(kernel_name, capfd):
    timeout = 1
    kernelspec_path = (
        os.environ["CONDA_PREFIX"] + f"/share/jupyter/kernels/{kernel_name}/kernel.json"
    )
    kd = KernelDriver(kernelspec_path=kernelspec_path, log=False)
    await kd.start(startup_timeout=timeout)
    await kd.execute("print('Hello World!')", timeout=timeout)
    await kd.stop()

    out, err = capfd.readouterr()
    assert out == "Hello World!\n"
