from setuptools import setup

setup(
    name="kernel_driver",
    version="0.0.5",
    url="https://github.com/davidbrochart/kernel_driver.git",
    author="David Brochart",
    author_email="david.brochart@gmail.com",
    description="A Jupyter kernel driver",
    packages=["kernel_driver"],
    python_requires=">=3.7",
    install_requires=[
        "pyzmq",
        "python-dateutil",
        "rich",
    ],
    extras_require={
        "test": [
            "xeus-python",
            "ipykernel",
            "pytest",
            "pytest-asyncio",
            "mypy",
            "flake8",
        ],
    },
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)
