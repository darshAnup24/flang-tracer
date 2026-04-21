from setuptools import setup, find_packages

setup(
    name='flang-tracer',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'click',
        'rich',
        'pytest'
    ],
    entry_points='''
        [console_scripts]
        ftrace=ftrace.cli:cli
    ''',
)
