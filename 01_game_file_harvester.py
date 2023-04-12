import requests
from bs4 import BeautifulSoup
import os
import time

OUTPUT_DIR = './Output/'

def get_game_list(page_number):
    page = requests.get(f'http://gokifu.com/index.php?p={page_number}')
    if page.status_code != 200:
        raise RuntimeError(f'Got {page.status_code} on page {page_number}')
    soup = BeautifulSoup(page.content, 'html.parser')
    games = soup.find_all(class_='game_type')
    links = []
    for game in games[1:]:
        links.append(game.find_all('a')[1].attrs['href'])
    return links


for page_number in range(2582):
    print(f'Downloading page {page_number}...')
    links = get_game_list(page_number)
    for link in links:
        file_name = link.split('/')[-1]
        full_file_path = f'{OUTPUT_DIR}{file_name}'
        if os.path.exists(full_file_path):
            print(f'Skipping {full_file_path}')
            continue

        print(f'Downloading {file_name}')
        page = requests.get(link)
        if page.status_code != 200:
            raise RuntimeError(f'Got {page.status_code} on page {page_number} file {file_name}')
        with open(full_file_path, 'w') as fp:
            fp.write(page.content.decode())
        time.sleep(0.5)

print('Done.')


