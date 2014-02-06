from setuptools import setup, find_packages

setup( name='cqrs',
    version = '0.0.1',
    description = 'CQRS inspired helpers for Django / Meteor',
    author = 'Daryl Antony',
    author_email = 'daryl@commoncode.com.au',
    url = 'https://github.com/commoncode/cqrs',
    keywords = ['django',],
    packages = find_packages(),
    include_package_data = True,
    zip_safe = False,
    classifiers = [
        'Environment :: Web Environment',
        'Framework :: Django',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
    install_requires = [
        'django-denormalize',
        'pymongo',
    ],
)
