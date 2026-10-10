import json
import re

from llm import ask_llm
from tools.calculator import calculate
from tools.summary import summarize
from tools.quiz import run_quiz
from tools.pdf_reader import read_pdf


def choose_action(question):
    prompt = f"""
Tu es le contrôleur d'un agent IA pédagogique appelé StudyAgent.

Choisis l'outil le plus adapté à la demande.

Outils disponibles :

1. calculator
Pour les calculs mathématiques.
Format :
{{"tool": "calculator", "a": 25, "b": 18, "operation": "add"}}

Opérations : add, subtract, multiply, divide.

2. summary
Pour résumer un texte ou un cours fourni directement.
Format :
{{"tool": "summary"}}

3. quiz
Pour créer un quiz à partir d'un cours fourni directement.
Format :
{{"tool": "quiz"}}

4. question
Pour répondre à une question ou expliquer un concept.
Format :
{{"tool": "question"}}

5. pdf_summary
Pour résumer un fichier PDF présent dans le dossier documents.
Format :
{{"tool": "pdf_summary"}}

6. pdf_quiz
Pour créer un quiz depuis un fichier PDF.
Format :
{{"tool": "pdf_quiz"}}

Exemples :

Demande : Combien font 25 + 18 ?
Réponse : {{"tool": "calculator", "a": 25, "b": 18, "operation": "add"}}

Demande : Combien font 25 multiplié par 18 ?
Réponse : {{"tool": "calculator", "a": 25, "b": 18, "operation": "multiply"}}

Demande : Résume ce texte : Le Machine Learning apprend à partir des données.
Réponse : {{"tool": "summary"}}

Demande : Génère un quiz sur le Machine Learning.
Réponse : {{"tool": "quiz"}}

Demande : Explique-moi le Deep Learning.
Réponse : {{"tool": "question"}}

Demande : Résume le PDF cours.pdf.
Réponse : {{"tool": "pdf_summary"}}

Demande : Résume le fichier Cours.pdf.
Réponse : {{"tool": "pdf_summary"}}

Demande : Génère un quiz à partir du PDF cours.pdf.
Réponse : {{"tool": "pdf_quiz"}}

Règles :
- Retourne uniquement un objet JSON valide.
- N'ajoute aucun texte avant ou après le JSON.
- N'invente pas de nombres pour un calcul.
- Utilise uniquement les outils disponibles.
- Si un fichier PDF est mentionné, choisis pdf_summary ou pdf_quiz selon la demande.
- Si l'utilisateur demande un résumé d'un PDF, choisis pdf_summary.
- Si l'utilisateur demande un quiz à partir d'un PDF, choisis pdf_quiz.

Demande utilisateur :
{question}
"""

    decision = ask_llm(prompt).strip()

    if decision.startswith("```"):
        decision = decision.replace("```json", "", 1)
        decision = decision.replace("```", "").strip()

    start = decision.find("{")
    end = decision.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("La décision de l'agent n'est pas un JSON valide.")

    result = json.loads(decision[start:end + 1])

    if not isinstance(result, dict):
        raise ValueError("La décision doit être un objet JSON.")

    return result


def extract_content(question, prefixes):
    normalized_question = question.lower()

    for prefix in prefixes:
        if normalized_question.startswith(prefix):
            return question[len(prefix):].strip()

    return question.strip()


def extract_pdf_filename(question):
    """
    Extrait uniquement le nom du PDF, sans les mots de la demande.
    Exemple : 'Résume le PDF cours.pdf' -> 'cours.pdf'
    """
    match = re.search(
        r"""["']?([A-Za-z0-9À-ÿ_() -]+\.pdf)\b["']?""",
        question,
        re.IGNORECASE
    )

    if not match:
        return None

    filename = match.group(1).strip()

    # Si le modèle ou la demande inclut un préfixe,
    # conserve uniquement le nom de fichier après le dernier espace.
    filename = re.split(
        r"\b(?:pdf|fichier)\s+",
        filename,
        flags=re.IGNORECASE
    )[-1].strip()

    return filename


def run_agent(question):
    question = question.strip()

    if not question:
        return "Veuillez saisir une question."

    print("Agent : analyse de la demande...")

    # Détecter directement les demandes PDF simples.
    # Cela évite de dépendre entièrement du choix du petit modèle local.
    normalized = question.lower()

    if ".pdf" in normalized:
        if any(word in normalized for word in (
            "quiz", "questionnaire", "questions à choix multiples",
            "questions a choix multiples", "qcm"
        )):
            tool = "pdf_quiz"
        elif any(word in normalized for word in (
            "résume", "resume", "résumé", "resume-moi",
            "résumer", "resumer", "summary", "résumer"
        )):
            tool = "pdf_summary"
        else:
            return (
                "Que souhaitez-vous faire avec ce PDF ? "
                "Demandez par exemple : 'Résume le PDF cours.pdf' "
                "ou 'Génère un quiz à partir du PDF cours.pdf'."
            )
    else:
        try:
            decision = choose_action(question)
            tool = decision.get("tool")
        except (json.JSONDecodeError, ValueError):
            return "Erreur : impossible de déterminer l'action à effectuer."
        except Exception as error:
            return f"Erreur lors de l'analyse de la demande : {error}"

    # Calculator
    if tool == "calculator":
        a = decision.get("a")
        b = decision.get("b")
        operation = decision.get("operation")

        if (
            not isinstance(a, (int, float))
            or isinstance(a, bool)
            or not isinstance(b, (int, float))
            or isinstance(b, bool)
        ):
            return "Erreur : les valeurs du calcul sont invalides."

        if operation not in {"add", "subtract", "multiply", "divide"}:
            return "Erreur : opération mathématique non autorisée."

        print("Agent : exécution de l'outil Calculator.")
        return f"Résultat du calcul : {calculate(a, b, operation)}"

    # Summary d'un texte fourni directement
    if tool == "summary":
        print("Agent : exécution de l'outil Summary.")

        prefixes = (
            "résume ce texte :", "résume ce texte:",
            "résume ce cours :", "résume ce cours:",
            "fais un résumé de ce texte :", "fais un résumé de ce texte:",
            "fais un résumé de ce cours :", "fais un résumé de ce cours:",
        )

        text_to_summarize = extract_content(question, prefixes)

        if not text_to_summarize:
            return "Veuillez fournir le texte à résumer."

        try:
            return f"Résumé :\n{summarize(text_to_summarize)}"
        except Exception as error:
            return f"Erreur pendant le résumé : {error}"

    # Quiz d'un cours fourni directement
    if tool == "quiz":
        print("Agent : lancement du quiz interactif.")

        prefixes = (
            "génère un quiz sur ", "genere un quiz sur ",
            "crée un quiz sur ", "cree un quiz sur ",
            "fais un quiz sur ",
            "crée des questions à choix multiples sur ",
            "cree des questions a choix multiples sur ",
        )

        course = extract_content(question, prefixes)

        if not course:
            return "Veuillez fournir le contenu du cours."

        try:
            run_quiz(course, 3)
            return "Quiz terminé."
        except Exception as error:
            return f"Erreur pendant le quiz : {error}"

    # Outils PDF
    if tool in {"pdf_summary", "pdf_quiz"}:
        filename = extract_pdf_filename(question)

        if not filename:
            return (
                "Nom du PDF introuvable. Exemple : "
                "'Résume le PDF cours.pdf'."
            )

        try:
            content = read_pdf(filename)
        except (ValueError, FileNotFoundError) as error:
            return f"Erreur de lecture du PDF : {error}"
        except Exception as error:
            return f"Impossible de lire le PDF : {error}"

        if tool == "pdf_summary":
            print(f"Agent : résumé du PDF {filename} en cours...")

            try:
                return f"Résumé du PDF {filename} :\n{summarize(content)}"
            except Exception as error:
                return f"Erreur pendant le résumé du PDF : {error}"

        print(f"Agent : création du quiz à partir de {filename}...")

        try:
            run_quiz(content, 3)
            return "Quiz PDF terminé."
        except Exception as error:
            return f"Erreur pendant le quiz PDF : {error}"

    # Réponse libre avec le modèle local
    if tool == "question":
        print("Agent : génération de la réponse avec le LLM local.")

        try:
            return ask_llm(question)
        except Exception as error:
            return f"Erreur pendant la génération de la réponse : {error}"

    return f"Erreur : outil inconnu ({tool})."


if __name__ == "__main__":
    print("=== StudyAgent ===")
    print("Modèle local : Ollama / Qwen")
    print("Outils : Calculator, Summary, Quiz, PDF et Question")
    print("Tapez 'quitter' pour arrêter le programme.")

    while True:
        try:
            question = input("\nVotre demande : ").strip()

            if question.lower() in {"quitter", "exit", "quit"}:
                print("StudyAgent arrêté.")
                break

            if not question:
                print("Veuillez saisir une demande.")
                continue

            response = run_agent(question)

            if response:
                print("\nRéponse de l'agent :")
                print(response)

        except KeyboardInterrupt:
            print("\nStudyAgent arrêté.")
            break
        except Exception as error:
            print(f"\nErreur inattendue : {error}")