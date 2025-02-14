import setuptools

with open("README.md", "r") as fd:
    long_desc = fd.read()


setuptools.setup(
    name="dataiku-plugin-tests-utils",
    version="0.0.1",
    description="The common tooling needed for each plugin",
    author="Dataiku",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    url="https://www.dataiku.com",
    packages=setuptools.find_packages(),
    entry_points={"pytest11": ["pytest_plugin = dku_plugin_test_utils.pytest_plugin.plugin"]},
    classifiers=[
            'Intended Audience :: Developers',
            'License :: OSI Approved :: Apache Software License',
            'Topic :: Software Development :: Libraries',
            'Programming Language :: Python',
            'Operating System :: OS Independent'
        ],
    python_requires='>=2.7',
    install_requires=[
        "dataiku-api-client",
        "allure-pytest==2.13.3"
        ]
)
