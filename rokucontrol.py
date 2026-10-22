from urllib.request import Request, urlopen

ROKU_IP = "192.168.0.44"  # Replace with your Roku's IP address

request = Request(
    f"http://{ROKU_IP}:8060/keypress/home",
    data=b"",
    method="POST",
)

with urlopen(request, timeout=3) as response:
    print("Roku replied:", response.status)