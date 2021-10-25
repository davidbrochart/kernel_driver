import os

import pytest
from kernel_driver import KernelDriver


TIMEOUT = 3


@pytest.mark.asyncio
@pytest.mark.parametrize("kernel_name", ["xpython", "python3", "akernel"])
async def test_driver(kernel_name, capfd):
    kernelspec_path = (
        os.environ["CONDA_PREFIX"] + f"/share/jupyter/kernels/{kernel_name}/kernel.json"
    )
    kd = KernelDriver(kernelspec_path=kernelspec_path, log=False)
    await kd.start(startup_timeout=TIMEOUT)
    await kd.execute("print('Hello World!')", timeout=TIMEOUT)
    await kd.stop()

    out, err = capfd.readouterr()
    assert out == "Hello World!\n"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kernel_name", ["akernel"]
)  # xpython and python3 don't support message-based restart
async def test_restart(kernel_name, capfd):
    kernelspec_path = (
        os.environ["CONDA_PREFIX"] + f"/share/jupyter/kernels/{kernel_name}/kernel.json"
    )
    kd = KernelDriver(kernelspec_path=kernelspec_path, log=False)
    await kd.start(startup_timeout=TIMEOUT)
    await kd.execute("print('before restart')", timeout=TIMEOUT)
    await kd.restart(startup_timeout=TIMEOUT)
    await kd.execute("print('after restart')", timeout=TIMEOUT)
    await kd.stop()

    out, err = capfd.readouterr()
    assert out == "before restart\nafter restart\n"
