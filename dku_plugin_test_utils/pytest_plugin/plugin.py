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
logger.setLevel(logging.DEBUG)

def pytest_addoption(parser):
    parser.addoption(
        "--exclude-dss-targets",
        action="store",
        help='"Target,[other targets]". Exclude DSS target from the instance configuration file.',
    )


def pytest_generate_tests(metafunc):
    """
    Pytest exposed hook allowing to dynamically change the pytest representation
    of a test which is metafunc.
    Here we use that hook to dynamically parameterize the "client" fixture of each test.
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
            raise RuntimeError(
                "You have excluded non existing DSS targets. Actual DSS targets : {}".format(
                    ",".join(targets)
                )
            )

        # subtract the excluded target from the target
        targets = list(targets - excluded_targets)

        if len(targets) == 0:
            raise RuntimeError("You have excluded all the DSS targets, nothing to do.")

    metafunc.parametrize("dss_target", targets, indirect=["dss_target"])


@pytest.fixture(scope="session")
def dss_target(request):
    """
    This is a parameterized fixture.
    Its value will be set with the different DSS target (DSS7, DSS8 ...)
    that are specified in the configuration file.
    It returns the value of the considered DSS target for the test.
    Here it is only used by other fixtures, but one could use it
    as a test function parameter to access its value inside the test function.

    Args:
        request: The object to introspect the “requesting”
        test function, class or module context

    Returns:
        The string corresponding to the considered DSS target for the
        test to be executed
    """

    dss_target = request.param

    current_run_config = ScenarioConfiguration()
    current_plugin_config = PluginInfo().plugin_metadata

    target_dss_available_interpreter = set(
        current_run_config.full_config[dss_target]["python_interpreter"]
    )

    plugin_python_interpreter = set(
        current_plugin_config["python_interpreter"]
        if "python_interpreter" in current_plugin_config
        else []
    )

    python_interpreters_for_code_env = list(
        target_dss_available_interpreter.intersection(plugin_python_interpreter)
    )
    if not python_interpreters_for_code_env:
        raise pytest.skip(
            (
                "No common python interpreter could be found "
                "between the DSS target and the ones ask by the plugin [{plugin_id}]"
                "From plugin: {plugin_interpreters}, "
                "From target: {target_interpreters}"
            ).format(
                plugin_id=current_plugin_config["id"],
                plugin_interpreters=",".join(plugin_python_interpreter),
                target_interpreters=",".join(target_dss_available_interpreter),
            )
        )

    return dss_target


@pytest.fixture(scope="function")
def user_dss_clients(dss_clients, dss_target):
    """
    Fixture that narrows down the dss clients to only the ones that are relevant
    considering the current DSS target.

    Args:
        dss_clients (fixture): All the dss client instances for
                               each user and dss targets
        dss_target (fixture): The considered DSS target for the test to be executed

    Returns:
        A dict of dss client instances for the current DSS target
        and each of its specified users.
    """
    return dss_clients[dss_target]


@pytest.fixture(scope="session")
def dss_clients(request):
    """
    The client fixture that is used by each of the tests that
    will target a DSS instance.
    The scope of that fixture is set to module, so upon exiting a test module,
    the fixture is destroyed

    Args:
        request: A pytest object allowing to introspect the test context.
        It allows us to access the value of host set in `pytest_generate_tests`

    Returns:
        dssclient: return a instance of a DSS client.
        It will be the same reference for each test withing the associated context.
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
                dss_clients[target].update(
                    {user: dataikuapi.DSSClient(url, api_key=api_key)}
                )

    return dss_clients


@pytest.fixture(scope="session")
def plugin(dss_clients, dss_target):
    """
    The plugin fixture that is used by each of the tests.
    It depends on the client fixture, as it needs to be
    uploaded on the proper DSS instance using the admin user.
    The scope of that fixture is set to module,
    so upon exiting a test module, the fixture is destroyed

    Args:
        dss_clients: A DSS client instance.
        dss_target:
    """

    logger.info(
        f"Uploading the plugin to [{dss_target}] instance"
    )
    p = subprocess.Popen(
        ["make", "plugin"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = p.communicate()
    return_code = p.returncode
    if return_code != 0:
        raise RuntimeError(
            f"Error while compiling the plugin. \n "
            f"Make command stderr : \n"
            f" - stderr:\n{stderr.decode('utf-8')}"
        )

    logger.debug(
        f"make command output:\n "
        f"- stdout:\n{stdout.decode('utf-8')}\n "
        f"- stderr:\n{stderr.decode('utf-8')}"
    )

    info = PluginInfo().plugin_metadata
    plugin_zip_name = f"dss-plugin-{info['id']}-{info['version']}.zip"
    plugin_zip_path = os.path.join(os.getcwd(), "dist", plugin_zip_name)

    admin_client = dss_clients[dss_target]["admin"]
    get_plugin_ids = itemgetter("id")
    available_plugins = list(map(get_plugin_ids, admin_client.list_plugins()))
    if info["id"] in available_plugins:
        logger.debug(
            f"Plugin [{info['id']}] is already installed on [{dss_target}], updating it"
        )
        with open(plugin_zip_path, "rb") as fd:
            uploaded_plugin = admin_client.get_plugin(info["id"])
            uploaded_plugin.update_from_zip(fd)
    else:
        logger.debug(
            f"Plugin [{info['id']}] is not installed on [{dss_target}], installing it"
        )
        with open(plugin_zip_path, "rb") as fd:
            admin_client.install_plugin_from_archive(fd)
            uploaded_plugin = admin_client.get_plugin(info["id"])

    plugin_settings = uploaded_plugin.get_settings()
    raw_plugin_settings = plugin_settings.get_raw()

    # install (or reinstall) code-env only if the plugin has a specific
    # code-env defined (not using DSS built-in):
    if PluginInfo().plugin_codenv_metadata is not None:
        if (
            "codeEnvName" in raw_plugin_settings
            and len(raw_plugin_settings["codeEnvName"]) != 0
        ):
            logger.debug(
                f"Code env [{raw_plugin_settings['codeEnvName']}] "
                f"is already associated to [{info['id']}] "
                f"on [{dss_target}], deleting it"
            )

            code_env_list = admin_client.list_code_envs()
            code_env_info = list(
                filter(
                    lambda x: x["envName"] == raw_plugin_settings["codeEnvName"],
                    code_env_list,
                )
            )
            if code_env_info:
                code_env_info = code_env_info[0]
                code_env = admin_client.get_code_env(
                    code_env_info["envLang"], code_env_info["envName"]
                )
                code_env.delete()
            logger.debug(
                f"Code env [{raw_plugin_settings['codeEnvName']}] is deleted. "
                f"Creating it again and associating it back to [{info['id']}] "
                f"on [{dss_target}]"
            )
            _install_code_env(dss_target, info, plugin_settings, uploaded_plugin)
        else:
            logger.debug(
                f"No code env is associated to [{info['id']}] "
                f"on [{dss_target}], creating it"
            )
            _install_code_env(dss_target, info, plugin_settings, uploaded_plugin)


def _install_code_env(target, plugin_info, plugin_settings, uploaded_plugin):
    """
    Install the code env for the plugin.
    It is a private function to avoid code duplication

    Args:
        target(str): The DSS target to install the code env
        plugin_info(dict): The plugin info based on the plugin.json and code-env desc.json.
        plugin_settings: The plugin settings object from dataiku-api
        uploaded_plugin: The plugin object corresponding to the current plugin
    """
    current_run_config = ScenarioConfiguration()
    target_available_interpreter = set(
        current_run_config.full_config[target]["python_interpreter"]
    )
    plugin_python_interpreter = set(
        plugin_info["python_interpreter"] if "python_interpreter" in plugin_info else []
    )

    python_interpreters_for_code_env = list(
        target_available_interpreter.intersection(plugin_python_interpreter)
    )

    python_interpreter = python_interpreters_for_code_env[
        0
    ]  # if multiple in common taking the first one.
    logger.debug(
        "The code env will be installed using interpreter [{}]".format(
            python_interpreter if python_interpreter is not None else "PYTHON27"
        )
    )
    ret = uploaded_plugin.create_code_env(
        python_interpreter=python_interpreter
    ).wait_for_result()
    if ret["messages"]["error"]:
        raise RuntimeError(
            "Error while installing the code-env [{ret['envName']}], "
            "check DSS code-env creation logs on DSS"
        )

    logger.debug(
        f"The code env [{ret['envName']}] is assocated with [{plugin_info['id']}]"
    )
    plugin_settings.set_code_env(ret["envName"])
    plugin_settings.save()
