import json
from llm import ask_llm


def generate_quiz(course, number_of_questions=5):
    course = course.strip()

    if not course:
        return []

    prompt = f"""
Tu es un générateur de quiz pédagogique.

Utilise uniquement les faits présents dans le cours.
Ne pose pas de question si la réponse n'est pas dans le cours.
Chaque question doit avoir quatre choix distincts et une seule réponse correcte.
La réponse correcte doit être justifiée par le cours.

Cours :
{course}

Génère au maximum {number_of_questions} questions.

Retourne uniquement un tableau JSON valide :
[
  {{
    "question": "Question",
    "options": {{
      "A": "Choix A",
      "B": "Choix B",
      "C": "Choix C",
      "D": "Choix D"
    }},
    "answer": "A",
    "justification": "Justification fondée sur le cours"
  }}
]
"""

    try:
        response = ask_llm(prompt).strip()
        start = response.find("[")
        end = response.rfind("]")

        if start == -1 or end == -1:
            return []

        questions = json.loads(response[start:end + 1])

        if not isinstance(questions, list):
            return []

        validated = []

        for item in questions:
            if not isinstance(item, dict):
                continue

            options = item.get("options")
            answer = item.get("answer")

            if not isinstance(options, dict):
                continue

            if set(options) != {"A", "B", "C", "D"}:
                continue

            if not all(
                isinstance(options[key], str) and options[key].strip()
                for key in ("A", "B", "C", "D")
            ):
                continue

            if answer not in {"A", "B", "C", "D"}:
                continue

            if len(set(options.values())) != 4:
                continue

            if not isinstance(item.get("question"), str):
                continue

            if not isinstance(item.get("justification"), str):
                continue

            validated.append({
                "question": item["question"],
                "options": options,
                "answer": answer,
                "justification": item["justification"]
            })

        return validated[:number_of_questions]

    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    except Exception:
        return []


def run_quiz(course, number_of_questions=5):
    questions = generate_quiz(course, number_of_questions)

    if not questions:
        print("Impossible de générer un quiz valide.")
        return

    score = 0

    print("\n===== QUIZ STUDYAGENT =====")

    for index, item in enumerate(questions, start=1):
        print(f"\nQuestion {index}/{len(questions)}")
        print(item["question"])

        for letter in ("A", "B", "C", "D"):
            print(f"{letter}. {item['options'][letter]}")

        while True:
            answer = input("Votre réponse (A/B/C/D) : ").strip().upper()

            if answer in {"A", "B", "C", "D"}:
                break

            print("Veuillez saisir A, B, C ou D.")

        if answer == item["answer"]:
            print("Bonne réponse !")
            score += 1
        else:
            print(f"Mauvaise réponse. Réponse attendue : {item['answer']}")

        print(f"Explication : {item['justification']}")

    percentage = score / len(questions) * 100

    print("\n===== RÉSULTAT =====")
    print(f"Score : {score}/{len(questions)}")
    print(f"Pourcentage : {percentage:.1f} %")


if __name__ == "__main__":
    course = input("Collez votre cours : ").strip()

    if course:
        run_quiz(course, 3)
    else:
        print("Veuillez fournir un cours.")