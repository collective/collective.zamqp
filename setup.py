from setuptools import setup, find_packages

setup(
    name='collective.zamqp',
    version='0.16.0',
    description="Asynchronous AMQP-integration for Plone (and Zope2)",
    long_description=(open("README.rst").read() + "\n" +
                      open("CHANGES.txt").read()),
    classifiers=[
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Topic :: Communications",
        "Topic :: System :: Distributed Computing",
        "Programming Language :: Python",
    ],
    keywords='',
    author='Asko Soukka',
    author_email='asko.soukka@iki.fi',
    url='http://github.com/collective/collective.zamqp',
    license='ZPL',
    packages=find_packages('src', exclude=['ez_setup']),
    package_dir={'': 'src'},
    namespace_packages=['collective'],
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'console_scripts': ['publishmsg = collective.zamqp.cli:main']
    },
    extras_require={
        'test': [
            'testfixtures',
            'rabbitfixture',
            'plone.testing',
            'plone.app.testing',
            'zope.configuration',
            'msgpack-python',
        ],
        'reload': [
            'z3c.unconfigure==1.0.1',  # required for full sauna.reload-support
        ],
        'docs': [
            'sphinx',
            'collective.sphinx.includedoc',
            'repoze.sphinx.autointerface',
            'sphinxcontrib-plantuml',
            'sphinxtogithub',
        ]
    },
    install_requires=[
        'setuptools',
        'Zope2',
        'ZODB3',
        'transaction',
        'zope.interface',
        'zope.component',
        'zope.publisher',
        'zope.event',
        'zope.processlifetime',
        'grokcore.component',
        'pika == 0.9.5',  # pika > 0.9.5 will require review and fixes
        'collective.monkeypatcher >= 1.1.1',  # patch a missing import in pika
        'zope.deprecation',
    ]
)
