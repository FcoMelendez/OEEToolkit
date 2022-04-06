from setuptools import setup, find_packages

with open("README.md", "r") as readme_file:
    readme = readme_file.read()

requirements = ["requests>=2"]

setup(
    name="OEEToolkit",
    version="0.0.5",
    author="Francisco Melendez",
    author_email="fco.melendez.f@gmail.com",
    description="A package to calculate the OEE for Industry 4.0 Assets",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/FcoMelendez/OEEToolkit",
    packages=find_packages(),
    install_requires=requirements,
    classifiers=[
        "Programming Language :: Python :: 3.7",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    ],
)
