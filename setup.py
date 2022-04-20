from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in raviproducts/__init__.py
from raviproducts import __version__ as version

setup(
	name="raviproducts",
	version=version,
	description="Custom Features",
	author="VPS Consultancy",
	author_email="vivekchamp84@gmail.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
