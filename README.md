# Multimodal Fusion Engine - SRI 5A

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)  
[![Pygame](https://img.shields.io/badge/Pygame-2.1%2B-green.svg)](https://www.pygame.org/)

Moteur de fusion multimodale combinant commande vocale, geste et pointage pour créer, déplacer et supprimer des formes graphiques dans une interface interactive.

---

## Prérequis

- Python 3.8 ou supérieur  
- Modules Python : `pygame`, `ivy-python` (optionnel)  
- SRA5 installé et fonctionnel  

Installation rapide des dépendances :

```bash
pip install pygame ivy-python
```

Fichiers principaux

fusion.py : Application principale pour lancer la palette multimodale

ivy.ivy : Module optionnel pour la communication Ivy (SRA5 et gestes)

Lancement

Démarrer SRA5 :

sra5_on


Lancer l’application :

python fusion.py


Si Ivy n’est pas disponible, l’application fonctionne en mode drag & drop uniquement.

Commandes multimodales
Création
Commande	Action
CREATE CIRCLE RED THERE	Créer un cercle rouge → cliquer pour la position
CREATE CIRCLE SELECT THERE	Prendre la couleur sous la souris → cliquer pour la position
Déplacement
Commande	Action
MOVE CIRCLE THERE	Déplacer un cercle (sans couleur) → cliquer destination
MOVE CIRCLE YELLOW THERE	Déplacer un cercle jaune → cliquer destination
MOVE THIS THERE	Pointer un objet avec la souris → cliquer destination
Suppression
Commande	Action
DELETE	Efface toutes les formes
DELETE THERE	Efface la forme cliquée
Quitter
Commande	Action
QUIT	Ferme l’application
Drag & Drop

Cliquer et glisser une forme pour la déplacer librement

Fonctionne uniquement si aucune commande multimodale n’est en cours

Formes supportées

Cercle (CIRCLE)

Rectangle (RECTANGLE)

Triangle (TRIANGLE)

Losange (DIAMOND)

Notes

Fusion des informations vocale, gestuelle et pointage avec un timeout de 3 secondes

Ivy permet de recevoir les messages SRA5 et de reconnaissance gestuelle

Sans Ivy, seules les interactions souris / drag & drop fonctionnent
