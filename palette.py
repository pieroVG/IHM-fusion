import pygame
import random
import sys
import speech_recognition as sr
from queue import Queue
import time
import threading

# Initialisation de pygame
pygame.init()
pygame.mixer.init()

# Définition des constantes et des couleurs
WIDTH, HEIGHT = 800, 600
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
COLORS = {'rouge': RED, 'vert': GREEN, 'bleu': BLUE, 'jaune': YELLOW, 'noir': BLACK, 'blanc': WHITE}

# États
INITIAL = "INITIAL"
AFFICHER_FORMES = "AFFICHER_FORMES"

# ----- Classes des formes -----
class Forme:
    def __init__(self, x, y, color=WHITE):
        self.x = x
        self.y = y
        self.color = color
    
    def set_location(self, x, y):
        self.x, self.y = x, y

    def set_color(self, color):
        self.color = color
    
    def draw(self, screen):
        pass
    
    def distance_to(self, pos):
        return ((self.x - pos[0])**2 + (self.y - pos[1])**2) ** 0.5


class Cercle(Forme):
    def __init__(self, x, y, color=WHITE):
        super().__init__(x, y, color)
        self.radius = 30
    
    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (self.x, self.y), self.radius)


class Rectangle(Forme):
    def __init__(self, x, y, color=WHITE):
        super().__init__(x, y, color)
        self.width = 60
        self.height = 40
    
    def draw(self, screen):
        pygame.draw.rect(screen, self.color, (self.x - self.width//2, self.y - self.height//2, self.width, self.height))


class Triangle(Forme):
    def __init__(self, x, y, color=WHITE):
        super().__init__(x, y, color)
        self.size = 50
    
    def draw(self, screen):
        points = [(self.x, self.y - self.size), (self.x + self.size, self.y + self.size),
                  (self.x - self.size, self.y + self.size)]
        pygame.draw.polygon(screen, self.color, points)


class Losange(Forme):
    def __init__(self, x, y, color=WHITE):
        super().__init__(x, y, color)
        self.size = 50
    
    def draw(self, screen):
        points = [(self.x, self.y - self.size), (self.x + self.size, self.y),
                  (self.x, self.y + self.size), (self.x - self.size, self.y)]
        pygame.draw.polygon(screen, self.color, points)

# ----- Utilitaires -----
def assombrir_couleur(couleur):
    return tuple(max(c - 70, 0) for c in couleur)

# ----- Écoute vocale -----
def ecouter_commande_thread(commande_queue):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        while True:
            try:
                audio = recognizer.listen(source, timeout=1, phrase_time_limit=3)
                commande = recognizer.recognize_google(audio, language="fr-FR")
                print(f"Commande entendue : {commande}")
                commande_queue.put(commande.lower())
            except:
                commande_queue.put(None)

# ----- Programme principal -----
def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Palette multimodale")

    formes = []
    mae = INITIAL

    commande_queue = Queue()
    listen_thread = threading.Thread(target=ecouter_commande_thread, args=(commande_queue,))
    listen_thread.daemon = True
    listen_thread.start()

    forme_selectionnee = None
    couleur_originale = None
    selection_active = False
    souris_mouvement = False  # Indicateur de mouvement de souris
    derniere_pos_souris = (0, 0)
    temps_dernier_mouvement = time.time()

    running = True
    while running:
        screen.fill(WHITE)

        # --- Commandes vocales ---
        if not commande_queue.empty():
            commande = commande_queue.get()
            if commande:
                # Création d’une forme
                if any(f in commande for f in ["cercle", "rectangle", "triangle", "losange"]):
                    pos = pygame.mouse.get_pos() if "ici" in commande else (WIDTH // 2, HEIGHT // 2)

                    if "cercle" in commande:
                        forme = Cercle(*pos)
                    elif "rectangle" in commande:
                        forme = Rectangle(*pos)
                    elif "triangle" in commande:
                        forme = Triangle(*pos)
                    elif "losange" in commande:
                        forme = Losange(*pos)

                    # Déterminer la couleur
                    couleur_trouvee = False
                    for c_nom, c_val in COLORS.items():
                        if c_nom in commande:
                            forme.set_color(c_val)
                            couleur_trouvee = True
                            break
                    if not couleur_trouvee:
                        forme.set_color(random.choice([RED, GREEN, BLUE, YELLOW, BLACK]))

                    formes.append(forme)
                    mae = AFFICHER_FORMES

                # Déplacement par la parole
                elif "déplace ça ici" in commande and formes:
                    souris = pygame.mouse.get_pos()
                    # Trouver la forme la plus proche du pointeur
                    forme_selectionnee = min(formes, key=lambda f: f.distance_to(souris))
                    couleur_originale = forme_selectionnee.color
                    forme_selectionnee.set_color(assombrir_couleur(forme_selectionnee.color))
                    selection_active = True
                    souris_mouvement = True
                    print(f"Forme {forme_selectionnee.__class__.__name__} sélectionnée pour déplacement.")

                elif "là" in commande and selection_active and forme_selectionnee:
                    souris = pygame.mouse.get_pos()
                    forme_selectionnee.set_location(*souris)
                    forme_selectionnee.set_color(couleur_originale)
                    forme_selectionnee = None
                    selection_active = False
                    souris_mouvement = False
                    print("Forme déplacée.")

                elif "quitter" in commande:
                    running = False

        # --- Suivi visuel pendant le déplacement ---
        souris = pygame.mouse.get_pos()
        if souris_mouvement and forme_selectionnee:
            forme_selectionnee.set_location(*souris)
            derniere_pos_souris = souris
            # Ne pas mettre à jour `temps_dernier_mouvement` tant que la souris bouge
            temps_dernier_mouvement = time.time()

        # --- Vérification du délai pour poser la forme ---
        if selection_active:
            # Vérifier si la souris a cessé de bouger
            if time.time() - temps_dernier_mouvement > 0.5:
                # Si la position n'a pas changé suffisamment
                if abs(derniere_pos_souris[0] - souris[0]) < 5 and abs(derniere_pos_souris[1] - souris[1]) < 5:
                    forme_selectionnee.set_location(*derniere_pos_souris)
                    forme_selectionnee.set_color(couleur_originale)
                    forme_selectionnee = None
                    selection_active = False
                    souris_mouvement = False
                    print("Forme posée après 0.5 seconde d'inactivité.")

        # --- Événements Pygame ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # --- Affichage ---
        if mae != INITIAL:
            for f in formes:
                f.draw(screen)

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
