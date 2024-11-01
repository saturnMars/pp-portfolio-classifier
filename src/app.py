from components.classifier import PortfolioPerformanceFile
from components.isin2secid import Isin2secid
from utils.taxonomies import taxonomies
from tqdm import tqdm

from shutil import copyfile
from os import path, getcwd
from win11toast import toast

from multiprocessing import Process
import logging

if __name__ == '__main__':
      
      logging.basicConfig(filename = path.join('_tmp','app.log'), filemode='a+', 
                          format='%(asctime)s-%(levelname)s-%(message)s', level=logging.INFO)
      logging.info('Starting the app')

      # INPUT
      data_folder = path.join('..', '..', 'Portfolio Perfomance')
      file_name = "PAC.xml"
      input_path = path.join(data_folder, file_name)
      
      # Load cache
      Process(target = Isin2secid.load_cache()).start()

      # Backup the file
      backup_fileName = path.splitext(file_name)[0] + '_backup.xml'
      copyfile(input_path, path.join('_tmp', backup_fileName))

      # Load the portfolio
      pp_file = PortfolioPerformanceFile(input_path)
      print(f'\nPortfolio Performance file ({file_name}) has been loaded.\n')

      # Add the taxonomies
      taxonomies_to_skip = ['Asset-Type', 'MSCI Regions']
      processes = [Process(target = pp_file.add_taxonomy, args=(taxonomy,)) 
                  for taxonomy in taxonomies if taxonomy not in taxonomies_to_skip]
      [process.start() for process in tqdm(processes, desc='Adding taxonomies')]
      [process.join() for process in processes]
      
      # Save the ids
      Isin2secid.save_cache()

      # Write the enhanced portfolio
      output_path = path.join(data_folder, file_name)
      pp_file.write_xml(output_path)

      # Window Message
      toast('Taxonomy updated', f'The file "{file_name}" is now updated up to date', 
            icon = path.join(getcwd(), 'src', 'utils', 'notification.ico'),
            audio = {'silent': 'true'},
      )