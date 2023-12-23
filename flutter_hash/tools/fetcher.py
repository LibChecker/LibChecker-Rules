import json
import os

import requests

url = 'https://storage.googleapis.com/flutter_infra_release/releases/releases_linux.json'
response = requests.get(url)

if response.status_code == 200:
    data = json.loads(response.text)
    hash_list = data['releases']

    folder_path = '../hash'
    os.makedirs(folder_path, exist_ok=True)

    for item in hash_list:
        hash_value = item['hash']
        file_path = os.path.join(folder_path, f'{hash_value}.json')

        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump(item, f)
                print(f"Saved {file_path}")
else:
    print(f"Failed to retrieve data. Status code: {response.status_code}")
