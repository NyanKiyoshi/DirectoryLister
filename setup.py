from setuptools import setup, find_packages
from sys import version_info

if version_info <= (2, 6) or version_info.major > 2:
    raise Exception('This project requires a Python2 version greater or equal than 2.7.')

with open('README.md') as f:
    README = f.read()

PROJECT_NAME = 'directoryLister'

with open('%s/VERSION' % PROJECT_NAME) as f:
    VERSION = f.read().strip()

setup(
    name=PROJECT_NAME,
    version=VERSION,
    description=README.split('\n')[2],
    long_description=README,
    author_email='wibberry@gmail.com',
    url='http://github.com/NyanKiyoshi/%s' % PROJECT_NAME,
    license='MIT',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    classifiers=[
        # https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 2 :: Only',
        'Topic :: Software Development :: Libraries',
        'Topic :: Utilities'
    ]
)
