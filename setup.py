# coding=utf-8
import io
import os

from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
with io.open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="OctoPrint-NavLink",
    version="1.2.0",
    description="Adds a link button with a configurable URL and icon to OctoPrint's top navigation bar.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="mikulik86",
    url="https://github.com/mikulik86/OctoPrint-NavLink",
    license="MIT",
    packages=["octoprint_navlink"],
    package_data={
        "octoprint_navlink": [
            "templates/*.jinja2",
            "static/js/*.js",
            "static/css/*.css",
        ]
    },
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.7,<4",
    classifiers=[
        "Framework :: OctoPrint",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    entry_points={"octoprint.plugin": ["navlink = octoprint_navlink"]},
)
