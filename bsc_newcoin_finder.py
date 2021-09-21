import os
import traceback
import webbrowser
from itertools import cycle
from random import choice, uniform
from time import sleep
import requests
import re
from pydash import get as _
from selectolax.parser import HTMLParser
from bs4 import BeautifulSoup

####### configuration #######
MIN_HOLDERS = 250
PS_DEAD_MAX_INDEX = 2
MIN_LIQUIDITY_POOL = 30000
MIN_TX_MINUTE = 8
#############################

"""
The script applies the following rules in order to select coins:
0. The coin is "new"
1/1. Holders are more than ${MIN_HOLDERS}
1/2. The Liquidity Pool and Dead Coin Wallet appear among the largest ${PS_DEAD_MAX_INDEX} holders
2. The Liquidity Pool is higher than ${MIN_LIQUIDITY_POOL}
3. The Volume is higher than ${MIN_TX_MINUTE} transactions per minute

Usage:
    ./bsc_newcoin_finder.py
"""


USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.135 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.2 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.135 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.83 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:80.0) Gecko/20100101 Firefox/80.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.83 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.83 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.83 Safari/537.36'
]

def random_ua():
    return choice(USER_AGENTS)

def file2list(filename):
    result = []
    if os.path.isfile(filename):
        with open(filename, encoding='utf-8') as f:
            return f.read().splitlines()
    return []

def load_proxy():
    proxies = set()
    if os.path.exists('./proxy.txt'):
        with open('./proxy.txt', 'r') as f:
            for line in f:
                px = line.strip().split(':')
                proxies.add(f'http://{px[2]}:{px[3]}@{px[0]}:{px[1]}')
    return proxies

proxies = cycle(load_proxy())
coins = set(file2list('coins.txt'))

def get_text(selector: str, soup: HTMLParser):
    try:
        t = (soup.css_first(selector) if selector else soup).text(
            separator=' ', strip=True).replace('\xa0', ' ').replace(
                '\t', ' ').replace('\r', ' ').replace('\n', ' ').strip()
        while '  ' in t:
            t = t.replace('  ', ' ')
        return t
    except:
        return ''

def rand_sleep(start, end):
    sleep(uniform(start, end))

def to_int(s):
    try:
        return int(s.replace(',', '').replace(' ', '').strip())
    except:
        return 0

def sync_fetch(url: str, session=None, headers=None):
    tried = 0
    while tried < 5:
        try:
            proxy = next(proxies, None)
            #print(f'Getting {url}')
            return (session or requests).get(
                url,
                headers=headers if headers else {'User-Agent': random_ua()},
                timeout=30,
                proxies={
                    'http': proxy,
                    'https': proxy
                } if proxy else None)

        except KeyboardInterrupt:
            raise KeyboardInterrupt('Abort')
        except:
            traceback.print_exc()
            tried += 1
            sleep(1)


def get_next_elements(selector: str, next_selector, text, soup: HTMLParser):
    try:
        elements = []
        for el in soup.css(selector):
            t = el.text().replace('\xa0', ' ').strip()
            if text == t:
                start = False
                for cnode in el.parent.iter():
                    if cnode == el:
                        start = True
                    elif start:
                        elements.append(cnode)
        return elements
    except:
        return None


def get_attr(selector: str, attr: str, soup: HTMLParser):
    try:
        return (soup.css_first(selector) if selector else soup).attributes.get(
            attr, '').replace('\xa0', ' ').strip()
    except:
        return ''


def sync_bs(url: str, session=None):
    r = sync_fetch(url, session)
    soup = HTMLParser(r.text if r else '')
    return soup

def holders_count_ok(url):
    s = sync_bs(url)
    t = get_text(None, s)
    if 'LPs' in t or '-LP' in t or 'BLP' in t:
        return False
    els = get_next_elements('div', 'div', 'Holders:', s)
    if els:
        for node in els:
            text = get_text(None, node)
            if 'addresses' in text:
                holders = to_int(
                    text.split('addresses')[0])
                #print(holders, text)
    return holders >= MIN_HOLDERS

def ps_dead_ok(token):
    pancake_ok, dead_ok = False, False
    a_token = ""
    api_url = "https://bscscan.com/token/generic-tokenholders2"
    params = {
        "m": "normal",
        "a": token,
        "p": "1",
    }
    headers = {
        'User-Agent': random_ua()
    }
    soup = BeautifulSoup(requests.get(api_url, params=params, headers=headers).content, "html.parser")
    for count, row in enumerate(soup.select("tr:has(td)")):
        for td in row.select("td"):
            links = td.select('a[href]')
            if links:
                link = td.select('a[href]')[0]
                if "dead" in link['href']: dead_ok = True
            name = td.get_text(strip=True)
            if "PancakeSwap" in name: 
                pancake_ok = True
                if link and "a=" in link['href']:
                    a_token = link['href'].split('a=')[1] #extract the `a` token param from the href, we need it later to check the liquidity pool
        if count == PS_DEAD_MAX_INDEX: break
    #print("pancake is: "+str(pancake_ok))
    #print("dead is: "+str(dead_ok))       
    return pancake_ok and dead_ok, a_token

def get_minutes(ts):
    match = re.search(r'(?:(?P<h1>\d+)\shr[s]?\s(?P<m1>\d+)\smin)|(?:(?P<h2>\d+)\shr)|(?:(?P<mins>\d+)\smin)|(?:(?P<secs>\d+)\ssec)', ts)
    h1 = int(match.group('h1')) if match.group('h1') else 0
    h2 = int(match.group('h2')) if match.group('h2') else 0
    m1 = int(match.group('m1')) if match.group('m1') else 0
    mins = int(match.group('mins')) if match.group('mins') else 0
    secs = int(match.group('secs')) if match.group('secs') else 0
    hours = h1 + h2
    mins += m1
    return hours * 60 + mins + secs / 60

def volume_ok(token):
    with requests.Session() as s:
        headers = {
            'User-Agent': random_ua()
        }
        c = s.get(f"https://bscscan.com/token/{token}", headers=headers).text

        try:
            sid = re.search("sid\s=\s'(.*)';", c).group(1)
        except AttributeError: 
            return True # I guess we'll just skip this whole check then...

        api_url = "https://bscscan.com/token/generic-tokentxns2"
        params = {
            "m": "normal",
            "contractAddress": token,
            "sid": sid,
            "p": "1"
        }
        soup = BeautifulSoup(s.get(api_url, params=params, headers=headers).content, "html.parser")

        allTS = soup.find_all("td", class_="showAge")
        count = len(allTS)
        lastTS = allTS[count-1]
        lastTSTimeMin = get_minutes(lastTS.get_text())
        return count // lastTSTimeMin > MIN_TX_MINUTE

def lp_ok(a):
    with requests.Session() as s:
        headers = {
            'User-Agent': random_ua()
        }
        soup = BeautifulSoup(s.get(f"https://bscscan.com/token/0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c?a={a}", headers=headers).content,"html.parser")
        lp_div = soup.find("div", {"id": "ContentPlaceHolder1_divFilteredHolderValue"})
        lp_value = int(float(re.search("\$((\d+[,]?)+(\.\d+)?)", lp_div.get_text()).group(1).replace(",", "")))
    return lp_value >= MIN_LIQUIDITY_POOL

def print_result(token, result, rule_id):
    print("["+token+"] "+result+" rule "+rule_id)

def main():
    while True:
        try:
            soup = sync_bs('https://bscscan.com/tokentxns')
            for el in soup.css('#content td a'):
                href = get_attr(None, 'href', el)
                # rule 0: the coin is new
                if '/token/' in href and '/images/main/empty-token.png' in get_attr(
                        'img', 'src', el):
                    token = href.split("/token/")[-1]
                    url = f'https://bscscan.com{href}'
                    poocoin_url = f'http://poocoin.app/tokens/{token}'
                    if url not in coins:
                        # rule 1, part 1 (holders count > x)
                        if not holders_count_ok(url):
                            print_result(token, "failed", "1 part 1\n")
                            continue
                        print_result(token, "passed", "1 part 1")

                        # rule 1, part 2 (liq pool (PancakeSwap) and dead are in the top y holders)
                        ps_dead_major_h, a_token = ps_dead_ok(token)
                        if not ps_dead_major_h:
                            print_result(token, "failed", "1 part 2\n")
                            continue
                        print_result(token, "passed", "1 part 2")

                        # rule 2: liquidity pool > z
                        if a_token and not lp_ok(a_token):
                            print_result(token, "failed", "2\n")
                            continue
                        print_result(token, "passed", "2")

                        # rule 3: Volume > w
                        if not volume_ok(token):
                            print_result(token, "failed", "3\n")
                            continue
                        print_result(token, "passed", "All Rules\n")

                        coins.add(url)
                        webbrowser.open(url)
                        webbrowser.open(poocoin_url)
            rand_sleep(1, 3)
        except KeyboardInterrupt:
            return
        except:
            traceback.print_exc()
            sleep(1)


if __name__ == '__main__':
    try:
        main()
    finally:
        with open('coins.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(coins))
