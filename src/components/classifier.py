import xml.etree.ElementTree as ET
import uuid
from os import path, makedirs
from itertools import cycle
from typing import NamedTuple
from collections import defaultdict
from numpy import floor

# LOCAL IMPORT
from utils.CONSTANTS import COLORS
from components.holdings import Security
from components.create_taxonomyElement import createTaxonomyElement

class PortfolioPerformanceCategory(NamedTuple):
    name: str
    color: str
    uuid: str    
    
class PortfolioPerformanceFile:

    def __init__ (self, filepath):
        self.filepath = filepath
        self.pp_tree = ET.parse(filepath)
        self.pp = self.pp_tree.getroot()
        self.securities = None
        self.updateDate = None

    def get_security(self, security_xpath):
        """return a security object """
        security =  self.pp.findall(security_xpath)[0]
        if security is not None:
            isin = security.find('isin').text
            secid = security.find('secid')
            
            if secid is not None:
                secid = secid.text
            return Security(
                name = security.find('name').text,
                ticker = security.find('tickerSymbol').text,
                ISIN = isin,
                secid = secid,
                UUID = security.find('uuid').text,
            )
        return None

    def get_security_xpath_by_uuid (self, uuid):
        for idx, security in enumerate(self.pp.findall(".//securities/security")):
            sec_uuid =  security.find('uuid').text
            if sec_uuid == uuid:
                return f"../../../../../../../../securities/security[{idx + 1}]"

    def add_taxonomy (self, taxonomyName, overwrite = False):
        securities = self.get_securities()

        # Remove the existing taxonomy
        pos_taxonomy = -1
        taxonomies = self.pp.find('taxonomies')
        for idk_taxonomy, taxonomy in enumerate(taxonomies):
            if taxonomy.find('name').text == taxonomyName:
                pos_taxonomy = idk_taxonomy
                if overwrite:
                    taxonomies.remove(taxonomy)

        unique_categories = defaultdict(list)
        rank = 1
        fund_names = []

        colors = cycle(COLORS)
        for security in securities:
            security_h = security.holdings

            fund_names.append({
                'name': security.name, 
                "uuid": str(uuid.uuid4()), 
                "color": next(colors),
                'kind': taxonomyName
            })

            security_assignments = security_h.group_by_key(taxonomyName)

            # Single categories
            for category, weight in security_assignments.items():
                alt_weight = int(weight * 100)
                if alt_weight > 0:
                    unique_categories[category].append({
                        "security_xpath":self.get_security_xpath_by_uuid(security.UUID),
                        'security_name': security.name, 
                        "weight": int(floor(weight * 100)), # weight of the category in the security (FORMAT: e.g., 11.68 --> 1168)
                        "rank": rank
                    })
                    rank += 1
        categories = []
        for category, assignments in unique_categories.items():
            cat_weight = 0
            for assignment in assignments:
                cat_weight += assignment['weight']
            
            # Clear the category name
            for prefix in ['Inc', 'Ltd', 'Nv']:
                category = category.replace(prefix, '')
            category = category.replace(r'&amp;', '&').strip()

            if taxonomyName == 'ESG Risk':
                esg_colors = {'Negligible': '#2E7D32', 'Low' : '#8BC34A', 'Medium': '#FF9800',  'High': '#EF5350', 'Severe': '#C62828'}
                cat_color = esg_colors[category]
            else: 
                cat_color = next(colors)

            categories.append({
                "name": category,
                "uuid": str(uuid.uuid4()),
                "color": cat_color,
                "assignments": assignments,
                "weight": cat_weight
            })

        if taxonomyName in ['Holding']:
           parent_categories = fund_names

        elif taxonomyName == 'Stock-style':
            macro_categories_names = defaultdict(list)
            for category in categories:
                macroName = category['name'].split()[-1]
                macro_categories_names[macroName].append(category['name'])

            parent_categories = []
            for macroName in macro_categories_names.keys():
                parent_categories.append({'name':macroName,  "uuid": str(uuid.uuid4()), "color": next(colors), 'kind': taxonomyName})
            parent_categories = None
        else:
            parent_categories = None

        new_XML_taxonomy = createTaxonomyElement(
            taxonomyName = taxonomyName, 
            parent_categories = parent_categories,
            taxonomyCategories = categories,
            id = taxonomies[pos_taxonomy].find('id').text if pos_taxonomy != -1 else None)

        if overwrite:
            taxonomies.insert(pos_taxonomy, new_XML_taxonomy)
        elif pos_taxonomy == -1:
            taxonomies.append(new_XML_taxonomy)
        else:
            taxonomies[pos_taxonomy] = new_XML_taxonomy

    def write_xml(self, output_file):
        folder = path.dirname(output_file)
        if not path.exists(folder):
            makedirs(folder)
    
        with open(output_file, 'wb+') as xml_file:
            self.pp_tree.write(xml_file)

    def dump_xml(self):
        print (ET.tostring(self.pp, encoding="unicode"))

    def get_securities(self):
        if self.securities is None:
            self.securities = []
            sec_xpaths = []
            for transaction in self.pp.findall('.//portfolio-transaction'): 
                for child in transaction:
                    if child.tag == "security":
                        sec_xpaths.append('.//'+ child.attrib["reference"].split('/')[-1])
    
            for sec_xpath in list(set(sec_xpaths)):
                security = self.get_security(sec_xpath)
                self.updateDate = security.get_updateDate()
                
                if security is not None:
                    security_h = security.load_holdings()
                    if security_h.secid !='':
                        self.securities.append(security)
        self.securities = sorted(self.securities, key = lambda security: security.ticker, reverse=True)

        return self.securities
    
    def get_updateDate(self):
        return self.updateDate

def print_class(grouped_holding):
    for key, value in sorted(grouped_holding.items(), reverse=True):
        print (key, "\t\t{:.2f}%".format(value))
    print ("-"*30)