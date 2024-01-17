import logging
from operator import itemgetter
import os
import subprocess

import dataikuapi
import pytest

from dku_plugin_test_utils.logger import Log
from dku_plugin_test_utils.run_config import ScenarioConfiguration
from dku_plugin_test_utils.run_config import PluginInfo


# Entry point for integration test cession, load the logger configuration
Log()

logger = logging.getLogger("dss-plugin-test.pytest_plugin")


def pytest_addoption(parser):
    parser.addoption(
        "--exclude-dss-targets", action="store", help="\"Target,[other targets]\". Exclude DSS target from the instance configuration file."
    )


def pytest_generate_tests(metafunc):
    """
    Pytest exposed hook allowing to dynamically alterate the pytest representation of a test which is metafunc
    Here we use that hook to dynamically paramertrize the "client" fixture of each tests. 
    Therefore, a new client will be instantiated for each DSS instance.

    Args:
        metafunc: pytest object representing a test function
    """
    curent_run_config = ScenarioConfiguration()
    targets = curent_run_config.targets
    if metafunc.config.getoption("--exclude-dss-targets"):
        excluded_targets = metafunc.config.getoption("--exclude-dss-targets")
        excluded_targets = excluded_targets.split(",")

        # The excluded targets list is casted as set to use the set arithmetic operators
        excluded_targets = set(excluded_targets)
        targets = set(targets)

        if excluded_targets.isdisjoint(targets):
            raise RuntimeError("You have excluded non existing DSS targets. Actual DSS targets : {}".format(','.join(targets)))

        # substract the excluded target from the target
        targets = list(targets - excluded_targets)

        if len(targets) == 0:
            raise RuntimeError("You have excluded all the DSS targets, nothing to do.")

    metafunc.parametrize("dss_target", targets, indirect=["dss_target"])


@pytest.fixture(scope="function")
def dss_target(request):
    """
    This is a parameterized fixture. Its value will be set with the different DSS target (DSS7, DSS8 ...) that are specified in the configuration file.
    It returns the value of the considered DSS target for the test. Here it is only used by other fixtures, but one could use it 
    as a test function parameter to access its value inside the test function.

    Args:
        request: The object to introspect the “requesting” test function, class or module context

    Returns:
        The string corresponding to the considered DSS target for the test to be executed
    """
    return request.param


@pytest.fixture(scope="function")
def user_dss_clients(dss_clients, dss_target):
    """
    Fixture that narrows down the dss clients to only the ones that are relevant considering the curent DSS target.

    Args:
        dss_clients (fixture): All the instanciated dss client for each user and dss targets
        dss_target (fixture): The considered DSS target for the test to be executed

    Returns:
        A dict of dss client instances for the current DSS target and each of its specified users.
    """
    return dss_clients[dss_target]


@pytest.fixture(scope="module")
def dss_clients(request):
    """
    The client fixture that is used by each of the test that will target a DSS instance.
    The scope of that fixture is set to module, so upon exiting a test module the fixture is destroyed

    Args:
        request: A pytest obejct allowing to introspect the test context. It allows us to access 
        the value of host set in `pytest_generate_tests`

    Returns:
        dssclient: return a instance of a DSS client. It will be the same reference for each test withing the associated context.
    """
    dss_clients = {}
    current_run_config = ScenarioConfiguration()

    excluded_targets = []
    if request.config.getoption("--exclude-dss-targets"):
        excluded_targets = request.config.getoption("--exclude-dss-targets")
        excluded_targets = excluded_targets.split(",")

    logger.info("Instanciating all the DSS clients for each user and DSS instance")
    for host in current_run_config.hosts:
        target = host["target"]
        if target not in excluded_targets:
            dss_clients.update({target: {}})
            url = host["url"]
            for user, api_key in host["users"].items():
                dss_clients[target].update({user: dataikuapi.DSSClient(url, api_key=api_key)})

    return dss_clients


@pytest.fixture(scope="module")
def plugin(request, dss_clients, dss_target):
    """
    The plugin fixture that is used by each of the test. It depends on the client fixture, as it needs to be 
    uploaded on the proper DSS instance using the admin user.
    The scope of that fixture is set to module, so upon exiting a test module the fixture is destroyed

    Args:
        request: The internal pytest fixture to access test context
        dss_clients: The list of DSS clients.
        dss_target: The target DSS instance.

    """
    logger.setLevel(logging.DEBUG)

    logger.info("Uploading the pluging to each DSS instances [{}]".format(",".join(dss_clients.keys())))
    p = subprocess.Popen(['make', 'plugin'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    return_code = p.returncode
    if return_code != 0:
        raise RuntimeError("Error while compiling the plugin. \n Make command stderr : \n - stderr:\n{}".format(stderr.decode("utf-8")))

    logger.debug("make command output:\n - stdout:\n{}\n - stderr:\n{}".format(stdout.decode("utf-8"), stderr.decode("utf-8")))

    info = PluginInfo().plugin_metadata
    plugin_zip_name = "dss-plugin-{plugin_id}-{plugin_version}.zip".format(plugin_id=info["id"], plugin_version=info["version"])
    plugin_zip_path = os.path.join(os.getcwd(), "dist", plugin_zip_name)

    admin_client = dss_clients[dss_target]["admin"]
    get_plugin_ids = itemgetter("id")
    available_plugins = list(map(get_plugin_ids, admin_client.list_plugins()))
    if info["id"] in available_plugins:
        logger.debug("Plugin [{plugin_id}] is already installed on [{dss_target}], updating it".format(plugin_id=info["id"], dss_target=dss_target))
        with open(plugin_zip_path, 'rb') as fd:
            uploaded_plugin = admin_client.get_plugin(info["id"])
            uploaded_plugin.update_from_zip(fd)
    else:
        logger.debug("Plugin [{plugin_id}] is not installed on [{dss_target}], installing it".format(plugin_id=info["id"], dss_target=dss_target))
        with open(plugin_zip_path, 'rb') as fd:
            admin_client.install_plugin_from_archive(fd)
            uploaded_plugin = admin_client.get_plugin(info["id"])

    plugin_settings = uploaded_plugin.get_settings()
    raw_plugin_settings = plugin_settings.get_raw()

    # install (or reinstall) code-env only if plugin has a specific code-env defined (not using DSS built-in):
    if PluginInfo().plugin_codenv_metadata is not None:
        if "codeEnvName" in raw_plugin_settings and len(raw_plugin_settings["codeEnvName"]) != 0:
            logger.debug("Code env [{code_env_name}] is already associated to [{plugin_id}] on [{dss_target}], deleting it".format(code_env_name=raw_plugin_settings["codeEnvName"],
                                                                                                                                   plugin_id=info["id"],
                                                                                                                                   dss_target=dss_target))

            code_env_list = admin_client.list_code_envs()
            code_env_info = list(filter(lambda x: x["envName"] == raw_plugin_settings["codeEnvName"], code_env_list))
            if code_env_info:
                code_env_info = code_env_info[0]
                code_env = admin_client.get_code_env(code_env_info["envLang"], code_env_info["envName"])
                code_env.delete()
            logger.debug("Code env [{code_env_name}] is deleted. Creating it again and associating it back to [{plugin_id}] on [{dss_target}]".format(code_env_name=raw_plugin_settings["codeEnvName"],
                                                                                                                                                      plugin_id=info["id"],
                                                                                                                                                      dss_target=dss_target))
            _install_code_env(dss_target, info, plugin_settings, uploaded_plugin)
        else:
            logger.debug("No code env is associated to [{plugin_id}] on [{dss_target}], creating it".format(plugin_id=info["id"], dss_target=dss_target))
            _install_code_env(dss_target, info, plugin_settings, uploaded_plugin)


def _install_code_env(request, target, plugin_info, plugin_settings, uploaded_plugin):
    """
    Install the code env for the plugin. It is a private function to avoid code duplication

    Args:
        request: The pytest request fixture to intract with the test context.
        target(str): The DSS target to install the code env
        plugin_info(dict): The plugin info based on the plugin.json and code-env desc.json.
        plugin_settings: The plugin settings object from dataikuapi
        uploaded_plugin: The plugin object corresping the to current plugin
    """
    current_run_config = ScenarioConfiguration()
    target_available_interpreter = set(current_run_config.full_config[target]["python_interpreter"])
    plugin_python_interpreter = set(plugin_info["python_interpreter"] if "python_interpreter" in plugin_info else [])

    python_interpreters_for_code_env = list(target_available_interpreter.intersection(plugin_python_interpreter))
    if not python_interpreters_for_code_env:
        request.applymarker(pytest.mark.skip(reason="OUPS"))
        raise RuntimeError("No common python interpreter could be found "
                           "between the DSS target and the ones ask by the plugin [{plugin_id}]"
                           "From plugin: {plugin_interpreters}, From target: {target_interpreters}".format(plugin_id=plugin_info["id"],
                                                                                                           plugin_interpreters=",".join(plugin_python_interpreter),
                                                                                                           target_interpreters=",".join(target_available_interpreter)))

    python_interpreter = python_interpreters_for_code_env[0]  # if multiple in common taking the first one.
    logger.debug("The code env will be installed using interpreter [{}]".format(python_interpreter if python_interpreter is not None else "PYTHON27"))
    ret = uploaded_plugin.create_code_env(python_interpreter=python_interpreter).wait_for_result()
    if ret["messages"]["error"]:
        raise RuntimeError("Error while installing the code-env [{code_env_name}], check DSS code-env creation logs on DSS".format(code_env_name=ret["envName"]))

    logger.debug("The code env [{code_env_name}] is assocated with [{plugin_id}]".format(code_env_name=ret["envName"], plugin_id=plugin_info["id"]))
    plugin_settings.set_code_env(ret["envName"])
    plugin_settings.save()
