from setuptools import setup, find_packages

setup(
    name="silentscan",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click",
        "numpy",
        "soundfile",
    ],
)

