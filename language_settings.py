import xml.etree.ElementTree as ET
from save_engine import install_path
import os


def language_strings():
    tree = ET.parse(os.path.join(install_path(), "assets/29oct2012/en_US.xml"))
    root = tree.getroot()
    return {text.attrib["key"]: text[0].text for pkg in root for text in pkg}
