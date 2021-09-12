import xml.etree.ElementTree as ET


def language_strings():
    tree = ET.parse("assets/29oct2012/en_US.xml")
    root = tree.getroot()
    return {text.attrib["key"]: text[0].text for pkg in root for text in pkg}
