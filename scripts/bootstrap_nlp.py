import nltk
import spacy
from spacy.cli import download

SPACY_MODEL = "en_core_web_trf"


def ensure_spacy_model() -> None:
    try:
        spacy.load(SPACY_MODEL)
        print(f"spaCy model already installed: {SPACY_MODEL}")
    except OSError:
        print(f"Installing spaCy model: {SPACY_MODEL}")
        download(SPACY_MODEL)


def ensure_nltk_data() -> None:
    for corpus in ("punkt", "wordnet", "stopwords"):
        nltk.download(corpus)


if __name__ == "__main__":
    ensure_spacy_model()
    ensure_nltk_data()
    print("NLP bootstrap complete.")
