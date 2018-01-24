import sys  # noqa
import subprocess  # noqa
from setuptools import setup, find_packages


commit = subprocess.Popen(
    'git rev-parse --short HEAD'.split(),
    stdout=subprocess.PIPE,
).stdout.read().decode('utf-8').strip()

setup(
    name='stellar-nice-body',
    version='0.1+%s' % commit,
    description='stellar nice-body; Trying to compose (ideal and safe) quorums',
    author='Spike^ekipS',
    author_email='spikeekips@gmail.com',
    license='GPLv3+',
    keywords='boscoin blockchainos stellar blockchain quorum python',
    install_requires=(
        'Jinja2',
        'stellar-base',
        'colorful',
        'PyYAML',
        'graphviz',
        'colorlog',
        'termcolor',
        'tabulate',
    ),
    package_dir={'': 'src'},
    packages=find_packages('src', exclude=('test',)),
    scripts=('script/stellar-nice-body',),
    zip_safe=False,
)
