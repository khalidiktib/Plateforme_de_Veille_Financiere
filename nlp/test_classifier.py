from nlp.classifier import classifier_document

resume_test = """
La Bourse de Casablanca a clôturé en hausse portée par le secteur bancaire. 
Le volume global des échanges a dépassé 1,5 milliard de dirhams, 
marquant une accélération notable de la liquidité sur le marché.
"""

resultat = classifier_document(resume_test, "Bourse de Casablanca")
print(resultat)