#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = ['Click>=7.0', ]

test_requirements = ['pytest>=3', ]

setup(
    author="Nikhil Arora",
    author_email='nikhiljarora@outlook.com',
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description="Bittorrent client written written for learning purposes.",
    entry_points={
        'console_scripts': [
            'bittorrent_client=bittorrent_client.cli:main',
        ],
    },
    install_requires=requirements,
    license="MIT license",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='bittorrent_client',
    name='bittorrent_client',
    packages=find_packages(include=['bittorrent_client', 'bittorrent_client.*']),
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/nikhiljarora/bittorrent_client',
    version='0.1.0',
    zip_safe=False,
)
