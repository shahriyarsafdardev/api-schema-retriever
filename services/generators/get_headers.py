import matplotlib.pyplot as plt
from services.helpers.s3 import read_object, list_objects
from services.helpers.json_loader import load_connectors
from urllib.parse import quote
import re

def get_headers(content):
    regex_matcher = re.compile(r"(^#{1}.*?$)", re.MULTILINE)  # regex for markdown headers
    matches = regex_matcher.findall(content) 
    return matches 

connectors = load_connectors('data/airbyte_connectors.json', local=True)

# Create a dictionary to store each connector and the total number of characters in its .md files
connector_character_counts = {}

for connector in connectors:
    files = list_objects([quote(connector['base_url'], safe=""), ".md"])
    bulk_concise = read_object(quote(connector['base_url'], safe="") + '-bulk-concise' + '.md')
    
    # Check if bulk_concise is a string before processing
    if isinstance(bulk_concise, str):
        total_characters = 0

        # Read the content of each markdown file, get its length, and add it to the total
        for file in files:
            file_content = read_object(file)
            total_characters += len(file_content)

        # Store the total number of characters in the dictionary
        connector_character_counts[connector['name']] = total_characters

# Create a bar chart to display the total number of characters in .md files for each connector
plt.bar(connector_character_counts.keys(), connector_character_counts.values())
plt.xlabel('Connector')
plt.ylabel('Total number of characters')
plt.title('Total number of characters in .md files for each connector')
plt.xticks(rotation=90)
plt.show()
