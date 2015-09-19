#!/usr/bin/env python3

import os
import re
import sys

from setuptools import find_packages, setup


if sys.hexversion < 0x3030000:
  print("Python version %s is unsupported, >= 3.3.0 is needed" % (".".join(map(str, sys.version_info[:3]))))
  exit(1)

with open(os.path.join("canalplus", "__init__.py"), "rt") as f:
  version = re.search("__version__ = \"([^\"]+)\"", f.read()).group(1)

with open("requirements.txt", "rt") as f:
  requirements = f.read().splitlines()
  # require enum34 if enum module is missing (Python 3.3)
  try:
    import enum
  except ImportError:
    requirements.append("enum34")

try:
  import pypandoc
  readme = pypandoc.convert("README.md", "rst")
except ImportError:
  with open("README.md", "rt") as f:
    readme = f.read()

setup(name="canalplus",
      version=version,
      author="desbma",
      packages=find_packages(),
      entry_points={"console_scripts": ["canalplus = canalplus:cl_main"]},
      test_suite="tests",
      install_requires=requirements,
      description="Parcourir/visionner/télécharger les vidéos mises en ligne par la chaine Canal+",
      long_description=readme,
      url="https://github.com/desbma/canalplus",
      download_url="https://github.com/desbma/canalplus/archive/%s.tar.gz" % (version),
      keywords=["canal+", "canal", "canalplus", "video", "vidéo", "download", "télécharger"],
      classifiers=["Development Status :: 5 - Production/Stable",
                   "Environment :: Console",
                   "Intended Audience :: Developers",
                   "Intended Audience :: End Users/Desktop",
                   "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
                   "Natural Language :: English",
                   "Natural Language :: French",
                   "Operating System :: OS Independent",
                   "Programming Language :: Python",
                   "Programming Language :: Python :: 3",
                   "Programming Language :: Python :: 3 :: Only",
                   "Programming Language :: Python :: 3.3",
                   "Programming Language :: Python :: 3.4",
                   "Programming Language :: Python :: 3.5",
                   "Topic :: Multimedia :: Video",
                   "Topic :: Utilities"])
