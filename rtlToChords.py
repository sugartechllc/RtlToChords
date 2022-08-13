import subprocess
import json
import pychords.tochords as tochords
import time
import argparse
import logging
import io
import datetime
import sys


def sendToChords(config: dict, short_name: str, timestamp: int, value: float):
    """
    Send a single value to chords.
    config: Config settings dictionary.
    short_name: The chords short variable name of the value to send.
    timestamp: The unix timestamp of the data in seconds.
    value: The data value to send.
    """
    chords_record = {}
    chords_record["inst_id"] = config["instrument_id"]
    chords_record["api_email"] = config["api_email"]
    chords_record["api_key"] = config["api_key"]
    chords_record["vars"] = {}
    chords_record["vars"]["at"] = int(timestamp)
    chords_record["vars"][short_name] = value
    uri = tochords.buildURI(config["chords_host"], chords_record)
    logging.info(f"Submitting: {uri}")
    max_queue_length = 10*60*24
    tochords.submitURI(uri, max_queue_length)


def handleRtlData(config: dict, data: dict):
    """
    Handle a RTL json data item.
    config: Config setting dictionary.
    data: The json data to handle.
    """

    # Get list of sensors to parse
    if "smart_sensors" not in config:
        logging.warning("No smart sensors defined, not handling RTL data.")
        return
    sensors = config["smart_sensors"]
    if len(sensors) == 0:
        logging.warning("No smart sensors defined, not handling RTL data.")
        return

    # Check if model exists in data
    if "model" not in data:
        logging.error("No model defined in RTL data.")
        return

    # Get timestamp
    timestamp = time.time()
    if "time" in data:
        try:
            dt = datetime.datetime.fromisoformat(data["time"])
            timestamp = dt.timestamp()
        except Exception as e:
            logging.error(
                f'Failed to parse timestamp {data["time"]}, using current time')
    else:
        logging.warning("No timestamp in data, using current time")
    logging.info(f"Timestamp is: {timestamp}")

    # Check each sensor and handle all variables that apply to this data
    for sensor in sensors:
        if "model" not in sensor:
            logging.warning(f"No model defined for sensor {sensor}")
            continue
        if sensor["model"] != data["model"]:
            logging.debug(
                f'Sensor model {sensor["model"]} does not match data model {data["model"]}')
            continue
        if "id" not in sensor:
            logging.warning(f"No id defined for sensor {sensor}")
            continue
        if sensor["id"] != data["id"]:
            logging.debug(
                f'Sensor id {sensor["id"]} does not match data id {data["id"]}')
            continue
        logging.info("Found matching RTL model!")
        if "variables" not in sensor:
            logging.warning(f"No variables to handle for sensor {sensor}")
            continue

        # Handle each variable
        for variable in sensor["variables"]:
            if "chords_short_name" not in variable:
                logging.warning(
                    f"No chords_short_name defined for variable {variable}")
                continue
            chords_short_name = variable["chords_short_name"]
            if "rtl_name" not in variable:
                logging.warning(f"No rtl_name defined for variable {variable}")
                continue
            if variable["rtl_name"] not in data:
                logging.warning(
                    f'{variable["rtl_name"]} does not exist in data: {data}')
                continue
            rtl_name = variable["rtl_name"]
            value = data[rtl_name]
            logging.info(
                f"Found matching data for {rtl_name} with value {value}")
            sendToChords(config, chords_short_name, timestamp, value)


def forwardFromStream(config: dict, io_stream: io.TextIOBase):
    """
    Forward data from a generic text stream.
    config: Config settings dictionary.
    io_stream: The io stream to read json lines from an forward data from.
    """
    for line in io_stream:
        logging.info(f"RTL line is: {line}")
        try:
            data = json.loads(line)
            logging.info(f"RTL data is {data}")
            handleRtlData(config, data)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse RTL line: {e}")


def forwardRtlData(config: dict):
    """
    Run rtl_433 command and forward any received RTL data to chords.
    Blocks indefinitely.
    config: Config settings dictionary.
    """

    # Open RTL subprocess that prints any received data to stdout as json
    rtl_process = subprocess.Popen(["/usr/local/bin/rtl_433",
                                    "-f", "915000000",
                                    "-F", "json"],
                                   stdout=subprocess.PIPE)

    # Read all lines from RTL
    forwardFromStream(config, rtl_process.stdout)


def main():

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--config", help="Path to json configuration file to use.", required=True)
    parser.add_argument(
        "-f", "--file", help="Read from specified file instead of running rtl_433 indefinitely", required=False, type=str)
    parser.add_argument(
        "--debug", help="Enable debug logging",
        action="store_true")
    args = parser.parse_args()

    # Configure logging
    level = logging.INFO
    if args.debug:
        level = logging.DEBUG
    logging.basicConfig(stream=sys.stdout, level=level, format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    logging.debug("Debug logging enabled")

    # Load configuration
    logging.info(f"Starting RTL to Chords with {args.config}")
    config = json.loads(open(args.config).read())

    # Startup chords sender
    tochords.startSender()

    if args.file is None:
        # Forward RTL data indefinitely
        while True:
            try:
                forwardRtlData(config)
            except Exception as e:
                logging.error("Something went wrong when forwarding RTL data.")
                logging.exception(e)
                time.sleep(1)
    else:
        # Read from file
        with open(args.file, "r") as f:
            forwardFromStream(config, f)

    # Wait for all data to be sent
    while True:
        num_remaining = tochords.waiting()
        logging.info(f"Queue length: {num_remaining}")
        time.sleep(1)
        if num_remaining == 0:
            break


if __name__ == '__main__':
    main()
