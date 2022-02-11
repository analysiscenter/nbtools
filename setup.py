"""
NBTools is a collection of tools for using in notebooks and inspect running notebooks.
"""
import re
from setuptools import setup, find_packages


with open('nbtools/__init__.py', 'r') as f:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE).group(1)


with open('README.md', 'r') as f:
    long_description = f.read()


setup(
    name='py-nbtools',
    packages=find_packages(),
    version=version,
    url='https://github.com/analysiscenter/nbtools',
    license='Apache License 2.0',
    author='Serget Tsimfer',
    author_email='sergeytsimfer@gmail.com',
    description='A collection of tools for using inside Jupyter Notebooks',
    long_description=long_description,
    long_description_content_type="text/markdown",
    zip_safe=False,
    platforms='any',
    install_requires=[
        'nvidia-ml-py3>=7.352',
        'blessed>=1.17',
        'psutil>=5.6',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: System :: Monitoring',
    ],
    entry_points={
        'console_scripts': [
            'nbstat = nbtools.nbstat.cli:nbstat',
            'nbwatch = nbtools.nbstat.cli:nbwatch',
            'devicestat = nbtools.nbstat.cli:devicestat',
            'devicewatch = nbtools.nbstat.cli:devicewatch',
        ],
    },
)
