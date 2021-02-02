"""
Create the handler and formatter for the logging capabilities
"""
import logging
import sys


# Just to prevent the logger from being initialized many times (as we are passing here more than one time)
class Log(object):
    """
    Create the dss-plugin-test root logger from which each plugin test module logger can inherit from.
    The goal is to have an unified look and feel across all the logging messages.

    usage :
    logger = logging.getLogger("dss-plugin-test.YOUR_PLUGIN.some_modiule")

    it will print on the console :
    [date_utc_format] [processId-thread Name] [level of log] [name of logger] - message

    For now, the messages are directed to the console, but could go to a file/syslog/log servers ...
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        """
        Used here to define only one instance of the class
        """
        if not cls._instance:
            cls._instance = super(Log, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialized = False

        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True

        # Get the logger and set the base log level
        dss_pluging_test_logger = logging.getLogger("dss-plugin-test")
        dss_pluging_test_logger.setLevel(logging.INFO)
        dss_pluging_test_logger.propagate = False

        # create console handler and set level to debug as default
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)

        # create formatter
        formatter = logging.Formatter(
           '[%(asctime)s] [%(process)d-%(threadName)s] [%(levelname)s] [%(name)s] - %(message)s')

        # add formatter to console handler
        console_handler.setFormatter(formatter)

        # add ch to logger
        dss_pluging_test_logger.addHandler(console_handler)