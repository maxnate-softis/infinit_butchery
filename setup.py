"""
Infinit Butchery v3.0 - ERPNext App for Multi-tenant Butchery Business
Simplified architecture: 8 doctypes, 5 feature flags
"""
from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="infinit_butchery",
    version="3.0.0",
    description="Multi-tenant Butchery Management for ERPNext - v3.0 Simplified",
    author="Maxnate",
    author_email="dev@maxnate.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Framework :: Frappe",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
