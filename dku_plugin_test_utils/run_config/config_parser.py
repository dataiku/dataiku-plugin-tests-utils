import json
import os


class ScenarioConfiguration(object):
    """
    Class that will hold the test cessuib configuration regarding DSS and users that will be involded.
    It is a singleton, so it will read only once the configuration and each time it is requested, it will
    loaded directly from memory and not from the json file.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        """
        Used here to define only one instance of the class
        """
        if not cls._instance:
            cls._instance = \
                super(ScenarioConfiguration, cls).__new__(cls)
            cls._instance._initialized = False

        return cls._instance

    def __init__(self):

        # Skip the init if we already have read the file.
        if self._initialized:
            return

        self._initialized = True

        # Get the path to the configuration file, if it is empty raise an Error
        test_instance_config_path = os.getenv("PLUGIN_INTEGRATION_TEST_INSTANCE", None)
        if not test_instance_config_path:
            raise ValueError("'PLUGIN_INTEGRATION_TEST_INSTANCE' is not defined, please point it to an instance configuration file")

        # Open the json file and map it to a python dict
        with open(test_instance_config_path, "r") as fd:
            self._run_instance_config = json.load(fd)

        # For simplicity replace the default tag with the actual api_key
        for dss_target in self._run_instance_config:
            default_user = self._run_instance_config[dss_target]["users"]["default"]
            default_api_key = self._run_instance_config[dss_target]["users"][default_user]
            self._run_instance_config[dss_target]["users"]["default"] = default_api_key

        # Slightly change the format to put the key which is the target DSS
        # at the same level of the other walues.
        self._hosts = []
        for key, value in self._run_instance_config.items():
            self._hosts.append({"target": key, **value})

    @property
    def hosts(self):
        return self._hosts

    @property
    def targets(self):
        return self._run_instance_config.keys()

    @property
    def full_config(self):
        return self._run_instance_config


class PluginInfo(object):
    """
    A class that will hold the plugin and associated code env metadata.

    It reads the plugin information that can be found at the root level of each plugin.
    It also parses the information related to the code env needed by the pluging 
    that can be found in the code-env folder.

    Returns:
        dict: The python dict representing the plugin informations
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        """
        Used here to define only one instance of the class
        """
        if not cls._instance:
            cls._instance = \
                super(PluginInfo, cls).__new__(cls)
            cls._instance._initialized = False

        return cls._instance

    def __init__(self):

        # Skip the init if we already have read the file.
        if self._initialized:
            return

        self._initialized = True

        self._plugin_metadata = None
        with open('plugin.json') as json_file:
            self._plugin_metadata = json.load(json_file)

        self._code_env_info = None
        # Some plugins don't have a specific code-env defined (they use DSS built-in code-env instead).
        # for those, code-env desc.json will not exist:
        if os.path.isfile('code-env/python/desc.json'):
            with open('code-env/python/desc.json') as json_file:
                self._code_env_info = json.load(json_file)

            python_interpretors_to_use = None
            if "acceptedPythonInterpreters" in self._code_env_info and len(self._code_env_info["acceptedPythonInterpreters"]) > 0:
                _envs = self._code_env_info["acceptedPythonInterpreters"]
                if all(map(lambda x: "PYTHON3" in x, _envs)):
                    python_interpretors_to_use = _envs  # All interpretor are python3 so taking any should do the trick
                else:
                    # We have a mix of python2 and python3 or just python2
                    if all(map(lambda x: "PYTHON2" in x, _envs)):
                        python_interpretors_to_use = _envs   # All interpretor are python2 so taking any should do the trick
                    else:
                        python_interpretors_to_use = list(filter(lambda x: "PYTHON2" in x, _envs))  # Filtering out python2, and taking any python3 interpretor version.

                self._plugin_metadata.update({"python_interpreter": python_interpretors_to_use})

    @property
    def plugin_metadata(self):
        """
        Returns:
            dict: The python dict representing the plugin and code env prefered interpreter
        """
        return self._plugin_metadata

    @property
    def plugin_codenv_metadata(self):
        """
        Returns:
            dict: The python dict representing the code env metadata
        """
        return self._code_env_info
