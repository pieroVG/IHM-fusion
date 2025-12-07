import pygame
import sys
import threading
import unicodedata
import math
from queue import Queue
import speech_recognition as sr

# ------------------------------
# CONFIGURATION
# ------------------------------
pygame.init()

WIDTH, HEIGHT = 800, 600
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
COLORS = {
    "rouge": RED,
    "vert": GREEN,
    "bleu": BLUE,
    "jaune": YELLOW,
    "noir": BLACK,
    "blanc": WHITE
}

PALETTE_HEIGHT = 50
COLOR_BOX_SIZE = 40
COLOR_MARGIN = 10

ETAT_ATTENTE = "ATTENTE"
ETAT_DEPLACEMENT = "DEPLACEMENT"
ETAT_ATTENTE_CREATION = "ATTENTE_CREATION"

# ------------------------------
# OUTILS
# ------------------------------
def normaliser(texte):
    if not texte:
        return ""
    texte = unicodedata.normalize('NFD', texte)
    texte = ''.join(c for c in texte if unicodedata.category(c) != 'Mn')
    return texte.lower()

def assombrir(c):
    return tuple(max(v - 70, 0) for v in c)

# ------------------------------
# FORMES
# ------------------------------
class Forme:
    def __init__(self, x, y, color=WHITE):
        self.x = x
        self.y = y
        self.color = color

    def set_location(self, x, y):
        self.x, self.y = x, y

    def set_color(self, color):
        self.color = color

    def distance_to(self, pos):
        return ((self.x - pos[0]) ** 2 + (self.y - pos[1]) ** 2) ** 0.5

    def draw(self, screen):
        pass

class Cercle(Forme):
    radius = 30
    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (self.x, self.y), self.radius)

class Rectangle(Forme):
    width = 60
    height = 40
    def draw(self, screen):
        pygame.draw.rect(screen, self.color,
                         (self.x - self.width // 2, self.y - self.height // 2,
                          self.width, self.height))

class Triangle(Forme):
    size = 50
    def draw(self, screen):
        points = [
            (self.x, self.y - self.size),
            (self.x + self.size, self.y + self.size),
            (self.x - self.size, self.y + self.size)
        ]
        pygame.draw.polygon(screen, self.color, points)

class Losange(Forme):
    size = 50
    def draw(self, screen):
        points = [
            (self.x, self.y - self.size),
            (self.x + self.size, self.y),
            (self.x, self.y + self.size),
            (self.x - self.size, self.y)
        ]
        pygame.draw.polygon(screen, self.color, points)

# ------------------------------
# ÉCOUTE VOCALE
# ------------------------------
def ecouter_thread(queue):
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            while True:
                try:
                    audio = recognizer.listen(source, timeout=1, phrase_time_limit=3)
                    txt = recognizer.recognize_google(audio, language="fr-FR")
                    queue.put(normaliser(txt))
                except:
                    pass
    except:
        pass

# ------------------------------
# $1 Recognizer minimal
# ------------------------------
class DollarOneRecognizer:
    def __init__(self):
        self.templates = {}
    
    def add_template(self, name, points):
        self.templates[name] = self.resample(points)
    
    def resample(self, points, n=64):
        if len(points) < 2:
            return points
        total_len = sum(math.dist(points[i], points[i+1]) for i in range(len(points)-1))
        D = total_len / (n-1)
        new_points = [points[0]]
        d = 0
        for i in range(1, len(points)):
            dist = math.dist(points[i-1], points[i])
            if (d + dist) >= D:
                t = (D - d) / dist
                x = points[i-1][0] + t*(points[i][0]-points[i-1][0])
                y = points[i-1][1] + t*(points[i][1]-points[i-1][1])
                new_points.append((x, y))
                points.insert(i, (x, y))
                d = 0
            else:
                d += dist
        while len(new_points) < n:
            new_points.append(points[-1])
        return new_points

    def recognize(self, points):
        points = self.resample(points)
        best_score = float('inf')
        best_name = None
        for name, template in self.templates.items():
            score = sum(math.dist(points[i], template[i]) for i in range(len(points)))
            if score < best_score:
                best_score = score
                best_name = name
        return best_name

# ------------------------------
# PROGRAMME PRINCIPAL
# ------------------------------
def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Palette + $1 Recognizer + Voice")

    forme_courante = None
    couleur_originale = None
    couleur_courante = BLACK
    formes = []
    etat = ETAT_ATTENTE

    # Variables création forme "ici après couleur"
    creation_points = []
    creation_shape_name = None
    creation_forme = None
    creation_attend_couleur = False
    couleur_choisie = None

    drawing = False
    drawing_points = []

    commande_queue = Queue()
    t = threading.Thread(target=ecouter_thread, args=(commande_queue,))
    t.daemon = True
    t.start()

    recognizer = DollarOneRecognizer()
    recognizer.add_template("cercle", [(math.cos(t)*50+400, math.sin(t)*50+300) for t in [i*2*math.pi/32 for i in range(32)]])
    recognizer.add_template("rectangle", [(350,250),(450,250),(450,350),(350,350)])
    recognizer.add_template("triangle", [(400,250),(450,350),(350,350)])
    recognizer.add_template("losange", [(400,250),(450,300),(400,350),(350,300)])

    running = True
    while running:
        screen.fill(WHITE)
        current_mouse_pos = pygame.mouse.get_pos()

        # ------------------------------
        # Affichage palette
        # ------------------------------
        palette_rects = {}
        x_offset = COLOR_MARGIN
        for nom, col in COLORS.items():
            rect = pygame.Rect(x_offset, COLOR_MARGIN, COLOR_BOX_SIZE, COLOR_BOX_SIZE)
            pygame.draw.rect(screen, col, rect)
            if col == couleur_courante:
                pygame.draw.rect(screen, BLACK, rect, 3)
            palette_rects[nom] = rect
            x_offset += COLOR_BOX_SIZE + COLOR_MARGIN

        # ------------------------------
        # Événements souris
        # ------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked_on_palette = False
                for nom, rect in palette_rects.items():
                    if rect.collidepoint(event.pos):
                        couleur_courante = COLORS[nom]
                        clicked_on_palette = True
                        break

                if not clicked_on_palette and event.pos[1] > PALETTE_HEIGHT:
                    drawing = True
                    drawing_points = [event.pos]

            elif event.type == pygame.MOUSEMOTION and drawing:
                drawing_points.append(event.pos)

            elif event.type == pygame.MOUSEBUTTONUP and drawing:
                drawing = False
                if len(drawing_points) > 1:
                    if etat == ETAT_ATTENTE_CREATION:
                        # Reconnaissance de la forme mais on ne crée pas l'objet encore
                        creation_shape_name = recognizer.recognize(drawing_points)
                        creation_points = drawing_points.copy()
                        creation_attend_couleur = True
                        print("Forme dessinée, dis la couleur.")
                    else:
                        # création normale directement
                        shape_name = recognizer.recognize(drawing_points)
                        xs = [p[0] for p in drawing_points]
                        ys = [p[1] for p in drawing_points]
                        center = (sum(xs)//len(xs), sum(ys)//len(ys))

                        if shape_name == "cercle": formes.append(Cercle(*center, couleur_courante))
                        elif shape_name == "rectangle": formes.append(Rectangle(*center, couleur_courante))
                        elif shape_name == "triangle": formes.append(Triangle(*center, couleur_courante))
                        elif shape_name == "losange": formes.append(Losange(*center, couleur_courante))

        # ------------------------------
        # Commandes vocales
        # ------------------------------
        while not commande_queue.empty():
            speech = commande_queue.get()

            if speech:
                print("Commande vocale :", speech)

                # Création vocale normale
                if any(f in speech for f in ["cercle", "rectangle", "triangle", "losange"]) and etat != ETAT_ATTENTE_CREATION:
                    pos = current_mouse_pos if "ici" in speech else (WIDTH//2, HEIGHT//2)

                    if "cercle" in speech: forme = Cercle(*pos)
                    elif "rectangle" in speech: forme = Rectangle(*pos)
                    elif "triangle" in speech: forme = Triangle(*pos)
                    elif "losange" in speech: forme = Losange(*pos)

                    for nom, col in COLORS.items():
                        if nom in speech:
                            forme.set_color(col)
                            break
                    else:
                        forme.set_color(couleur_courante)

                    formes.append(forme)

                # Nouvelle fonctionnalité : "créé un"
                if "créé un" in speech or "crée un" in speech or "creer un" in speech or "creer" in speech or "dessine un" in speech or "dessine" in speech:
                    etat = ETAT_ATTENTE_CREATION
                    drawing_points = []
                    creation_points = []
                    creation_shape_name = None
                    creation_forme = None
                    creation_attend_couleur = False
                    couleur_choisie = None
                    print("Dessinez la forme avec la souris...")

                # Choix couleur puis placement
                if etat == ETAT_ATTENTE_CREATION and creation_shape_name:
                    if creation_attend_couleur:
                        # On attend la couleur
                        for nom, col in COLORS.items():
                            if nom in speech:
                                couleur_choisie = col
                                creation_attend_couleur = False
                                print(f"Couleur {nom} choisie. Dites 'ici' pour placer la forme.")
                                break
                    else:
                        # On attend le "ici"
                        if "ici" in speech:
                            # Créer réellement la forme avec couleur et position
                            xs = [p[0] for p in creation_points]
                            ys = [p[1] for p in creation_points]
                            center = current_mouse_pos

                            if creation_shape_name == "cercle": creation_forme = Cercle(*center, couleur_choisie)
                            elif creation_shape_name == "rectangle": creation_forme = Rectangle(*center, couleur_choisie)
                            elif creation_shape_name == "triangle": creation_forme = Triangle(*center, couleur_choisie)
                            elif creation_shape_name == "losange": creation_forme = Losange(*center, couleur_choisie)

                            formes.append(creation_forme)

                            # Réinitialisation
                            creation_points = []
                            creation_shape_name = None
                            creation_forme = None
                            couleur_choisie = None
                            etat = ETAT_ATTENTE
                            print("Forme créée et placée !")

                # Déplacement en 2 temps
                if "deplace ca" in speech or "déplace ça" in speech or "des places" in speech or "des places ca" in speech or "des places ca" in speech or "bouge ca" in speech or "bouge" in speech:
                    if formes:
                        forme_courante = min(formes, key=lambda f: f.distance_to(current_mouse_pos))
                        couleur_originale = forme_courante.color
                        forme_courante.set_color(assombrir(couleur_originale))
                        etat = ETAT_DEPLACEMENT

                if etat == ETAT_DEPLACEMENT and "ici" in speech:
                    forme_courante.set_location(*current_mouse_pos)
                    forme_courante.set_color(couleur_originale)
                    forme_courante = None
                    etat = ETAT_ATTENTE

                if "quitter" in speech:
                    running = False

        # ------------------------------
        # Dessin temporaire
        # ------------------------------
        if drawing and len(drawing_points) > 1:
            pygame.draw.lines(screen, couleur_courante, False, drawing_points, 3)

        # ------------------------------
        # Affichage des formes
        # ------------------------------
        for f in formes:
            f.draw(screen)

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
