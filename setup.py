#!/usr/bin/env python

# Copyright (c) 2018 Red Hat, Inc.
# All Rights Reserved.

from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="receptor-satellite",
    version="1.2.0",
    author="Red Hat Ansible",
    url="https://github.com/project-receptor/receptor-satellite",
    license="Apache",
    packages=find_packages(),
    long_description=long_description,
    long_description_content_type="text/markdown",
    # TODO: Require minimal version of insights-core once a version with
    #       playbook verifier is released
    install_requires=["aiohttp", "insights-core>=3.0.199"],
    zip_safe=False,
    entry_points={"receptor.worker": "receptor_satellite = receptor_satellite.worker"},
    classifiers=["Programming Language :: Python :: 3"],
    extras_require={"dev": ["pytest", "flake8", "pylint", "black"]},
)
