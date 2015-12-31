from setuptools import setup, find_packages

import versioneer

setup(
    name = "c4-utils",
    version = versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    packages = find_packages(),
    install_requires = [],
    author = "IBM",
    author_email = "",
    description = "This is a collection of Python utility modules for project C4",
    license = "IBM",
    keywords = "python c4 utils",
    url = "",
)
