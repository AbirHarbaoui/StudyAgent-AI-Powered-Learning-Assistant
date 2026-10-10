import os
import sys

# Ajouter le dossier backend au chemin de recherche de Python
backend_path = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
sys.path.append(backend_path)

from llm import ask_llm


def summarize(text):
    prompt = f"""
Résume le texte suivant de manière simple et concise.

Garde uniquement les informations importantes.
Ne donne pas ton avis.
Réponds en français.

Texte :
{text}
"""

    return ask_llm(prompt)


if __name__ == "__main__":
    text = input("Texte à résumer : ")

    summary = summarize(text)

    print("\nRésumé :")
    print(summary)