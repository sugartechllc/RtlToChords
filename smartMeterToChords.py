import logging
import argparse
import pychords.tochords as tochords
import json
import subprocess
import sys


def forwardRtlData():
    """
    Forward any received RTL data to chords.
    Block indefinitely.
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
            forwardRtlData()
        except Exception as e:
            logging.error("Something went wrong when forwarding RTL data.")
            logging.exception(e)


if __name__ == '__main__':
    main()
