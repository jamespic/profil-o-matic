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
            'src/eliot_profiler/_call_graph.pyx',
            'src/eliot_profiler/_stack_trace.pyx'
        ])
        if supports_fast_monotonic:
            extensions.extend(cythonize('src/eliot_profiler/fast_monotonic.pyx'))
    except ImportError:
        extensions = [
            Extension(
                'eliot_profiler._call_graph',
                ['src/eliot_profiler/_call_graph.c']
            ),
            Extension(
                'eliot_profiler._stack_trace',
                ['src/eliot_profiler/_stack_trace.c']
            )
        ]
        if supports_fast_monotonic:
            extensions.append(Extension(
                'eliot_profiler.fast_monotonic',
                ['src/eliot_profiler/fast_monotonic.c']
            ))


class sdist(_sdist):
    def run(self):
        from Cython.Build import cythonize
        cythonize(['src/eliot_profiler/**.pyx'])
        _sdist.run(self)


setup(
    name='Eliot Profiler',
    version='0.1',
    description='A hybrid profiler / mini APM tool, that links in with Eliot',
    author='James Pickering',
    author_email='james_pic@hotmail.com',
    url='https://github.com/jamespic/eliot-profiler',
    packages=find_packages('src'),
    package_dir={'':'src'},
    ext_modules=extensions,
    cmdclass={'sdist': sdist},
    install_requires=[
        'eliot',
        'monotonic',
        'pytz'
    ],
    setup_requires=[
        'cython',
    ],
    tests_require=[
        'mock',
        'six'
    ],
    test_suite='tests'
)
