#!/usr/bin/env python

from setuptools import setup, Extension
from setuptools.command.sdist import sdist as _sdist
from platform import python_implementation
import unittest


extensions = None

if python_implementation() == 'CPython':
    try:
        from Cython.Build import cythonize
        extensions = cythonize('eliot_profiler/**.pyx')
    except ImportError:
        extensions = [
            Extension(
                'eliot_profiler._call_graph',
                ['eliot_profiler/_call_graph.c']
            ),
            Extension(
                'eliot_profiler._stack_trace',
                ['eliot_profiler/_stack_trace.c']
            ),
        ]


class sdist(_sdist):
    def run(self):
        from Cython.Build import cythonize
        cythonize(['eliot_profiler/**.pyx'])
        _sdist.run(self)


setup(
    name='Eliot Profiler',
    version='0.1',
    description='A hybrid profiler / mini APM tool, that links in with Eliot',
    author='James Pickering',
    author_email='james_pic@hotmail.com',
    url='https://github.com/jamespic/eliot-profiler',
    packages=['eliot_profiler'],
    ext_modules=extensions,
    cmdclass={'sdist': sdist},
    install_requires=[
        'eliot',
        'monotonic',
        'pytz'
    ],
    setup_requires=[
        #'cython',
        'mock',
        'six'
    ],
    test_suite='tests'
)
