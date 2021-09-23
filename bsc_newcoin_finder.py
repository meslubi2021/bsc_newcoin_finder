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
PS_DEAD_MAX_HOLDERS_POSITION = 3
MIN_LIQUIDITY_POOL = 30000
MIN_TX_MINUTE = 8
EXIT_AFTER_FOUND_COINS = 4
#############################

"""
The script applies the following rules in order to select coins:
  0) The coin is "new"
1.1) Holders are more than ${MIN_HOLDERS}
1.2) The Liquidity Pool and Dead Coin Wallet appear among the largest ${PS_DEAD_MAX_HOLDERS_POSITION} holders
  2) The Liquidity Pool is higher than ${MIN_LIQUIDITY_POOL}. 
     We only use liquidity pools that appear in the first page of holders here.
  3) The Volume is higher than ${MIN_TX_MINUTE} transactions per minute

The script exits automatically after ${EXIT_AFTER_FOUND_COINS} coins are found

Usage:
    ./bsc_newcoin_finder.py
"""

lp_tokens = [
    '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c', # WBNB LP Holdings
    '0x55d398326f99059ff775485246999027b3197955', # BUSD-T LP Holdings
    '0xe9e7cea3dedca5984780bafc599bd69add087d56'  # BUSD LP Holdings
]

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

def rand_sleep(start, end):
    sleep(uniform(start, end))

def to_int(s):
    try:
        return int(s.replace(',', '').replace(' ', '').replace('\n', '').strip())
    except:
        return 0

def sync_fetch(url: str, session=None, headers=None):
    tried = 0
    while tried < 5:
        try:
            proxy = next(proxies, None)
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
    holders = 0
    headers = {
        'User-Agent': random_ua()
    }
    soup = BeautifulSoup(requests.get(url, headers=headers).content, "html.parser")
    holders_div = soup.find("div", {"id": "ContentPlaceHolder1_tr_tokenHolders"})
    if not holders_div:
        return False
    divs = holders_div.find_all('div')
    for d in divs:
        if "addresses" in d.get_text():
            holders = holders or to_int(d.get_text().split('addresses')[0])
    return holders >= MIN_HOLDERS

def ps_dead_ok(token):
    pancake, dead = 0, 0
    a_tokens = []
    max_index = 0
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
                if "dead" in link['href']: 
                    dead += 1
                    max_index = max(max_index, count)
                    break
            name = td.get_text(strip=True)
            if "PancakeSwap" in name: 
                pancake += 1
                max_index = max(max_index, count)
                if link and "a=" in link['href']:
                    a_tokens.append(link['href'].split('a=')[1]) #extract the `a` token params from href, used later to check the liquidity pools size  
                break
    max_position = max_index - pancake - dead + 3 
    return max_position <= PS_DEAD_MAX_HOLDERS_POSITION and pancake and dead, a_tokens

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

def lp_ok(a_tokens):
    total_lp = 0
    # probably there is a better way to do this
    # we should match `a` with the right `lp_token` in case there are multiple lp holdings
    for lp_token in lp_tokens:
        for a in list(a_tokens):
            with requests.Session() as s:
                headers = {
                    'User-Agent': random_ua()
                }
                soup = BeautifulSoup(s.get(f"https://bscscan.com/token/{lp_token}?a={a}", headers=headers).content,"html.parser")
                lp_div = soup.find("div", {"id": "ContentPlaceHolder1_divFilteredHolderValue"})
                lp_value = int(float(re.search("\$((\d+[,]?)+(\.\d+)?)", lp_div.get_text()).group(1).replace(",", "")))
                total_lp += lp_value
                if total_lp >= MIN_LIQUIDITY_POOL:
                    return True
                if lp_value > 0:
                    a_tokens.remove(a)
                rand_sleep(1, 3)
    return total_lp >= MIN_LIQUIDITY_POOL

def print_result(token, result, rule_desc):
    print(f"[{token}] {result} rule {rule_desc}")

def main():
    found_coin = 0
    while found_coin < EXIT_AFTER_FOUND_COINS:
        try:
            checked = set()
            soup = sync_bs('https://bscscan.com/tokentxns')
            for el in soup.css('#content td a'):
                href = get_attr(None, 'href', el)
                # rule 0: the coin is new
                if '/token/' in href and '/images/main/empty-token.png' in get_attr(
                        'img', 'src', el):
                    token = href.split("/token/")[-1]
                    url = f'https://bscscan.com{href}'
                    #poocoin_url = f'http://poocoin.app/tokens/{token}'
                    if url not in coins and token not in checked:
                        checked.add(token)

                        # rule 1, part 1 (holders count > MIN_HOLDERS)
                        if not holders_count_ok(url):
                            print_result(token, "failed", "1 part 1\nAbort!!!")
                            continue
                        print_result(token, "passed", "1 part 1")

                        # rule 1, part 2 (liq pool (PancakeSwap) and dead are in the top PS_DEAD_MAX_INDEX holders)
                        ps_dead_major_h, a_tokens = ps_dead_ok(token)
                        if not ps_dead_major_h:
                            print_result(token, "failed", "1 part 2\nAbort!!!")
                            continue
                        print_result(token, "passed", "1 part 2")

                        # rule 2: liquidity pool > MIN_LIQUIDITY_POOL
                        if a_tokens and not lp_ok(a_tokens):
                            print_result(token, "failed", "2\nAbort!!!")
                            continue
                        print_result(token, "passed", "2")

                        # rule 3: Volume > MIN_TX_MINUTE
                        if not volume_ok(token):
                            print_result(token, "failed", "3\nAbort!!!")
                            continue
                        print_result(token, "passed", "all Rules!\n")

                        coins.add(url)
                        found_coin+=1
                        webbrowser.open(url)
                        #webbrowser.open(poocoin_url)
                        rand_sleep(2, 4)
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
