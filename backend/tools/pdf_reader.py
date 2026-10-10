from pathlib import Path
from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS_DIR = PROJECT_ROOT / "documents"


def read_pdf(filename):
    pdf_path = (DOCUMENTS_DIR / filename).resolve()

    if not pdf_path.is_relative_to(DOCUMENTS_DIR.resolve()):
        raise ValueError("Chemin de fichier non autorisé.")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Le fichier doit être au format PDF.")

    if not pdf_path.is_file():
        raise FileNotFoundError(
            f"Fichier PDF introuvable : {pdf_path.name}"
        )

    reader = PdfReader(str(pdf_path))

    if reader.is_encrypted:
        raise ValueError("Ce PDF est protégé par un mot de passe.")

    pages_text = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text()

        if text and text.strip():
            pages_text.append(
                f"Page {page_number}\n{text.strip()}"
            )

    if not pages_text:
        raise ValueError(
            "Aucun texte extractible. Le PDF est peut-être scanné."
        )

    return "\n\n".join(pages_text)


if __name__ == "__main__":
    filename = input("Nom du fichier PDF dans documents : ").strip()

    try:
        content = read_pdf(filename)
        print("\nTexte extrait du PDF :\n")
        print(content[:5000])
        print(f"\nNombre de caractères extraits : {len(content)}")
    except (ValueError, FileNotFoundError) as error:
        print(f"Erreur : {error}")