from pathlib import Path
from uuid import uuid4
import json
import urllib.request

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from pypdf import PdfReader

from agent import run_agent
from llm import ask_llm
from dashboard_db import log_event, get_dashboard_data


# =========================================================
# CONFIGURATION
# =========================================================

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*"}})

app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_FOLDER = PROJECT_ROOT / "documents"

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


# =========================================================
# LECTURE DU PDF
# =========================================================

def extract_pdf_text(pdf_path):
    """Extrait le texte d'un PDF."""

    reader = PdfReader(str(pdf_path))

    if reader.is_encrypted:
        raise ValueError(
            "Ce PDF est protégé par un mot de passe."
        )

    text = "\n".join(
        page.extract_text() or ""
        for page in reader.pages
    ).strip()

    if not text:
        raise ValueError(
            "Aucun texte lisible dans ce PDF. "
            "Un document scanné nécessite une étape OCR."
        )

    return text, len(reader.pages)


# =========================================================
# PAGE D'ACCUEIL DE L'API
# =========================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "success",
        "message": "StudyAgent API fonctionne !"
    })


# =========================================================
# DASHBOARD : STATISTIQUES ET ÉTAT DES SERVICES
# =========================================================

@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    services = {
        "flask": {
            "status": "online",
            "message": "Le backend Flask répond correctement."
        },
        "ollama": {
            "status": "offline",
            "message": "Ollama ne répond pas."
        },
        "model": {
            "name": "qwen2.5:1.5b",
            "status": "unknown",
            "message": "État du modèle non vérifié."
        }
    }

    try:
        url = "http://127.0.0.1:11434/api/tags"
        with urllib.request.urlopen(url, timeout=2) as response:
            ollama_data = json.loads(response.read().decode("utf-8"))

        services["ollama"] = {
            "status": "online",
            "message": "Le serveur Ollama répond correctement."
        }

        models = ollama_data.get("models", [])
        model_found = any(
            model.get("name", "").split(":")[0] == "qwen2.5"
            and model.get("name", "").endswith(":1.5b")
            for model in models
        )

        services["model"] = {
            "name": "qwen2.5:1.5b",
            "status": "available" if model_found else "missing",
            "message": (
                "Le modèle est disponible."
                if model_found
                else "Le modèle qwen2.5:1.5b n'est pas trouvé."
            )
        }
    except Exception:
        app.logger.warning(
            "Ollama est indisponible pendant la vérification du dashboard."
        )

    try:
        dashboard_data = get_dashboard_data()
        return jsonify({
            "status": "success",
            "services": services,
            "stats": dashboard_data["stats"],
            "recent_events": dashboard_data["recent_events"]
        })
    except Exception:
        app.logger.exception("Impossible de charger les données du dashboard.")
        return jsonify({
            "status": "error",
            "message": "Impossible de charger le dashboard."
        }), 500


# =========================================================
# CHAT GÉNÉRAL
# =========================================================

@app.route("/api/chat", methods=["POST"])
def chat():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Requête JSON invalide."
        }), 400

    message = data.get("message")

    if not isinstance(message, str) or not message.strip():
        return jsonify({
            "status": "error",
            "message": "Veuillez saisir un message."
        }), 400

    try:
        response = run_agent(message.strip())
        log_event("chat", "Message traité par StudyAgent")

        return jsonify({
            "status": "success",
            "response": str(response)
        })

    except Exception:
        app.logger.exception(
            "Erreur pendant le chat"
        )

        return jsonify({
            "status": "error",
            "message": (
                "Erreur pendant la discussion avec StudyAgent. "
                "Vérifie que le backend et Ollama fonctionnent."
            )
        }), 500


# =========================================================
# IMPORTATION D'UN PDF
# =========================================================

@app.route("/api/upload", methods=["POST"])
def upload_pdf():

    if "file" not in request.files:
        return jsonify({
            "status": "error",
            "message": "Sélectionne un fichier PDF."
        }), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({
            "status": "error",
            "message": "Aucun fichier sélectionné."
        }), 400

    filename = secure_filename(file.filename)

    if (
        not filename
        or Path(filename).suffix.lower() != ".pdf"
    ):
        return jsonify({
            "status": "error",
            "message": "Seuls les fichiers PDF sont acceptés."
        }), 400

    stored_name = f"{uuid4().hex}_{filename}"
    destination = UPLOAD_FOLDER / stored_name

    try:
        file.save(destination)

        text, page_count = extract_pdf_text(destination)
        log_event(
            "pdf_uploaded",
            f"PDF importé : {filename}",
            metadata={"pages": page_count, "characters": len(text)}
        )

        return jsonify({
            "status": "success",
            "message": "PDF importé avec succès.",
            "document": {
                "name": filename,
                "document_id": stored_name,
                "pages": page_count,
                "characters": len(text)
            }
        })

    except ValueError as error:
        destination.unlink(missing_ok=True)

        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except Exception:
        destination.unlink(missing_ok=True)

        app.logger.exception(
            "Erreur pendant l'importation du PDF"
        )

        return jsonify({
            "status": "error",
            "message": "Impossible de lire ce PDF."
        }), 500


# =========================================================
# RÉSUMÉ, QUESTIONS ET QUIZ À PARTIR DU PDF
# =========================================================

@app.route("/api/document/action", methods=["POST"])
def document_action():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Requête JSON invalide."
        }), 400

    document_id = data.get("document_id")
    action = data.get("action")

    if (
        not isinstance(document_id, str)
        or not document_id.strip()
    ):
        return jsonify({
            "status": "error",
            "message": "Veuillez importer un PDF."
        }), 400

    safe_name = secure_filename(document_id)

    if (
        safe_name != document_id
        or not safe_name.lower().endswith(".pdf")
    ):
        return jsonify({
            "status": "error",
            "message": "Nom de document invalide."
        }), 400

    documents_folder = UPLOAD_FOLDER.resolve()
    pdf_path = (documents_folder / safe_name).resolve()

    if (
        pdf_path.parent != documents_folder
        or not pdf_path.is_file()
    ):
        return jsonify({
            "status": "error",
            "message": (
                "PDF introuvable. Importe-le à nouveau."
            )
        }), 404

    try:
        # Toujours utiliser le contenu du PDF sélectionné.
        content, _ = extract_pdf_text(pdf_path)

        # -------------------------------------------------
        # ACTION 1 : RÉSUMÉ DU COURS
        # -------------------------------------------------

        if action == "summary":

            document_text = content[:12000]

            prompt = f"""
Tu es StudyAgent, un assistant pédagogique.

Résume le cours fourni en français de manière claire
et structurée.

Présente :
- Le sujet principal.
- Les notions importantes.
- Les définitions.
- Les concepts et méthodes essentiels.
- Les points à retenir pour réviser.

Respecte le contenu du document.
N'invente pas d'informations absentes du document.

DOCUMENT :
{document_text}
"""

            response = ask_llm(prompt)
            log_event("summary", f"Résumé généré : {safe_name}")

            return jsonify({
                "status": "success",
                "response": str(response)
            })

        # -------------------------------------------------
        # ACTION 2 : POSER UNE QUESTION SUR LE PDF
        # -------------------------------------------------

        elif action == "question":

            question = data.get("question", "")

            if (
                not isinstance(question, str)
                or not question.strip()
            ):
                return jsonify({
                    "status": "error",
                    "message": "Écris une question sur ton cours."
                }), 400

            document_text = content[:12000]

            prompt = f"""
Tu es StudyAgent, un assistant pédagogique.

Réponds en français à la question de l'étudiant.
Utilise en priorité les informations du document fourni.

Explique simplement et précisément.
Si la réponse ne figure pas dans le document,
indique-le clairement.
N'invente pas de faits et ne prétends pas que le document
contient une information qu'il ne contient pas.

DOCUMENT :
{document_text}

QUESTION DE L'ÉTUDIANT :
{question.strip()}

RÉPONSE :
"""

            response = ask_llm(prompt)
            log_event("document_question", f"Question sur le PDF : {safe_name}")

            return jsonify({
                "status": "success",
                "response": str(response)
            })

        # -------------------------------------------------
        # ACTION 3 : GÉNÉRER UN QUIZ À PARTIR DU PDF
        # -------------------------------------------------

        elif action == "quiz":

            count = data.get("count", 5)

            if (
                not isinstance(count, int)
                or isinstance(count, bool)
                or count not in (3, 5, 10)
            ):
                return jsonify({
                    "status": "error",
                    "message": "Choisis 3, 5 ou 10 questions."
                }), 400

            # Le modèle reçoit le texte du document importé.
            # Pour les PDF longs, seule cette partie est utilisée.
            document_text = content[:12000]

            prompt = f"""
Tu es StudyAgent, un professeur qui crée des quiz
pour aider les étudiants à réviser leurs cours.

MISSION :
Lis le document fourni et crée un quiz basé sur son contenu.

RÈGLES OBLIGATOIRES :
1. Crée exactement {count} questions différentes si le
   document contient assez d'informations.
2. Chaque question doit tester une information précise
   présente dans le document.
3. Les questions doivent être complètes, naturelles
   et compréhensibles.
4. Chaque question doit être une vraie interrogation
   sur le contenu, et non un titre.
5. N'écris jamais seulement "Question 1", "Question 2"
   ou "Quelle est la bonne réponse ?".
6. Chaque question possède exactement quatre options.
7. Les options doivent être des réponses plausibles
   à la question correspondante.
8. Une seule option est correcte.
9. La réponse correcte doit être justifiée par le document.
10. Ajoute une explication courte pour chaque réponse.
11. Couvre différentes notions du cours lorsque possible.
12. N'invente aucune notion, définition, date, formule
    ou information absente du document.
13. Si le document ne permet pas de créer {count}
    questions différentes, retourne seulement les questions
    réellement possibles.
14. Rédige toutes les questions et les réponses en français.
15. Retourne uniquement du JSON valide, sans Markdown,
    sans introduction et sans texte après le JSON.

FORMAT EXACT :
{{
  "questions": [
    {{
      "question": "Question précise sur le contenu du cours ?",
      "options": [
        "Réponse possible A",
        "Réponse possible B",
        "Réponse possible C",
        "Réponse possible D"
      ],
      "answer": 0,
      "explanation": "Explication basée sur le document."
    }}
  ]
}}

Le champ answer représente l'indice de la bonne réponse :
0 = première option,
1 = deuxième option,
2 = troisième option,
3 = quatrième option.

DOCUMENT À ANALYSER :
========== DÉBUT DU COURS ==========
{document_text}
========== FIN DU COURS ==========
"""

            try:
                raw_response = str(ask_llm(prompt)).strip()

                # Retirer les balises Markdown éventuelles.
                if raw_response.startswith("```"):
                    lines = raw_response.splitlines()

                    if lines and lines[0].startswith("```"):
                        lines = lines[1:]

                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]

                    raw_response = "\n".join(lines).strip()

                # Si le modèle ajoute du texte autour du JSON,
                # essayer d'extraire l'objet JSON.
                if not raw_response.startswith("{"):
                    start = raw_response.find("{")
                    end = raw_response.rfind("}")

                    if start != -1 and end > start:
                        raw_response = raw_response[start:end + 1]

                quiz_data = json.loads(raw_response)

                if not isinstance(quiz_data, dict):
                    raise ValueError(
                        "Le résultat du quiz n'est pas un objet JSON."
                    )

                questions = quiz_data.get("questions")

                if not isinstance(questions, list):
                    raise ValueError(
                        "La liste des questions est absente."
                    )

                valid_questions = []

                for item in questions:

                    if not isinstance(item, dict):
                        continue

                    question = item.get("question")
                    options = item.get("options")
                    answer = item.get("answer")
                    explanation = item.get("explanation", "")

                    # Vérifier la présence d'une vraie question.
                    if (
                        not isinstance(question, str)
                        or len(question.strip()) < 10
                    ):
                        continue

                    if question.strip().lower() in {
                        "question",
                        "question 1",
                        "question 2",
                        "question 3",
                        "question 4",
                        "question 5",
                    }:
                        continue

                    # Vérifier les quatre propositions.
                    if (
                        not isinstance(options, list)
                        or len(options) != 4
                        or not all(
                            isinstance(option, str)
                            and option.strip()
                            for option in options
                        )
                    ):
                        continue

                    # Vérifier l'indice de la bonne réponse.
                    if (
                        not isinstance(answer, int)
                        or isinstance(answer, bool)
                        or answer not in (0, 1, 2, 3)
                    ):
                        continue

                    valid_questions.append({
                        "question": question.strip(),
                        "options": [
                            option.strip()
                            for option in options
                        ],
                        "answer": answer,
                        "explanation": (
                            explanation.strip()
                            if isinstance(explanation, str)
                            else ""
                        )
                    })

                # Ne pas renvoyer un quiz vide ou des options seules.
                if not valid_questions:
                    raise ValueError(
                        "Aucune question complète n'a été générée."
                    )

                # Le modèle peut renvoyer moins de questions si
                # le document est trop court, mais pas davantage.
                valid_questions = valid_questions[:count]

                quiz_data = {
                    "questions": valid_questions
                }
                log_event(
                    "quiz",
                    f"Quiz généré : {safe_name}",
                    metadata={"questions": len(valid_questions)}
                )

                return jsonify({
                    "status": "success",
                    "response": json.dumps(
                        quiz_data,
                        ensure_ascii=False
                    ),
                    "quiz": quiz_data
                })

            except (ValueError, TypeError, AttributeError):
                app.logger.exception(
                    "Échec de génération du quiz à partir du PDF"
                )

                return jsonify({
                    "status": "error",
                    "message": (
                        "Impossible de générer des questions valides "
                        "à partir de ce PDF. Vérifie que le document "
                        "contient du texte lisible, puis réessaie."
                    )
                }), 502

        # -------------------------------------------------
        # ACTION INCONNUE
        # -------------------------------------------------

        else:
            return jsonify({
                "status": "error",
                "message": (
                    "Action inconnue. Utilise summary, question ou quiz."
                )
            }), 400

    except ValueError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except Exception:
        app.logger.exception(
            "Erreur pendant le traitement du document"
        )

        return jsonify({
            "status": "error",
            "message": (
                "Erreur pendant le traitement du PDF. "
                "Vérifie qu'Ollama et le modèle local fonctionnent."
            )
        }), 500


# =========================================================
# GESTION DES FICHIERS TROP VOLUMINEUX
# =========================================================

@app.errorhandler(413)
def file_too_large(error):
    return jsonify({
        "status": "error",
        "message": "Le fichier PDF ne doit pas dépasser 15 Mo."
    }), 413


# =========================================================
# DÉMARRAGE DU BACKEND
# =========================================================

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
