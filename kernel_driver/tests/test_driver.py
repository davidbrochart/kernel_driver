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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kernel_name", ["akernel"]
)  # xpython and python3 don't support message-based restart
async def test_restart(kernel_name, capfd):
    timeout = 1
    kernelspec_path = (
        os.environ["CONDA_PREFIX"] + f"/share/jupyter/kernels/{kernel_name}/kernel.json"
    )
    kd = KernelDriver(kernelspec_path=kernelspec_path, log=False)
    await kd.start(startup_timeout=timeout)
    await kd.execute("print('before restart')", timeout=timeout)
    await kd.restart(startup_timeout=timeout)
    await kd.execute("print('after restart')", timeout=timeout)
    await kd.stop()

    out, err = capfd.readouterr()
    assert out == "before restart\nafter restart\n"
