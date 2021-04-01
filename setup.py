from setuptools import setup

setup(
    name='kernel_driver',
    version='0.0.1',
    url='https://github.com/davidbrochart/kernel_driver.git',
    author='David Brochart',
    author_email='david.brochart@gmail.com',
    description='A Jupyter kernel driver',
    require=[
        'pyzmq',
        'python-dateutil',
        'rich',
    ],
    extras_require={
        'test': [
            'xeus-python',
            'ipykernel',
            'pytest',
            'pytest-asyncio',
            'mypy',
            'flake8',
        ],
    },
)
