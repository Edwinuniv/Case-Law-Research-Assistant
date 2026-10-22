"""WEEK 1 GATE - does a citation exist?  (SR14: in our corpus / outside it / not found / cannot be read)
Usage: python -m scripts.check_citation "603 U.S. 593" "999 U.S. 9999" """
import sys
from app.citations import CitationIndex

index = CitationIndex()
for text in sys.argv[1:]:
    print(index.lookup(text))
