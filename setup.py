"""
Infinit Butchery - ERPNext App for Multi-tenant Butchery Business
"""
from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="infinit_butchery",
    version="2.0.0",
    description="Multi-tenant Butchery Management for ERPNext",
    author="Maxnate",
    author_email="dev@maxnate.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
