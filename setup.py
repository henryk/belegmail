"""LexOffice Tools: setup module

Verwendung auf eigene Gefahr
"""
from codecs import open
from os import path

from setuptools import find_packages, setup

here = path.abspath(path.dirname(__file__))

with open(path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="belegmail",
    version="0.0.1",
    description="Holt Attachments und legt sie ab",
    long_description=long_description,
    author="Henryk Plötz",
    author_email="henryk+belegmail@digitalwolff.de",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
    ],
    keywords="email buchhaltung belege",
    packages=find_packages(exclude=["contrib", "docs", "tests"]),
    install_requires=[
        "requests",
        "PyYAML",
        "imapclient",
        "python-magic",
        "pysigset",
        "filelock",
    ],
    extras_require={},
    package_data={},
    data_files=[],
    entry_points={"console_scripts": ["belegmail=belegmail:main.main",],},
)
