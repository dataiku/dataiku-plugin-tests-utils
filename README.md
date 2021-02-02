# dataiku-plugin-tests-utils
Common tooling for DSS plugins integration tests

# How to install in your plugin
To install the `dataiku-plugin-tests-utils` package for your plugins use the
following line depending on your prefered way to managed packages and situation
you are in.
## Using Requierement.txt
### Development cycle

`git+git://github.com/dataiku/dataiku-plugin-tests-utils.git@<BRANCH>#egg=dataiku-plugin-tests-utils`

Replace `<BRANCH>` by the most accurate value

### Stable release (untested for now)

`git+git://github.com/dataiku/dataiku-plugin-tests-utils.git@releases/tag/<RELEASE_VERSION>#egg=dataiku-plugin-tests-utils`

Replace `<RELEASE_VERSION>` by the moist accurate value

## Using Pipfile
Put the following line under `[dev-packages]` section
### Development cycle
`dku-plugin-test-utils = {git = "git://github.com/dataiku/dataiku-plugin-tests-utils.git", ref = "<BRANCH>"}`
### Stable release
TBD

## Dev env
### Config

First, ensure that you have Personal Api Keys generated for the DSS you want to target.
Secondly, define a config file which will give the DSS you will target.
```
{
	"DSSX":
	{
		"url": ".......",
		"users": {
			"usrA": "api_key",
			"usrB": "api_key",
			"default": "usrA"
		}
	},
	"DSSY":
	{
		"url": "......",
		"users": {
			"usrA": "api_key",
			"usrB": "api_key",
			"default": "usrB"
		}
	}
}

```
Beware!!, user names must be identical in the configuration file between the different DSS instance.
Then, set the env var `PLUGIN_INTEGRATION_TEST_INSTANCE` to point to the config file.

# How to use the package

## General information
To use the package in your test files:
```python
import dku_plugin_test_utils
import dku_plugin_test_utils.subpakcage.subsymbol
```
Look at the next section for more information about potential `subpackage` and `subsymbol`

The python integration tests files are indirections towards the "real" tests that are written as DSS scenarios on DSS instances.
The python test function triggers the targeted DSS scenario and waits either for its sucessfull or failed completion.
Thence your test function should look like the following snippet :
```python
# Mandatory imprts
import pytest
import logging

from dku_plugin_test_utils import dss_scenario

# Mandatory object for testing
# These are the module level fixtures that will be created before running any tests.
pytestmark = pytest.mark.usefixtures("plugin", "dss_target")

# The modulke level logger to understand where you are when a failure arises
logger = logging.getLogger("dss-plugin-test.PLUGIN_NAME.current_python_module_name")

def test_run_some_dss_scenario(client, plugin):
     dss_scenario.run("default", user_clients["default"], 'PROJECT_KEY', 'scenario_id', logger)

# [... other tests ...]
```
With:
- `default`: being the default user that will run the scenario. It could be any other user as defined in you configuration file as seen above
- `user_clients["default"]`: representing the dss client corresponding to the desired user.
- `PROJECT_KEY`: The project that holds the test scenarios
- `scenario_id`: The test scenario to run
- `logger`: The module level logger. It will help you narow down any problem in can of error

## How to generate a graphical report with Allure for integration tests

For each plugin, a folder named `allure_report` should exists inside the `test` folder, reports will be generated inside that folder.
To generate the graphical report, you must have allure installed on your system as described [on their installation guide](https://docs.qameta.io/allure/#_manual_installation). Once the installation is done, run the following :
```shell
allure serve path/to/the/allure_report/dir/inside/you/plugin/test/folder/
```

# Package Hierarchy
As it is a tooling package for integration test, it will aggregate different packages with different aim. 
The following hierarchy exposes the different sub-package contained in `dku_plugin_test_utils` with their aim 
and the list of public symbols:

- `run_config`:
  - `ScenarioConfiguration`: Class exposing the parsed run configuration as a python dict.
  - `get_plugin_info`: Read the plugin.json file to extract plugin information as a python dict.
- `dss_scenario`: 
  - `run`: Run the targetted DSS scenario and wait for it completion either success or failure.
