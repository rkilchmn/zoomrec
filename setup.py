from setuptools import setup, find_packages

setup(
    name="zoomrec",
    version="0.1",
    packages=find_packages(include=["client", "server", "shared"]),
    python_requires='>=3.6',
)
