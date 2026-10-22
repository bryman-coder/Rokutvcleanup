# Roku Remote (Python)

A small command-line remote for a Roku device on the same local network. It uses Roku's External Control Protocol (ECP) on port 8060 and Python's standard library; no packages need to be installed.

## Requirements

- Python 3
- Computer and Roku connected to the same home network
- Roku setting **Control by mobile apps** enabled
- Roku's local IP address (find it in the Roku network settings)

## Run

From this folder:

```bash
python3 roku_remote.py
```

The program searches your local network for Roku devices. If it finds one, it selects it; if it finds several, it asks you to choose. If discovery does not find a device, enter the Roku's IP address when prompted. You can also skip discovery by passing an address directly:

```bash
python3 roku_remote.py --ip 192.168.1.50
```

## Browser remote

Run the computer app with:

```bash
python3 roku_web.py
```

Open `http://localhost:8765` on that computer and enter the temporary access code printed in Terminal. To use a phone on the same home Wi-Fi, stop the server with **Control-C**, then restart it with:

```bash
python3 roku_web.py --lan
```

On your phone, open `http://COMPUTER_LOCAL_IP:8765` (find the computer's local IP in its network settings) and enter the access code shown in Terminal. The code changes each time the server starts. Use phone mode only on a trusted home network and stop the server when finished. No third-party Python packages are required.

## Controls

- Navigation and playback: Home, arrows, Select, Back, Play/Pause, rewind, fast forward, replay, and Info
- Type into a Roku search field from the browser remote when the Roku on-screen keyboard is open
- TV controls when supported: volume, mute, power off, tuner/channel, and HDMI/AV inputs
- List installed apps and launch one by its app ID
- Display Roku device information and reported TV control support
- Automatically discover Roku devices on your local network

TV power and volume commands from a streaming stick require HDMI-CEC support and settings enabled on both the Roku and TV. The micro-USB cable supplies power; HDMI carries CEC commands. A physical Roku remote may control TV functions using infrared (IR); a computer on the network cannot reproduce IR through the Roku API. If the stick is powered from the TV's USB port, use a wall adapter so it remains powered when the TV is off. Network discovery can be blocked by Wi-Fi/router isolation; in that case enter the Roku IP directly.

## Network note

This tool is intended for your own Roku on your local network. Do not expose Roku's control port to the public internet or add a router port-forward for it.
Discovery can be blocked by guest Wi-Fi or router settings that isolate devices from each other. In that case, use `--ip` and make sure the computer and Roku can communicate on the same network.

## Next steps

1. Add saved Roku profiles and improve app/device labels.
2. Add user-created routines with confirmation for actions such as changing inputs or powering off.
3. Explore more custom display layouts for the computer app. Roku's remote-control API controls the Roku; it does not replace Roku's home screen or create a new Roku system display.
