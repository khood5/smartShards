from src.api.constants import API_IP, QUORUMS, PORT, QUORUM_ID, ROUTE_EXECUTION_FAILED
import os
import logging
import logging.handlers
import requests

logging.basicConfig(
    format='%(asctime)s %(levelname)-2s %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
api_util_logger = logging.getLogger(__name__)

LOG_FILE_SIZE = 5 * 1024 * 1024  # 5MB
URL_REQUEST = "http://{hostname}:{port}/"


def util_log_to(path, console_logging=False):
    handler = logging.handlers.RotatingFileHandler(path, backupCount=5, maxBytes=LOG_FILE_SIZE)
    formatter = logging.Formatter('%(asctime)s %(levelname)-2s %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    api_util_logger.propagate = console_logging
    api_util_logger.setLevel(os.environ.get("LOGLEVEL", "INFO"))
    api_util_logger.addHandler(handler)


# get plain text from HTTP GET response
def get_plain_text(response):
    try:
        return response.data.decode("utf-8")
    except AttributeError:
        api_util_logger.warning("{}: could not get text with response.data.decode(\"utf-8\")".format(__name__))

    try:
        return response.text
    except AttributeError:
        api_util_logger.error("{}: could not get text with response.text".format(__name__))


# this function is made to work with a flask app and cannot be used with out passing one to it as app
def forward(app, url_subdirectory: str, quorum_id: str, json_data):
    for check_quorum_id in list(app.config[QUORUMS].keys()):
        for intersecting_quorum in app.config[QUORUMS][check_quorum_id]:
            intersecting_quorum_id = intersecting_quorum[QUORUM_ID]
            if intersecting_quorum_id == quorum_id:
                url = URL_REQUEST.format(hostname=intersecting_quorum[API_IP],
                                        port=intersecting_quorum[PORT])
                url += url_subdirectory
                app.logger.info("request in quorum this peer is not a member of forwarding to "
                                "{}".format(url))
                try:
                    forwarding_request = requests.post(url, json=json_data)
                    forwarding_request = get_plain_text(forwarding_request)
                    app.logger.info("response form forward is {}".format(forwarding_request))
                    return forwarding_request
                except ConnectionError as e:
                    app.logger.error("{host}:{port} unreachable".format(host=intersecting_quorum[API_IP],
                                                                        port=intersecting_quorum[PORT]))
                    app.logger.error(e)
                    return ROUTE_EXECUTION_FAILED.format(msg="forward to {} failed".format(url))


# Creates a blank intersection map based on the quorums
# An intersection map is a dictionary of dictionaries that stores the 
# intersections between two quorums.
def create_intersection_map(quorum_ids):
    quorum_ids.sort()
    return {str(a): {str(b): {} for b in quorum_ids[i+1:]} for i, a in enumerate(quorum_ids)}

# Merge intersection maps, creating a union of the intersections.
# Returns the resulting intersection map
def merge_intersection_maps(map_a, map_b):
    keys_a = list(map_a.keys())
    vals_a = list(map_a[keys_a[0]].keys())
    keys_b = list(map_b.keys())
    vals_b = list(map_b[keys_b[0]].keys())
    quorum_ids = list(set(keys_a+vals_a+keys_b+vals_b))
    new_map = create_intersection_map(quorum_ids)
    for ((row_key_a, row_value_a), (row_key_b, row_value_b)) in zip(map_a.items(), map_b.items()):
        for ((col_key_a, col_value_a), (col_key_b, col_value_b)) in zip(row_value_a.items(), row_value_b.items()):
            new_map[row_key_a][col_key_a].update(col_value_a)
            new_map[row_key_b][col_key_b].update(col_value_b)
    return new_map

# Inserts a peer into an intersection map, automatically sorting ther quorums
# Returns nothing, alters the given map
def insert_into_intersection_map(map, peer, quorum_a, quorum_b):
    if quorum_a <= quorum_b:
        map[quorum_a][quorum_b][peer] = 0
    else:
        map[quorum_b][quorum_a][peer] = 0
