
import json
import urllib.parse
import urllib.request

print("Inspecting NYC bus ridership dataset columns...")

API_URL = "https://data.ny.gov/resource/gxb3-akrn.json"

params = urllib.parse.urlencode({
    "$limit": 1
})

url = API_URL + "?" + params

try:
    with urllib.request.urlopen(url, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))

    if data:
        print("\nAVAILABLE COLUMN NAMES:\n")

        for column in data[0].keys():
            print(column)

        print("\nSAMPLE RECORD:\n")
        print(json.dumps(data[0], indent=4))

    else:
        print("No records returned.")

except Exception as e:
    print("Error retrieving dataset:", e)
