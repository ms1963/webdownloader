# setup.py
from setuptools import setup

setup(
    name="webdownload",
    version="1.0",
    py_modules=["webdownload"],
    install_requires=[
        "requests",
        "beautifulsoup4",
        "python-magic"
    ],
    entry_points={
        "console_scripts": [
            "webdownload = webdownload:main",
        ]
    }
)
