import subprocess
import json
import pychords.tochords as tochords
import time
import argparse
import logging
import io
import datetime
import sys

# Save the previous trtl_data, so that we can discard succesive duplicate
# messages, a common situation with these sensors (especially the Ambient Wx ones).
previous_rtl_data = {}

def sendToChords(config: dict, timestamp: int, vars: {}, chords_inst_override=None):
    """
    Send a single value to chords.
    config: Config settings dictionary.
    timestamp: The unix timestamp of the data in seconds.
    vars: a dictionary of chords_short_names:values
    """
    chords_record = {}
    chords_record["inst_id"] = config["instrument_id"]
    if chords_inst_override:
        chords_record["inst_id"] = chords_inst_override
    chords_record["api_email"] = config["api_email"]
    chords_record["api_key"] = config["api_key"]
    chords_record["vars"] = {}
    chords_record["vars"]["at"] = int(timestamp)
    chords_record["vars"].update(vars)
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
    
    # Check if model and id exists in data
    if "model" not in data or "id" not in data:
        logging.debug(f"* Missing model or id for {data}")
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
    logging.debug(f"Timestamp is: {timestamp}")

    # Check each sensor and handle all variables that apply to this data
    logging.debug(f"Scanning for sensor {data['model']}:{data['id']}")
    matched_sensor = False
    for sensor in config["smart_sensors"]:
        if (sensor["model"] != data["model"]) or (sensor["id"] != data["id"]):
            continue 

        logging.debug(f"* Found match for sensor {data['model']}:{data['id']}")
        matched_sensor = True
        vars = {}
        for variable in sensor["variables"]:
            chords_short_name = variable["chords_short_name"]
            if variable["rtl_name"] not in data:
                logging.warning(
                    f'{variable["rtl_name"]} does not exist in data: {data}')
                continue
            rtl_name = variable["rtl_name"]
            value = data[rtl_name]
            vars[chords_short_name] = data[rtl_name]
            logging.debug(
                f"Found matching data for {rtl_name} with value {value}")
        if len(vars):
            # we found matching variables, send them to chords
            chords_inst_override = sensor["chords_inst_id"] if "chords_inst_id" in sensor else None
            sendToChords(config, timestamp, vars, chords_inst_override)
        break
    
    if not matched_sensor:
        logging.debug(f"* No match for sensor {data['model']}:{data['id']}")


def forwardFromStream(config: dict, io_stream: io.TextIOBase):
    """
    Forward data from a generic text stream.
    config: Config settings dictionary.
    io_stream: The io stream to read json lines from an forward data from.
    """
    global previous_rtl_data

    for line in io_stream:
        logging.info(f"RTL line is: {line}")
        try:
            data = json.loads(line)
            logging.debug(f"RTL data is {data}")
            if data != previous_rtl_data:
                handleRtlData(config, data)
            else:
                logging.debug('* Discarding duplicate msg')
            previous_rtl_data = data
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

def validate_config(config: {}) -> None:
    ''' Will exit(1) if the configuration is not up to snuff '''

    if "smart_sensors" not in config:
        print("Configuration does not contain a sensors section.")
        sys.exit(1)
    if len(config["smart_sensors"]) == 0:
        print("No smart sensors defined.")
        sys.exit(1)
    
    for sensor in config["smart_sensors"]:
        if ("model" not in sensor) or ("id" not in sensor) or ("variables" not in sensor):
            print("Sensor configurations must contain 'model', 'id' and 'variables' definitions.")
            sys.exit(1)
            if variables not in sensor:
                print(f"Variables must exist for all sensors.")
                sys.exit(1)
            for variable in sensor["variables"]:
                if ("chords_short_name" not in sensor ) or ("rtl_name" not in variable):
                    print("Variable definitions must contain 'chords_short_name' and 'rtl_name'.")
                    sys.exit(1)

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
    validate_config(config)

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
