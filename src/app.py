from components.classifier import PortfolioPerformanceFile
from components.isin2secid import Isin2secid
from utils.taxonomies import taxonomies

from shutil import copyfile
from os import path

if __name__ == '__main__':

    # INPUT
    data_folder = path.join('..', '..', 'Portfolio Perfomance')
    file_name = "PAC.xml"
    input_path = path.join(data_folder, file_name)
    
    # Load cache
    Isin2secid.load_cache()

    # Backup the file
    backup_fileName = path.splitext(file_name)[0] + '_backup.xml'
    copyfile(input_path, path.join('_tmp', backup_fileName))

    # Load the portfolio
    pp_file = PortfolioPerformanceFile(input_path)

    # Add the taxonomies
    taxonomies_to_skip = ['Asset-Type', 'MSCI Regions']
    for taxonomy in taxonomies:
        if taxonomy not in taxonomies_to_skip:
            pp_file.add_taxonomy(taxonomy)

    # Save the ids
    Isin2secid.save_cache()

    # Write the enhanced portfolio
    output_path = path.join(data_folder, file_name)
    pp_file.write_xml(output_path)