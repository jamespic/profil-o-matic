#!/usr/bin/env python

from setuptools import setup, Extension, find_packages
from setuptools.command.sdist import sdist as _sdist
from platform import python_implementation, platform, system
import unittest


extensions = None

if python_implementation() == 'CPython':
    supports_fast_monotonic = system() == 'Linux'
    try:
        from Cython.Build import cythonize
        extensions = cythonize([
            'src/profilomatic/_call_graph.pyx',
            'src/profilomatic/_stack_trace.pyx'
        ])
        if supports_fast_monotonic:
            extensions.extend(cythonize('src/profilomatic/fast_monotonic.pyx'))
    except ImportError:
        extensions = [
            Extension(
                'profilomatic._call_graph',
                ['src/profilomatic/_call_graph.c']
            ),
            Extension(
                'profilomatic._stack_trace',
                ['src/profilomatic/_stack_trace.c']
            )
        ]
        if supports_fast_monotonic:
            extensions.append(Extension(
                'profilomatic.fast_monotonic',
                ['src/profilomatic/fast_monotonic.c']
            ))


class sdist(_sdist):
    def run(self):
        from Cython.Build import cythonize
        cythonize(['src/profilomatic/**.pyx'])
        _sdist.run(self)


setup(
    name='Profil-o-matic',
    version='0.2.0',
    description='A hybrid profiler / mini APM tool, that measures line-level performance of your business-domain actions',
    author='James Pickering',
    author_email='james_pic@hotmail.com',
    license='MIT',
    url='https://github.com/jamespic/profil-o-matic',
    packages=find_packages('src'),
    package_dir={'':'src'},
    ext_modules=extensions,
    cmdclass={'sdist': sdist},
    install_requires=[
        'monotonic',
        'pytz',
        'six'
    ],
    setup_requires=[
        'cython',
    ],
    tests_require=[
        'mock'
    ],
    extras_require={
        'eliot': ['eliot>=0.9.0']
    },
    test_suite='tests'
)
