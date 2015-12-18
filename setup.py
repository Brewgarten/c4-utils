from setuptools import setup, find_packages

# get version without importing
versionFileName = "c4/utils/__init__.py"
packageVersion = None

try:
    import imp
    import os
    currentDirectory = os.path.dirname(os.path.abspath(__file__))
    baseDirectory = os.path.dirname(currentDirectory)
    versioningModulePath = os.path.join(baseDirectory, "versioning.py")
    setup = imp.load_source("versioning", versioningModulePath).versionedSetup
except:
    import re
    with open(versionFileName) as f:
        match = re.search("__version__\s*=\s*['\"](.*)['\"]", f.read())
        packageVersion = match.group(1)

setup(
    name = "c4-utils",
    version = packageVersion,
    versionFileName = versionFileName,
    packages = find_packages(),
    install_requires = [],
    author = "IBM",
    author_email = "",
    description = "This is a collection of Python utility modules for project C4",
    license = "IBM",
    keywords = "python c4 utils",
    url = "",
)
