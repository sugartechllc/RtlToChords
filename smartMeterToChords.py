import logging
import argparse
import time
import pychords.tochords as tochords
import json
import subprocess
import sys


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
            logging.info("Sending to chords!!!!!!!!")  # TODO.....


def forwardRtlData(config: dict):
    """
    Forward any received RTL data to chords.
    Blocks indefinitely.
    config: Config setting dictionary.
    """

    # Open RTL subprocess that prints any received data to stdout as json
    rtl_process = subprocess.Popen(["/usr/local/bin/rtl_433",
                                    "-f", "915000000",
                                    "-F", "json"],
                                   stdout=subprocess.PIPE)

    # Read all lines from RTL
    for line in rtl_process.stdout:
        logging.info(f"RTL line is: {line}")
        try:
            data = json.loads(line)
            logging.info(f"RTL data is {data}")
            handleRtlData(config, data)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse RTL line: {e}")


def main():

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--config", help="Path to json configuration file to use.", required=True)
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
    logging.info(f"Starting SmartMeter to Chords with {args.config}")
    config = json.loads(open(args.config).read())

    # Startup chords sender
    tochords.startSender()

    # Forward RTL data indefinitely
    while True:
        try:
            forwardRtlData(config)
        except Exception as e:
            logging.error("Something went wrong when forwarding RTL data.")
            logging.exception(e)
            time.sleep(1)


if __name__ == '__main__':
    main()
