import os
import sys

from setuptools import setup, find_packages

VERSION = '0.4'

install_reqs = [
    'regex',
    'daemons',
    'pymysql',
    'requests',
    'termcolor',
    'python-statsd',
]

setup(name='punnsilm', 
    version=VERSION,
    description='Log handling toolkit',
    author='Sven Petai',
    author_email='hadara@bsd.ee',
    url='',
    license='MIT',
    packages=find_packages(),
    install_requires=install_reqs,
    scripts=[
        'scripts/punnsilm',
    ],
)
