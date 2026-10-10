def calculate(a, b, operation):
    if operation == "add":
        return a + b

    elif operation == "subtract":
        return a - b

    elif operation == "multiply":
        return a * b

    elif operation == "divide":
        if b == 0:
            return "Erreur : division par zéro"

        return a / b

    else:
        return "Erreur : opération inconnue"


if __name__ == "__main__":
    print(calculate(10, 5, "add"))
    print(calculate(10, 5, "subtract"))
    print(calculate(10, 5, "multiply"))
    print(calculate(10, 5, "divide"))