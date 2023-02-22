## Installation

- install Raspbery PI OS (Raspberry PI Imager)
- `sudo apt-get install git`
- `sudo apt-get install rtl-433`
- `sudo ln -s /usr/bin/rtl_433 /usr/local/bin/`
- `cp rtltochords.service ~/`
- Edit ~/rtltochords.service
- Copy archived copy (on iMac) of config.json to ~/.config.json
- `sudo systemctl enable /home/pi/rtltochords.service`
- `sudo systemctl start rtltochords`
- `systemctl list-units --type=service`
- `journalctl -u rtltochords -f`
