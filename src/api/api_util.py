from src.api.constants import API_IP, QUORUMS, PORT, QUORUM_ID
import os
import logging
import logging.handlers
import requests

logging.basicConfig(
    format='%(asctime)s %(levelname)-2s %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
util_logger = logging.getLogger(__name__)

LOG_FILE_SIZE = 5 * 1024 * 1024  # 5MB
URL_REQUEST = "http://{hostname}:{port}/"


def util_log_to(path, console_logging=False):
    handler = logging.handlers.RotatingFileHandler(path, backupCount=5, maxBytes=LOG_FILE_SIZE)
    formatter = logging.Formatter('%(asctime)s %(levelname)-2s %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    util_logger.propagate = console_logging
    util_logger.setLevel(os.environ.get("LOGLEVEL", "INFO"))
    util_logger.addHandler(handler)


# get plain text from HTTP GET response
def get_plain_test(response):
    return response.data.decode("utf-8")


# this function is made to work with a flask app and cannot be used with out passing one to it as app
def forward(app, url_subdirectory: str, quorum_id: str, json_data):
    for this_quorum in app.config[QUORUMS]:
        for intersecting_quorum in app.config[QUORUMS][this_quorum]:
            if intersecting_quorum[QUORUM_ID] == quorum_id:
                url = URL_REQUEST.format(hostname=intersecting_quorum[API_IP],
                                         port=intersecting_quorum[PORT])
                url += url_subdirectory
                app.logger.info("request in quorum this peer is not a member of forwarding to "
                                "{}".format(url))
                forwarding_request = None
                try:
                    forwarding_request = requests.post(url, json=json_data)
                    app.logger.info("response form forward is {}".format(forwarding_request))
                except ConnectionError as e:
                    app.logger.error("{host}:{port} unreachable".format(host=intersecting_quorum[API_IP],
                                                                        port=intersecting_quorum[PORT]))
                    app.logger.error(e)
                return forwarding_request


