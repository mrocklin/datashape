import os
from setuptools import setup, find_packages

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "DataShape",
    version = "0.0.1",
    author = "Continuum Analytics",
    author_email = "blaze-dev@continuum.io",
    description = ("A data description language."),
    license = "BSD",
    keywords = "data language",
    url = "http://packages.python.org/an_example_pypi_project",
    packages = find_packages(),
    long_description = read('README.md'),
    classifiers = [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development",
        "License :: OSI Approved :: BSD License",
    ],
)
