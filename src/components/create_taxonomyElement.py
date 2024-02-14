from collections import defaultdict
import xml.etree.ElementTree as ET
import uuid

def createTaxonomyElement(taxonomyName, taxonomyCategories, parent_categories = None, id = None):

    # XML: root taxonomy element
    new_taxonomy = ET.Element('taxonomy')
    ET.SubElement(new_taxonomy, 'id').text = id if id else str(uuid.uuid4())
    ET.SubElement(new_taxonomy, 'name').text = str(taxonomyName)

    # XML: sub-root  taxonomy elements
    taxonomy_root = ET.SubElement(new_taxonomy, 'root')
    ET.SubElement(taxonomy_root, 'id').text = str(uuid.uuid4())
    ET.SubElement(taxonomy_root, 'name').text = str(taxonomyName)
    ET.SubElement(taxonomy_root, 'color').text = '#737373'

    main_entryPoint = ET.SubElement(taxonomy_root, 'children')

    if parent_categories:
        macro_children = dict()
        for idk_macro, macro_category in enumerate(parent_categories):

            category_element = ET.Element('classification')
            ET.SubElement(category_element, 'id').text = str(macro_category["uuid"])
            ET.SubElement(category_element, 'name').text = macro_category["name"]
            ET.SubElement(category_element, 'color').text = str(macro_category["color"])
            ET.SubElement(category_element, 'parent').set('reference', "../../..")

            ET.SubElement(category_element, 'children')
            
            ET.SubElement(category_element, 'assignments')
            ET.SubElement(category_element, 'weight').text = str(int(round(10000 / len(parent_categories), 0)))
            ET.SubElement(category_element, 'rank').text = str(idk_macro)

            macro_children[macro_category["name"]] = category_element

    # XML: Actual taxonomy elements (first level) 
    main_children = defaultdict(list)
    fund_counter = defaultdict(int)
   
    for main_category in taxonomyCategories:

        category_element = ET.Element('classification')
        ET.SubElement(category_element, 'id').text = str(main_category["uuid"])
        ET.SubElement(category_element, 'name').text = main_category["name"]
        ET.SubElement(category_element, 'color').text = str(main_category["color"])
        ET.SubElement(category_element, 'parent').set('reference', "../../..")

        ET.SubElement(category_element, 'children')

        # Security origin (i.e., ETF)
        assignments = ET.SubElement(category_element, 'assignments')
        categories = set() 
        for assignment in main_category["assignments"]:
            fund_element = ET.SubElement(assignments, 'assignment')

            origin = ET.SubElement(fund_element, 'investmentVehicle')
            origin.set('class', 'security')

            security_path = str(assignment["security_xpath"])
            if parent_categories:
                pos = security_path.index('securities')
                security_path = security_path[:pos -1] + '/../../' + security_path[pos:] 
                rank = fund_counter[assignment["security_name"]]
                fund_counter[assignment["security_name"]] += 1 

                if parent_categories[0]['kind'] == 'Holding':
                    categories.add(assignment["security_name"])
            else:
                rank = 1

            origin.set('reference', security_path)

            ET.SubElement(fund_element, 'weight').text = str(assignment["weight"])
            ET.SubElement(fund_element, 'rank').text = str(assignment["rank"])

            if parent_categories and len(categories) == 0:
                for item in parent_categories:
                    if item['kind'] in main_category["name"]:
                        categories.add(item['kind'])

        ET.SubElement(category_element, 'weight').text = str(0)
        ET.SubElement(category_element, 'rank').text = str(rank)
       
        if parent_categories:
            for category in categories:
                main_children[category].append(category_element)
        else:
            main_children['all_item'].append(category_element)
    # -----------------------------------------------------------------
    
    # Add the main category 
    if parent_categories != None:
        for macro_name, children in macro_children.items():
            entry_point = children.find('children')
            for item in main_children[macro_name]:
                entry_point.append(item)
            main_entryPoint.append(children)
    else:
        for item in main_children.values():
            main_entryPoint.extend(item)

    ET.SubElement(taxonomy_root, 'assignments')
    ET.SubElement(taxonomy_root, 'weight').text = str(10000)
    ET.SubElement(taxonomy_root, 'rank').text = str(0)

    return new_taxonomy