from bs4 import BeautifulSoup 
from typing import NamedTuple
from xml.sax.saxutils import escape
from collections import defaultdict
from jsonpath_ng import parse
from datetime import datetime
from tqdm import tqdm

import numpy as np
import json
import requests
import re

from utils.CONSTANTS import DOMAIN, NUM_HOLDINGS_FOR_ETF, NUM_VISUALISE_HOLDINGS
from components.isin2secid import Isin2secid
from utils.taxonomies import taxonomies

class Security:
 
    def __init__ (self, **kwargs):
        self.__dict__.update(kwargs)
        self.holdings = []
        self.updateDate = None
        self.verbose = False

    def load_holdings(self):
        if self.verbose:
            print('\n' + '-' * 100, "\n" + '-' * 100, "\n" +  '-' * 33 + f" {self.ticker.split('.')[0]}: {self.name} " + '-' * 33 , "\n" + '-' * 100, "\n" + '-' * 100)
        if len(self.holdings) == 0:
            self.num_holdings = NUM_HOLDINGS_FOR_ETF
            self.holdings = SecurityHoldingReport(NUM_HOLDINGS_FOR_ETF)
            self.holdings.load(isin = self.ISIN, secid = self.secid)
            self.updateDate = self.holdings.updateDate
        return self.holdings
    
    def get_updateDate(self):
        return self.updateDate

class SecurityHolding(NamedTuple):
    name: str
    isin: str
    country: str
    industry: str
    currency: str
    percentage: float


class Holding(NamedTuple):
    name: str
    percentage: float

class SecurityHoldingReport:
    def __init__ (self, num_holdings):
        self.secid=''
        self.num_holdings = num_holdings
        
        self.verbose = False

    def get_bearer_token(self, secid, domain):
        # the secid can change for retrieval purposes
        # find the retrieval secid
        headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36'}
        url = f'https://www.morningstar.{domain}/{domain}/funds/snapshot/snapshot.aspx?id={secid}'
        response = requests.get(url, headers=headers)
        secid_regexp = r"var FC =  '(.*)';"
        matches = re.findall(secid_regexp, response.text)
        if len(matches)>0:
            secid_to_search = matches[0]
        else:
            secid_to_search = secid
            
        # get the bearer token for the new secid
        url = f'https://www.morningstar.{domain}/Common/funds/snapshot/PortfolioSAL.aspx'
        payload = {'FC': secid_to_search}
        response = requests.get(url, headers=headers, params=payload)
        token_search = re.findall(r'maasToken = "(.+)";', response.text, re.IGNORECASE) # OLD: tokenMaaS\:\s\"(.+)\"
        resultstringtoken = token_search[0].strip()
        return resultstringtoken, secid_to_search

    def calculate_grouping(self, categories, percentages, grouping_name, long_equity):
        for category_name, percentage in zip(categories, percentages):
            self.grouping[grouping_name][escape(category_name)] += percentage  

        if grouping_name !='Asset-Type':
            self.grouping[grouping_name] = {k:v*long_equity for k, v in 
                                            self.grouping[grouping_name].items()}

    def load(self, isin, secid):
        secid, secid_type, domain = Isin2secid.get_secid(isin)
        if secid == '':
            print(f"isin {isin} not found in Morningstar for domain '{DOMAIN}', skipping it... Try another domain with -d <domain>")
            return
        elif secid_type=="stock":
            print(f"isin {isin} is a stock, skipping it...")
            return
        self.secid = secid
        bearer_token, secid = self.get_bearer_token(secid, domain)
        #print('\n' + '-' * 100 + '\n' + '-' * 100 + f"\nRetrieving data for {secid_type} {isin} ({secid}) using domain '{domain}'...\n" + '-' * 100 + '\n' + '-' * 100)
        headers = {
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'it,it-IT;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Authorization': f'Bearer {bearer_token}',
            }
        
        params = {
            'premiumNum': str(self.num_holdings),
            'freeNum': str(self.num_holdings),
            'languageId': 'en-GB',
            'locale': 'en-GB',
            'clientId': 'MDC_intl',
            'benchmarkId': 'category', #"mstarorcat", #'category',
            'version': '3.60.0',
        }
        
        self.grouping = dict()
        for taxonomy in taxonomies:
            self.grouping[taxonomy] = defaultdict(float)

        non_categories = ['avgMarketCap', 'portfolioDate', 'name', 'masterPortfolioId' ]
        json_not_found = False
        for idk, (taxonomyName, taxonomy) in enumerate(taxonomies.items()):
            
            if self.verbose:
                print('\n' + "-" * 20, f'({idk + 1})', taxonomyName, f'({isin})', "-" * 20)

            params['component'] = taxonomy['component']
            url = taxonomy['url'] + secid + "/data"
            url = url.replace("{type}", secid_type)
           
            if taxonomyName == 'Holding':
                params['premiumNum'] = NUM_VISUALISE_HOLDINGS
                params['freeNum'] =  NUM_VISUALISE_HOLDINGS

            resp = requests.get(url, params=params, headers=headers)

            try:
                response = resp.json()

                if 'fundPortfolio' in response.keys():
                    self.updateDate = response['fundPortfolio']['portfolioDate'].split('T')[0] 
                
                #with open('app/_tmp/raw_response.json', 'w+') as jFile:
                #    json.dump(response, jFile)

                jsonpath = parse(taxonomy['jsonpath'])
                percent_field = taxonomy['percent']

                # single match of the jsonpath means the path contains the categories
                if len(jsonpath.find(response)) == 1:
                    value = jsonpath.find(response)[0].value 
                    keys = [key for key in value if key not in non_categories]
                    
                    if percent_field != "":
                        if value[keys[0]][percent_field] is not None:
                            percentages = [float(value[key][percent_field]) for key in keys]
                        else:
                            percentages =[]
                    else:
                        if value[keys[0]] is not None:
                            
                            percentages = [float(value[key]) for key in keys]
                        else:
                            percentages = []
                        
                    if taxonomyName == 'Asset-Type':
                        try:
                            long_equity = (float(value.get('assetAllocEquity',{}).get('longAllocation',0)) +
                                      float(value.get('AssetAllocNonUSEquity',{}).get('longAllocation',0)) +           
                                      float(value.get('AssetAllocUSEquity',{}).get('longAllocation',0)))/100
                        except TypeError:
                            print(f"No information on {taxonomyName} for {secid}")

                else:
                    # every match is a category
                    value = jsonpath.find(response)
                    keys = [key.value[taxonomy['category']] for key in value if key.value[taxonomy['category']] is not None]

                    if taxonomyName in ['Currency', 'ESG Risk']:
                        unique, counter = np.unique(keys, return_counts = True)
                        counter = (counter / len(keys)) * 100
                        currencies = dict(zip(unique, counter))
                        currencies = dict(sorted(currencies.items(), key = lambda item: item[1], reverse = True))
  
                        percentages = list(currencies.values())
                        keys = list(currencies.keys())
                    else:
                        percentages = [float(key.value[taxonomy['percent']]) for key in value]

                # Map names if there is a map
                if len(taxonomy.get('map',{})) != 0:
                    
                    categories, unmapped_categories = [], []
                    for key in keys:
                        if key in taxonomy['map'].keys():
                            categories.append(taxonomy['map'][key])
                        else:
                            categories.append(key)
                            unmapped_categories.append(key)
                    categories = list(map(str.title, categories))

                    #if unmapped_categories:
                    #    print(f"[{secid}] Categories not mapped: {(unmapped_categories)}")
                else:
                    categories = list(map(str.title, keys))

                if percentages:
                    self.calculate_grouping(categories, percentages, taxonomyName, long_equity)
                
                if self.verbose:
                    print(f"--> OK: {len(categories)} categories found (e.g., {', '.join(categories[:3])}, ...).")
            except json.JSONDecodeError:
                print(f"Problem with {taxonomyName.upper()} for secid {secid} in PortfolioSAL...")
                json_not_found = True
                #break
            
        if json_not_found:
            
            non_categories = ['Defensive', 'Cyclical',  'Sensitive',
                              'Greater Europe', 'Americas', 'Greater Asia']
            url = "https://lt.morningstar.com/j2uwuwirpv/xray/default.aspx?LanguageId=en-EN&PortfolioType=2&SecurityTokenList=" + secid + "]2]0]FOESP%24%24ALL_1340&values=100"
            #print(url)
            resp = requests.get(url, headers=headers)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for grouping_name, taxonomy in taxonomies.items():
                if grouping_name in self.grouping:
                    continue
                print('\n' + "-" * 20, f'({idk + 1})', taxonomyName, f'({isin})', "-" * 20)

                table = soup.select("table.ms_data")[taxonomy['table']]
                trs = table.select("tr")[1:]
                if grouping_name == 'Asset-Type':
                    long_equity = float(trs[0].select("td")[0].text.replace(",","."))/100
                categories = []
                percentages = []
                for tr in trs:
                    if len(tr.select('th'))>0:
                        header = tr.th
                    else:
                        header = tr.td
                    if tr.text != '' and header.text not in non_categories:
                        categories.append(header.text)                                     
                        if len(tr.select("td")) > taxonomy['column']:
                            percentages.append(float('0' + tr.select("td")[taxonomy['column']].text.replace(",",".").replace("-","")))
                        else:
                            percentages.append(0.0)
                if len(taxonomy.get('map2',{})) != 0:
                    categories = [taxonomy['map2'][key] for key in categories]
        
                self.calculate_grouping(categories, percentages, grouping_name, long_equity)

                print(f"--> OK: {len(categories)} categories found (e.g., {', '.join(categories[:3])}, ...).")
        
        
    def group_by_key(self,key):
        group = dict(sorted(self.grouping[key].items(), key= lambda item: item[1], reverse=True))
        return group