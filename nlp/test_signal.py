from nlp.signal_extractor import extraire_signaux

texte_test = """
Bank Al-Maghrib signale une hausse marginale des retards de paiement 
observés sur les créances en souffrance des PME du secteur BTP au cours du dernier trimestre.
"""

resultat = extraire_signaux(texte_test, "BAM")
print(resultat)