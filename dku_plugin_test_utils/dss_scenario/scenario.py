import allure
import logging
import inspect

from dku_plugin_test_utils.run_config import PluginInfo

from dataikuapi.dss.job import DSSJob


def run(client, project_key, scenario_id, user="default"):
    """
    Remotly run a DSS scenario that correspond to one pytest test.
    Once executed, job logs are collected and attached to an allure report

    Args:
        user (str): The user used for the DSS client instance
        client: DSS clients instances from dataikuapi
        project_key (str): The project holding the scenarios to run
        scenario_id (str): The DSS scenario to run
        logger (logger): The logger instance to use to output messages
    """

    stack_frame = inspect.stack()[1]
    calling_module = inspect.getmodule(stack_frame[0])
    logger = logging.getLogger("dss-plugin-test.{plugin_id}.{module_name}".format(plugin_id=PluginInfo().plugin_metadata["id"], module_name=calling_module.__name__))
    logger.info("User [{user}] is running scenario [{scenario}] from project [{project}]".format(scenario=scenario_id, project=project_key, user=user))
    user_dss_client = client[user]
    
    # setting the user for the run of the scenario
    # TODO : finish that when DSS7 is no longer in the picture.
    # admin_dss_client = client["admin"]
    # dss_scenario_settings = admin_dss_client.get_project(project_key).get_scenario(scenario_id).get_settings()
    # dss_scenario_settings.run_as(user)

    # effectively running the scenario
    dss_scenario = user_dss_client.get_project(project_key).get_scenario(scenario_id)
    dss_scenario.run_and_wait()
    last_dss_scenario_details = dss_scenario.get_last_finished_run().get_details()

    jobs = []
    for step in last_dss_scenario_details["stepRuns"]:
        if len(step.job_ids) > 0:
            jobs.extend([DSSJob(user_dss_client, project_key, job_id) for job_id in step.job_ids])

    for job in jobs:
        allure.attach(job.get_log(), "{}-{}".format(scenario_id, job.id), attachment_type=allure.attachment_type.TEXT)