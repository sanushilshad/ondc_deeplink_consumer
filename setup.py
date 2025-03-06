import os
import setuptools

setuptools.setup(
    name="your_package",
    version=os.getenv("PACKAGE_VERSION", "0.1.0"),  # Use env var from CI/CD
    packages=setuptools.find_packages(),
)