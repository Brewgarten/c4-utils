import sys

from setuptools import setup, find_packages

import versioneer


needs_pytest = {"pytest", "test", "ptr"}.intersection(sys.argv)
pytest_runner = ["pytest-runner"] if needs_pytest else []

setup(
    name = "c4-utils",
    version = versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    packages = find_packages(),
    install_requires = [],
    setup_requires=[] + pytest_runner,
    tests_require=["pytest", "pytest-cov"],
    author = "IBM",
    author_email = "",
    description = "This is a collection of Python utility modules for project C4",
    license = "IBM",
    keywords = "python c4 utils",
    url = "",
)
