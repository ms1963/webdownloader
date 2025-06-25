# setup.py
from setuptools import setup

setup(
    name="wd",
    version="1.0",
    py_modules=["wd"],
    install_requires=[
        "requests",
        "beautifulsoup4",
        "python-magic"
    ],
    entry_points={
        "console_scripts": [
            "wd = wd:main",
        ]
    }
)
